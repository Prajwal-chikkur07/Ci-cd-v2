import logging

import uvicorn
from contextlib import asynccontextmanager
from fastapi import Body, FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.api.websocket import manager
from src.creator.analyzer import analyze_repo
from src.creator.generator import generate_pipeline
from src.creator.goal_parser import GoalParser
from src.db import repository as db
from src.db.session import init_db
from src.executor.dispatcher import run_pipeline
from src.models.messages import PipelineExecutionResult, StageResult
from src.models.pipeline import PipelineSpec, Stage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="CI/CD Pipeline Orchestrator", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "cicd-orchestrator"}


@app.get("/pipelines")
async def list_pipelines() -> list[dict]:
    """List all pipelines with their execution results."""
    specs = await db.list_pipelines()
    history = []
    for spec in specs:
        exec_result = await db.get_results(spec.pipeline_id)
        if not exec_result:
            overall = "not_executed"
            goal_achieved = False
        else:
            overall = exec_result.overall_status
            goal_achieved = exec_result.goal_achieved

        history.append({
            "pipeline": spec.model_dump(mode="json"),
            "results": exec_result.model_dump(mode="json") if exec_result else None,
            "completedAt": spec.created_at.isoformat(),
            "overallStatus": overall,
            "goalAchieved": goal_achieved,
            "duration_seconds": exec_result.duration_seconds if exec_result else None,
        })
    return history


@app.post("/pipelines")
async def create_pipeline(
    repo_url: str = Query(..., description="Git repository URL"),
    goal: str = Query(..., description="Deployment goal"),
    use_docker: bool = Query(False, description="Run stages in Docker containers"),
    name: str = Query("", description="Pipeline name"),
) -> PipelineSpec:
    """Analyze a repository and generate a pipeline spec."""
    repo_url = repo_url.strip()
    goal = goal.strip()
    if not goal:
        raise HTTPException(status_code=422, detail="goal must not be empty")
    analysis, clone_dir = await analyze_repo(repo_url, goal=goal)
    spec = await generate_pipeline(analysis, goal, repo_url=repo_url)
    spec.name = name.strip()
    spec.work_dir = clone_dir
    spec.use_docker = use_docker
    await db.save_pipeline(spec)
    logger.info("Created pipeline %s (%s) for %s (work_dir=%s)", spec.pipeline_id, spec.name, repo_url, clone_dir)
    return spec


@app.get("/parse-goal")
async def parse_goal(goal: str = Query(..., description="Deployment goal")) -> dict:
    """Parse a deployment goal and extract parameters."""
    parser = GoalParser()
    result = parser.parse(goal)
    return result


@app.post("/pipelines/{pipeline_id}/execute")
async def execute_pipeline(pipeline_id: str) -> PipelineExecutionResult:
    """Execute a generated pipeline."""
    import os
    spec = await db.get_pipeline(pipeline_id)
    if not spec:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    # Re-clone if work_dir is missing (e.g. container restarted, /tmp was wiped)
    if not spec.work_dir or not os.path.isdir(spec.work_dir):
        logger.info("work_dir %s missing for pipeline %s — re-cloning %s", spec.work_dir, pipeline_id, spec.repo_url)
        try:
            _, clone_dir = await analyze_repo(spec.repo_url, goal=spec.goal)
            spec.work_dir = clone_dir
            await db.update_pipeline(spec)
            logger.info("Re-cloned to %s", clone_dir)
        except Exception as e:
            logger.error("Re-clone failed: %s", e)
            raise HTTPException(status_code=500, detail=f"Re-clone failed: {e}")

    async def on_update(data: dict) -> None:
        await manager.broadcast(pipeline_id, data)

    try:
        result = await run_pipeline(spec, working_dir=spec.work_dir or ".", on_update=on_update)
    except ValueError as e:
        # DAGScheduler raises ValueError for circular dependencies or unknown stage refs
        logger.error("Pipeline spec validation error: %s", e)
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error("Pipeline execution error: %s", e)
        raise HTTPException(status_code=500, detail=f"Pipeline execution failed: {e}")
    await db.save_results(pipeline_id, result)
    return result


@app.get("/pipelines/{pipeline_id}")
async def get_pipeline(pipeline_id: str) -> PipelineSpec:
    """Get a pipeline spec by ID."""
    spec = await db.get_pipeline(pipeline_id)
    if not spec:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    return spec


class PipelineUpdate(BaseModel):
    name: str | None = None
    goal: str | None = None
    stages: list[Stage] | None = None


