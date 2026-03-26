import uuid

from sqlalchemy import select

from src.db.models import PipelineRow, StageResultRow
from src.db.session import async_session
from src.models.messages import PipelineExecutionResult, StageResult
from src.models.pipeline import PipelineSpec


async def list_pipelines() -> list[PipelineSpec]:
    """Load all pipelines, most recent first."""
    async with async_session() as session:
        result = await session.execute(
            select(PipelineRow).order_by(PipelineRow.created_at.desc())
        )
        return [
            PipelineSpec.model_validate_json(row.spec_json)
            for row in result.scalars()
        ]


async def save_pipeline(spec: PipelineSpec) -> None:
    """Persist a pipeline spec to the database."""
    row = PipelineRow(
        pipeline_id=spec.pipeline_id,
        name=spec.name,
        repo_url=spec.repo_url,
        goal=spec.goal,
        created_at=spec.created_at,
        work_dir=spec.work_dir,
        spec_json=spec.model_dump_json(),
    )
    async with async_session() as session:
        session.add(row)
        await session.commit()


async def get_pipeline(pipeline_id: str) -> PipelineSpec | None:
    """Load a pipeline spec by ID."""
    async with async_session() as session:
        result = await session.execute(
            select(PipelineRow).where(PipelineRow.pipeline_id == pipeline_id)
        )
        row = result.scalar_one_or_none()
        if not row:
            return None
        return PipelineSpec.model_validate_json(row.spec_json)


async def save_results(pipeline_id: str, execution_result: PipelineExecutionResult) -> None:
    """Persist execution results for a pipeline and update the pipeline status."""
    async with async_session() as session:
        # 1. Update overall pipeline status
        result = await session.execute(
            select(PipelineRow).where(PipelineRow.pipeline_id == pipeline_id)
        )
        pipeline_row = result.scalar_one_or_none()
        if pipeline_row:
            pipeline_row.overall_status = execution_result.overall_status
            pipeline_row.goal_achieved = "true" if execution_result.goal_achieved else "false"
            pipeline_row.execution_duration = str(execution_result.duration_seconds)

        # 2. Delete old stage results
        old = await session.execute(
            select(StageResultRow).where(StageResultRow.pipeline_id == pipeline_id)
        )
        for row in old.scalars():
            await session.delete(row)

        # 3. Insert new stage results
        for stage_id, res in execution_result.stages.items():
            row = StageResultRow(
                id=str(uuid.uuid4()),
                pipeline_id=pipeline_id,
                stage_id=stage_id,
                status=res.status.value,
                exit_code=str(res.exit_code),
                stdout=res.stdout,
                stderr=res.stderr,
                duration_seconds=str(res.duration_seconds),
                result_json=res.model_dump_json(),
            )
            session.add(row)
        await session.commit()


async def update_pipeline(spec: PipelineSpec) -> bool:
    """Update an existing pipeline spec in the database."""
    async with async_session() as session:
        result = await session.execute(
            select(PipelineRow).where(PipelineRow.pipeline_id == spec.pipeline_id)
        )
        row = result.scalar_one_or_none()
        if not row:
            return False
        row.name = spec.name
        row.goal = spec.goal
        row.spec_json = spec.model_dump_json()
        await session.commit()
        return True


async def delete_pipeline(pipeline_id: str) -> bool:
    """Delete a pipeline and its results from the database."""
    async with async_session() as session:
        result = await session.execute(
            select(PipelineRow).where(PipelineRow.pipeline_id == pipeline_id)
        )
        row = result.scalar_one_or_none()
        if not row:
            return False
        await session.delete(row)
        await session.commit()
        return True


async def get_results(pipeline_id: str) -> PipelineExecutionResult | None:
    """Load execution results for a pipeline and synthesize the structural result."""
    async with async_session() as session:
        # Load pipeline row for metadata
        pipeline_res = await session.execute(
            select(PipelineRow).where(PipelineRow.pipeline_id == pipeline_id)
        )
        pipeline_row = pipeline_res.scalar_one_or_none()
        if not pipeline_row:
            return None

        # Load stage results
        result = await session.execute(
            select(StageResultRow).where(StageResultRow.pipeline_id == pipeline_id)
        )
        rows = result.scalars().all()
        if not rows:
            return None
        
        stages = {
            row.stage_id: StageResult.model_validate_json(row.result_json)
            for row in rows
        }
        
        # Determine final output (like app_url) from stage metadata
        final_output = {}
        for res in stages.values():
            if "deploy_url" in res.metadata:
                final_output["app_url"] = res.metadata["deploy_url"]

        return PipelineExecutionResult(
            pipeline_id=pipeline_id,
            overall_status=pipeline_row.overall_status,
            goal_achieved=pipeline_row.goal_achieved == "true",
            stages=stages,
            duration_seconds=float(pipeline_row.execution_duration or 0.0),
            final_output=final_output
        )