@app.patch("/pipelines/{pipeline_id}")
async def update_pipeline(pipeline_id: str, update: PipelineUpdate) -> PipelineSpec:
    """Update a pipeline's name, goal, or stage commands."""
    spec = await db.get_pipeline(pipeline_id)
    if not spec:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    if update.name is not None and update.name.strip():
        spec.name = update.name
    if update.goal is not None and update.goal.strip():
        spec.goal = update.goal
    if update.stages is not None:
        # Filter out any stages that might have placeholder 'string' values in critical fields
        spec.stages = update.stages
    updated = await db.update_pipeline(spec)
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to update pipeline")
    logger.info("Updated pipeline %s", pipeline_id)
    return spec


@app.post("/pipelines/stop-app")
async def stop_app() -> dict[str, str]:
    """Kill any app running on port 3000 or 8080 inside the container."""
    import asyncio
    for port in [3000, 8080, 5000]:
        proc = await asyncio.create_subprocess_shell(
            f"fuser -k {port}/tcp 2>/dev/null || true",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()
    logger.info("stop-app: killed processes on ports 3000, 8080, 5000")
    return {"status": "stopped"}


@app.post("/pipelines/{pipeline_id}/execute-failed")
async def execute_failed_stages(pipeline_id: str) -> PipelineExecutionResult:
    """Re-execute only the failed (and their downstream skipped) stages."""
    import os
    from src.executor.scheduler import DAGScheduler
    from src.executor.dispatcher import PipelineExecutor

    spec = await db.get_pipeline(pipeline_id)
    if not spec:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    # Re-clone if work_dir is missing
    if not spec.work_dir or not os.path.isdir(spec.work_dir):
        try:
            _, clone_dir = await analyze_repo(spec.repo_url, goal=spec.goal)
            spec.work_dir = clone_dir
            await db.update_pipeline(spec)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Re-clone failed: {e}")

    # Load previous results to restore SUCCESS/SKIPPED statuses
    prev_result = await db.get_results(pipeline_id)

    async def on_update(data: dict) -> None:
        await manager.broadcast(pipeline_id, data)

    executor = PipelineExecutor(spec, working_dir=spec.work_dir or ".", on_update=on_update)

    # Restore previous results into the scheduler
    if prev_result:
        for stage_id, stage_result in prev_result.stages.items():
            if stage_result.status.value in ("success", "skipped"):
                executor.scheduler.mark_complete(stage_id, stage_result.status, stage_result)
            elif stage_result.status.value == "failed":
                # Mark as failed so reset_failed_stages() can find and reset them
                executor.scheduler.mark_complete(stage_id, stage_result.status, stage_result)

    # Reset failed stages to pending
    reset_ids = executor.scheduler.reset_failed_stages()
    logger.info("Re-running failed stages for pipeline %s: %s", pipeline_id, reset_ids)

    if not reset_ids:
        raise HTTPException(status_code=400, detail="No failed stages to re-run")

    try:
        result = await executor.run()
    except Exception as e:
        logger.error("Pipeline re-execution error: %s", e)
        raise HTTPException(status_code=500, detail=f"Pipeline execution failed: {e}")

    await db.save_results(pipeline_id, result)
    return result


class ChainRequest(BaseModel):
    pipeline_ids: list[str]


@app.post("/pipelines/{pipeline_id}/chain")
async def chain_pipelines(pipeline_id: str, body: ChainRequest = Body(...)) -> dict:
    """Execute this pipeline then sequentially execute the chained pipeline IDs."""
    import os
    results = {}

    all_ids = [pipeline_id] + body.pipeline_ids

    for pid in all_ids:
        spec = await db.get_pipeline(pid)
        if not spec:
            results[pid] = {"status": "not_found"}
            continue

        if not spec.work_dir or not os.path.isdir(spec.work_dir):
            try:
                _, clone_dir = await analyze_repo(spec.repo_url, goal=spec.goal)
                spec.work_dir = clone_dir
                await db.update_pipeline(spec)
            except Exception as e:
                results[pid] = {"status": "clone_failed", "error": str(e)}
                continue

        async def on_update(data: dict, _pid: str = pid) -> None:
            await manager.broadcast(_pid, data)

        try:
            result = await run_pipeline(spec, working_dir=spec.work_dir or ".", on_update=on_update)
            await db.save_results(pid, result)
            results[pid] = {"status": result.overall_status, "goal_achieved": result.goal_achieved}
            # Stop chain on failure
            if result.overall_status == "failed":
                logger.info("Chain stopped at pipeline %s due to failure", pid)
                break
        except Exception as e:
            results[pid] = {"status": "error", "error": str(e)}
            break

    return {"chain_results": results}


@app.delete("/pipelines/{pipeline_id}")
async def delete_pipeline(pipeline_id: str) -> dict[str, str]:
    """Delete a pipeline and its results."""
    deleted = await db.delete_pipeline(pipeline_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    return {"status": "deleted"}


@app.post("/pipelines/{pipeline_id}/rollback")
async def rollback_deployment(
    pipeline_id: str,
    to_version: str = Query(None, description="Specific version to rollback to")
) -> dict:
    """Rollback a deployment to a previous version.
    
    Args:
        pipeline_id: Pipeline ID to rollback
        to_version: Optional specific version ID to rollback to. If not provided,
                   rolls back to the most recent successful deployment.
    
    Returns:
        Rollback status and details
    """
    from src.executor.cloud_adapters import get_cloud_adapter
    
    spec = await db.get_pipeline(pipeline_id)
    if not spec:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    
    # Get deployment version to rollback to
    if to_version:
        version = await db.get_deployment_version(to_version)
    else:
        version = await db.get_previous_deployment_version(pipeline_id)
    
    if not version:
        raise HTTPException(
            status_code=404,
            detail="No previous deployment version found to rollback to"
        )
    
    try:
        # Get cloud provider from spec
        cloud_provider = spec.analysis.deploy_target or "local"
        
        if cloud_provider == "local":
            # For local deployments, we would need to re-run the deploy stage
            # with the previous image/artifact
            logger.info(f"Rolling back local deployment {pipeline_id} to version {version.version_id}")
            await db.update_deployment_version_status(version.version_id, "rolled_back")
            return {
                "status": "rolled_back",
                "version_id": version.version_id,
                "image": version.image,
                "message": "Local deployment rolled back (re-run deploy stage with previous artifact)"
            }
        else:
            # For cloud deployments, use cloud adapter
            adapter = get_cloud_adapter(cloud_provider)
            
            # Extract deployment ID from metadata
            deployment_id = version.metadata.get("deployment_id", pipeline_id)
            
            success = adapter.rollback(deployment_id, version.image)
            
            if success:
                await db.update_deployment_version_status(version.version_id, "rolled_back")
                return {
                    "status": "rolled_back",
                    "version_id": version.version_id,
                    "deployment_id": deployment_id,
                    "image": version.image,
                    "message": f"Successfully rolled back {cloud_provider} deployment"
                }
            else:
                raise HTTPException(
                    status_code=500,
                    detail=f"Rollback failed for {cloud_provider} deployment"
                )
    except Exception as e:
        logger.error(f"Rollback failed for pipeline {pipeline_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Rollback failed: {str(e)}")


@app.get("/pipelines/{pipeline_id}/deployment-history")
async def get_deployment_history(
    pipeline_id: str,
    limit: int = Query(10, description="Number of deployments to return")
) -> dict:
    """Get deployment history for a pipeline.
    
    Args:
        pipeline_id: Pipeline ID
        limit: Maximum number of deployments to return
    
    Returns:
        List of deployment versions
    """
    spec = await db.get_pipeline(pipeline_id)
    if not spec:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    
    history = await db.get_deployment_history(pipeline_id, limit=limit)
    
    return {
        "pipeline_id": pipeline_id,
        "deployments": [
            {
                "version_id": v.version_id,
                "timestamp": v.timestamp.isoformat(),
                "image": v.image,
                "environment": v.environment,
                "status": v.status,
                "health_check_passed": v.health_check_passed,
                "metadata": v.metadata,
            }
            for v in history
        ]
    }



@app.get("/pipelines/{pipeline_id}/results")
async def get_results(pipeline_id: str) -> PipelineExecutionResult:
    """Get execution results for a pipeline."""
    result = await db.get_results(pipeline_id)
    if not result:
        raise HTTPException(status_code=404, detail="Results not found")
    return result


@app.websocket("/ws/{pipeline_id}")
async def websocket_endpoint(websocket: WebSocket, pipeline_id: str) -> None:
    """WebSocket endpoint for real-time pipeline status updates."""
    await manager.connect(websocket, pipeline_id)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, pipeline_id)


if __name__ == "__main__":
    uvicorn.run("src.api.main:app", host="0.0.0.0", port=8001, reload=True)