async def save_deployment_version(version: "DeploymentVersion") -> None:
    """Save a deployment version for rollback tracking."""
    from src.db.models import DeploymentVersionRow
    from src.models.pipeline import DeploymentVersion
    import json
    
    row = DeploymentVersionRow(
        id=str(uuid.uuid4()),
        version_id=version.version_id,
        pipeline_id=version.pipeline_id,
        timestamp=version.timestamp,
        image=version.image,
        environment=version.environment,
        status=version.status,
        health_check_passed="true" if version.health_check_passed else "false",
        deployment_metadata=json.dumps(version.metadata),
    )
    async with async_session() as session:
        session.add(row)
        await session.commit()


async def get_deployment_version(version_id: str) -> "DeploymentVersion | None":
    """Get a specific deployment version by ID."""
    from src.db.models import DeploymentVersionRow
    from src.models.pipeline import DeploymentVersion
    import json
    
    async with async_session() as session:
        result = await session.execute(
            select(DeploymentVersionRow).where(DeploymentVersionRow.version_id == version_id)
        )
        row = result.scalar_one_or_none()
        if not row:
            return None
        
        return DeploymentVersion(
            version_id=row.version_id,
            pipeline_id=row.pipeline_id,
            timestamp=row.timestamp,
            image=row.image,
            environment=row.environment,
            status=row.status,
            health_check_passed=row.health_check_passed == "true",
            metadata=json.loads(row.deployment_metadata) if row.deployment_metadata else {},
        )


async def get_previous_deployment_version(pipeline_id: str) -> "DeploymentVersion | None":
    """Get the most recent successful deployment version for a pipeline."""
    from src.db.models import DeploymentVersionRow
    from src.models.pipeline import DeploymentVersion
    import json
    
    async with async_session() as session:
        result = await session.execute(
            select(DeploymentVersionRow)
            .where(
                (DeploymentVersionRow.pipeline_id == pipeline_id) &
                (DeploymentVersionRow.status == "success")
            )
            .order_by(DeploymentVersionRow.timestamp.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        if not row:
            return None
        
        return DeploymentVersion(
            version_id=row.version_id,
            pipeline_id=row.pipeline_id,
            timestamp=row.timestamp,
            image=row.image,
            environment=row.environment,
            status=row.status,
            health_check_passed=row.health_check_passed == "true",
            metadata=json.loads(row.deployment_metadata) if row.deployment_metadata else {},
        )


async def get_deployment_history(pipeline_id: str, limit: int = 10) -> list["DeploymentVersion"]:
    """Get deployment history for a pipeline."""
    from src.db.models import DeploymentVersionRow
    from src.models.pipeline import DeploymentVersion
    import json
    
    async with async_session() as session:
        result = await session.execute(
            select(DeploymentVersionRow)
            .where(DeploymentVersionRow.pipeline_id == pipeline_id)
            .order_by(DeploymentVersionRow.timestamp.desc())
            .limit(limit)
        )
        rows = result.scalars().all()
        
        return [
            DeploymentVersion(
                version_id=row.version_id,
                pipeline_id=row.pipeline_id,
                timestamp=row.timestamp,
                image=row.image,
                environment=row.environment,
                status=row.status,
                health_check_passed=row.health_check_passed == "true",
                metadata=json.loads(row.deployment_metadata) if row.deployment_metadata else {},
            )
            for row in rows
        ]


async def update_deployment_version_status(version_id: str, status: str) -> bool:
    """Update the status of a deployment version."""
    from src.db.models import DeploymentVersionRow
    
    async with async_session() as session:
        result = await session.execute(
            select(DeploymentVersionRow).where(DeploymentVersionRow.version_id == version_id)
        )
        row = result.scalar_one_or_none()
        if not row:
            return False
        
        row.status = status
        await session.commit()
        return True
