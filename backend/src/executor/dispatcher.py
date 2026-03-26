import asyncio
import logging
import re
import socket
from datetime import datetime
from typing import Callable, Awaitable, Optional

from src.executor.agents import (
    BuildAgent,
    DeployAgent,
    SecurityAgent,
    TestAgent,
    VerifyAgent,
)
from src.executor.docker_runner import run_in_docker
from src.executor.port_utils import (
    detect_port_conflict,
    extract_port_from_command,
    find_free_port,
    replace_port_in_command,
)
from src.executor.artifact_store import ArtifactStore
from src.executor.replanner import analyze_failure, execute_recovery
from src.executor.scheduler import DAGScheduler
from src.models.messages import (
    PipelineExecutionResult,
    StageRequest,
    StageResult,
    StageStatus,
)
from src.models.pipeline import AgentType, PipelineSpec

logger = logging.getLogger(__name__)

_PORT_PATTERNS = [
    re.compile(r"https?://(?:localhost|127\.0\.0\.1|0\.0\.0\.0):(\d{2,5})"),
    re.compile(r"(?:listening|running|started|serving)\s+(?:on|at)\s+(?:port\s+)?(\d{2,5})", re.IGNORECASE),
    re.compile(r"port\s+(\d{2,5})", re.IGNORECASE),
    re.compile(r"-p\s+(\d{2,5}):\d+"),
]


def extract_deploy_url(stdout: str, stderr: str, command: str = "") -> str | None:
    """Extract a deploy URL from stage output or command by detecting port numbers."""
    for text in (stdout, stderr, command):
        if not text:
            continue
        for pattern in _PORT_PATTERNS:
            match = pattern.search(text)
            if match:
                port = match.group(1)
                return f"http://localhost:{port}"
    return None


AGENT_MAP = {
    AgentType.BUILD: BuildAgent,
    AgentType.TEST: TestAgent,
    AgentType.SECURITY: SecurityAgent,
    AgentType.DEPLOY: DeployAgent,
    AgentType.VERIFY: VerifyAgent,
}


def _collect_upstream_context(
    stage_id: str, scheduler: DAGScheduler, artifact_store: Optional[ArtifactStore] = None, pipeline_id: Optional[str] = None
) -> tuple[dict[str, str], list[str]]:
    """Collect environment variables and artifact paths from upstream stages.

    Injects STAGE_<ID>_STATUS, STAGE_<ID>_EXIT_CODE, and STAGE_<ID>_DURATION
    for each direct predecessor, enabling inter-stage communication.
    """
    env_from_upstream: dict[str, str] = {}
    artifacts_from: list[str] = []

    predecessors = list(scheduler.graph.predecessors(stage_id))
    for pred_id in predecessors:
        result = scheduler._results.get(pred_id)
        if not result:
            continue

        # Inject predecessor status/exit_code/duration as env vars
        prefix = f"STAGE_{pred_id.upper().replace('-', '_')}"
        env_from_upstream[f"{prefix}_STATUS"] = result.status.value
        env_from_upstream[f"{prefix}_EXIT_CODE"] = str(result.exit_code)
        env_from_upstream[f"{prefix}_DURATION"] = f"{result.duration_seconds:.1f}"

        # Forward any metadata from predecessor as env vars
        for key, value in result.metadata.items():
            env_from_upstream[f"{prefix}_{key.upper()}"] = str(value)

        # Collect artifact paths from result
        if result.artifacts:
            artifacts_from.extend(result.artifacts)
        
        # Also collect artifacts from artifact store if available
        if artifact_store and pipeline_id:
            try:
                # Get artifacts from artifact store (now synchronous)
                stored_artifacts = artifact_store.get_artifacts(pipeline_id, pred_id)
                if stored_artifacts:
                    artifacts_from.extend(stored_artifacts)
                    # Add artifact paths as environment variables
                    for i, artifact in enumerate(stored_artifacts):
                        env_var = f"ARTIFACT_{pred_id.upper().replace('-', '_')}_{i}"
                        env_from_upstream[env_var] = artifact
            except Exception as e:
                logger.warning(f"Failed to get artifacts from store for {pred_id}: {e}")

    return env_from_upstream, artifacts_from


async def _execute_stage(
    stage_id: str,
    scheduler: DAGScheduler,
    agents: dict,
    working_dir: str,
    use_docker: bool = False,
    language: str = "",
    command_override: str | None = None,
    on_output: Callable[[str, str], Awaitable[None]] | None = None,
    artifact_store: Optional[ArtifactStore] = None,
    pipeline_id: Optional[str] = None,
) -> StageResult:
    """Execute a single stage using the appropriate agent."""
    stage = scheduler.get_stage(stage_id)
    command = command_override or stage.command

    scheduler.mark_running(stage_id)

    # Collect context from upstream stages for inter-stage communication
    upstream_env, artifacts_from = _collect_upstream_context(stage_id, scheduler, artifact_store, pipeline_id)

    # Merge upstream env vars with stage-defined env vars (stage takes precedence)
    merged_env = {**upstream_env, **(stage.env_vars or {})}

    # Docker execution path
    if use_docker:
        result = await run_in_docker(
            command=command,
            work_dir=working_dir,
            language=language,
            timeout=stage.timeout_seconds,
            env_vars=merged_env or None,
        )
        # If Docker fails (not installed), fall back to local execution
        if result.status == StageStatus.FAILED and "Docker not installed" in result.stderr:
            logger.warning("Docker unavailable, falling back to local execution for stage %s", stage_id)
        else:
            result.stage_id = stage_id
            return result

    # Local execution path
    agent = agents.get(stage.agent)
    if not agent:
        logger.error("No agent for type %s", stage.agent)
        return StageResult(
            stage_id=stage_id,
            status=StageStatus.FAILED,
            stderr=f"No agent registered for type {stage.agent}",
        )

    # Build per-line streaming callback
    line_callback = None
    if on_output:
        async def line_callback(line: str) -> None:
            await on_output(stage_id, line)

    request = StageRequest(
        stage_id=stage_id,
        command=command,
        working_dir=working_dir,
        env_vars=merged_env,
        timeout=stage.timeout_seconds,
        artifacts_from=artifacts_from,
        on_output=line_callback,
    )

    result = await agent.execute(request)
    
    # Hidden failure detection: some tools exit with 0 even on fatal errors
    if result.status == StageStatus.SUCCESS:
        combined = (result.stdout or "") + (result.stderr or "")
        hidden_patterns = [
            "ModuleNotFoundError:",
            "ImportError:",
            "SyntaxError:",
            "RuntimeError:",
        ]
        if any(p in combined for p in hidden_patterns):
            logger.warning("Hidden failure detected in stage %s despite exit code 0", stage_id)
            result.status = StageStatus.FAILED
            result.exit_code = 1
            
    return result


class PipelineExecutor:
    """Modular engine for orchesterating and executing CI/CD pipelines."""

    def __init__(
        self,
        spec: PipelineSpec,
        working_dir: str = ".",
        on_update: Callable[[dict], Awaitable[None]] | None = None,
    ):
        self.spec = spec
        self.working_dir = working_dir
        self.on_update = on_update
        self.scheduler = DAGScheduler(spec)
        self.agents = {agent_type: cls() for agent_type, cls in AGENT_MAP.items()}
        self.start_time: Optional[datetime] = None
        self.use_docker = spec.use_docker
        self.language = spec.analysis.language if spec.analysis else ""
        self.artifact_store = ArtifactStore()  # Initialize artifact store


    async def _on_stage_output(self, stage_id: str, line: str) -> None:
        """Broadcast a single stdout line from a running stage."""
        await self._broadcast({
            "stage_id": stage_id,
            "status": "running",
            "log_type": "stage_output",
            "log_message": line,
            "stdout_line": line,
        })

    async def _broadcast(self, data: dict) -> None:
        if self.on_update:
            await self.on_update(data)

    async def run(self) -> PipelineExecutionResult:
        """Execute the pipeline and return a structured result."""
        self.start_time = datetime.now()
        logger.info("Starting pipeline %s: %s", self.spec.pipeline_id, self.spec.name or "Unnamed")
        
        await self._broadcast({
            "log_type": "pipeline_start",
            "log_message": f"Pipeline started with {len(self.spec.stages)} stages",
            "stage_id": "",
            "status": "running",
        })

        while not self.scheduler.is_finished():
            ready = self.scheduler.get_ready_stages()
            if not ready:
                logger.warning("Pipeline stalled — no ready stages")
                await self._broadcast({
                    "log_type": "info",
                    "log_message": "No stages ready to execute — pipeline stalled",
                    "stage_id": "",
                    "status": "failed",
                })
                break

            logger.info("Dispatching %d stages: %s", len(ready), ready)

            # Execute ready stages in parallel
            tasks = [self._execute_stage_with_recovery(sid) for sid in ready]
            # asyncio.gather returns results in the order of tasks, but we don't need to process them here
            # as _execute_stage_with_recovery already handles marking complete and broadcasting.
            await asyncio.gather(*tasks, return_exceptions=True) # return_exceptions to prevent one task from crashing the whole gather

        # Compute final result
        end_time = datetime.now()
        duration = 0.0
        if self.start_time:
            duration = (end_time - self.start_time).total_seconds()
        
        results = self.scheduler.get_all_results()
        succeeded = sum(1 for r in results.values() if r.status == StageStatus.SUCCESS)
        failed = sum(1 for r in results.values() if r.status == StageStatus.FAILED)
        skipped = sum(1 for r in results.values() if r.status == StageStatus.SKIPPED)
        
        # Goal validation
        goal_achieved = self._validate_goal(results)
        
        # Overall status
        if failed > 0:
            overall = "failed"
        elif not goal_achieved:
            overall = "failed"
        else:
            overall = "success"

        final_result = PipelineExecutionResult(
            pipeline_id=self.spec.pipeline_id,
            overall_status=overall,
            goal_achieved=goal_achieved,
            stages=results,
            duration_seconds=duration,
            final_output=self._get_final_output(results)
        )

        await self._broadcast({
            "stage_id": "",
            "status": overall,
            "log_type": "pipeline_done",
            "log_message": f"Pipeline {overall}: {succeeded} succeeded, {failed} failed, {skipped} skipped. Goal '{self.spec.goal}' {'achieved' if goal_achieved else 'NOT achieved'}.",
        })

        return final_result

    def _validate_goal(self, results: dict[str, StageResult]) -> bool:
        """Determine if the primary project goal was achieved."""
        goal_lower = self.spec.goal.lower()
        if any(kw in goal_lower for kw in ["run", "start", "local"]):
            health_stages = [id for id in results if "health_check" in id]
            return any(results[id].status == StageStatus.SUCCESS for id in health_stages) if health_stages else False
        elif any(kw in goal_lower for kw in ["docker", "container", "image"]):
            docker_stages = [id for id in results if "docker_build" in id]
            return any(results[id].status == StageStatus.SUCCESS for id in docker_stages) if docker_stages else False
        return all(r.status != StageStatus.FAILED for r in results.values())

    def _get_final_output(self, results: dict[str, StageResult]) -> dict[str, str]:
        """Collect useful output metadata like URLs."""
        output = {}
        for res in results.values():
            if "deploy_url" in res.metadata:
                output["app_url"] = res.metadata["deploy_url"]
        return output

    async def _execute_stage_with_recovery(self, stage_id: str) -> StageResult:
        """Execute a stage with built-in retry and self-healing logic."""
        stage = self.scheduler.get_stage(stage_id)
        command = stage.command # Use original command for initial execution

        await self._broadcast({
            "stage_id": stage_id,
            "status": "running",
            "log_type": "stage_start",
            "log_message": f"Starting stage '{stage_id}' ({stage.agent.value}) — {str(command)[:80]}",
        })

        # Port conflict auto-recovery for deploy stages (pre-execution check)
        if stage.agent == AgentType.DEPLOY:
            old_port = extract_port_from_command(command)
            # Use a real socket check instead of a hardcoded string
            def is_port_in_use(port: int) -> bool:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    return s.connect_ex(('localhost', port)) == 0

            if old_port and is_port_in_use(old_port):
                try:
                    free_port = find_free_port(preferred=old_port + 1) # Start from next port
                    if free_port:
                        command = replace_port_in_command(command, old_port, free_port)
                        logger.info(
                            "Port %d in use for stage %s, retrying on port %d",
                            old_port, stage_id, free_port,
                        )
                        await self._broadcast({
                            "stage_id": stage_id,
                            "status": "running",
                            "log_type": "recovery_plan",
                            "log_message": f"Port {old_port} was in use. Retrying deploy on port {free_port}.",
                            "recovery_strategy": "FIX_AND_RETRY",
                            "recovery_reason": f"Port {old_port} was in use. Deployed on port {free_port} instead.",
                            "modified_command": command,
                        })
                        # Update health_check stage command with new port if it exists
                        for succ_id in self.scheduler.graph.successors(stage_id):
                            succ_stage = self.scheduler.get_stage(succ_id)
                            if succ_stage.agent == AgentType.VERIFY:
                                succ_stage.command = replace_port_in_command(
                                    succ_stage.command, old_port, free_port
                                )
                except RuntimeError:
                    logger.warning("Could not find a free port for stage %s", stage_id)
        
        result = await _execute_stage(
            stage_id, self.scheduler, self.agents, 
            self.working_dir, self.use_docker, self.language,
            command_override=command,
            on_output=self._on_stage_output,
            artifact_store=self.artifact_store,
            pipeline_id=self.spec.pipeline_id,
        )
        
        # Handle success
        if result.status == StageStatus.SUCCESS:
            # Check if this is a deploy stage and extract the URL
            deploy_url = None
            if stage.agent == AgentType.DEPLOY:
                deploy_url = extract_deploy_url(
                    result.stdout or "", result.stderr or "", command
                )
                # Fallback: check health_check stage command for a port/URL
                if not deploy_url:
                    for succ_id in self.scheduler.graph.successors(stage_id):
                        succ_stage = self.scheduler.get_stage(succ_id)
                        if succ_stage.agent == AgentType.VERIFY:
                            deploy_url = extract_deploy_url("", "", succ_stage.command)
                            if deploy_url:
                                break
                # Last resort: extract port from the command itself
                if not deploy_url:
                    deploy_url = extract_deploy_url("", "", command)

            # Also extract URL from health_check output (confirms actual running port)
            if stage.agent == AgentType.VERIFY:
                hc_url = extract_deploy_url(result.stdout or "", result.stderr or "", command)
                if hc_url:
                    deploy_url = hc_url
                # Parse "Success: service up on port XXXX" from health check output
                port_match = re.search(r"service up on port (\d+)", result.stdout or "")
                if port_match:
                    deploy_url = f"http://localhost:{port_match.group(1)}"

            if deploy_url:
                result.metadata["deploy_url"] = deploy_url
                logger.info("Detected deploy URL for stage %s: %s", stage_id, deploy_url)

            self.scheduler.mark_complete(stage_id, StageStatus.SUCCESS, result)
            broadcast_data = {
                "stage_id": stage_id,
                "status": "success",
                "duration_seconds": result.duration_seconds,
                "log_type": "stage_success",
                "log_message": f"Stage '{stage_id}' succeeded in {result.duration_seconds:.1f}s",
            }
            if deploy_url:
                broadcast_data["deploy_url"] = deploy_url
            await self._broadcast(broadcast_data)
            return result

        # Handle failure (Retries then Replanner)
        # Check if non-critical — skip and continue
        if not stage.critical:
            logger.info("Non-critical stage %s failed, skipping", stage_id)
            result.status = StageStatus.SKIPPED
            self.scheduler.mark_complete(stage_id, StageStatus.SKIPPED, result)
            stderr_preview = (result.stderr or "")[:100]
            await self._broadcast({
                "stage_id": stage_id,
                "status": "skipped",
                "log_type": "stage_skipped",
                "log_message": f"Stage '{stage_id}' failed but is non-critical — skipped. {stderr_preview}",
            })
            return result

        # Check retry count
        if stage.retry_count > 0:
            retries_left = stage.retry_count
            logger.info(
                "Retrying stage %s (%d retries remaining)",
                stage_id,
                retries_left,
            )
            stage.retry_count -= 1
            # Reset status to PENDING for re-execution in next cycle or recursive call
            self.scheduler._statuses[stage_id] = StageStatus.PENDING
            await self._broadcast({
                "stage_id": stage_id,
                "status": "running",
                "log_type": "retry",
                "log_message": f"Retrying stage '{stage_id}' ({retries_left} retries remaining)",
            })
            return await self._execute_stage_with_recovery(stage_id)

        # AI Replanner as final fallback
        try:
            await self._broadcast({
                "stage_id": stage_id,
                "status": "failed",
                "log_type": "recovery_start",
                "log_message": f"Stage '{stage_id}' failed (exit code {result.exit_code}). Analyzing failure for self-healing...",
                "log_tail": (result.stderr or result.stdout or "")[:200],
            })

            plan = await analyze_failure(stage, result, self.spec)
            await self._broadcast({
                "stage_id": stage_id,
                "status": "failed",
                "recovery_strategy": plan.strategy.value,
                "recovery_reason": plan.reason,
                "modified_command": plan.modified_command,
                "log_type": "recovery_plan",
                "log_message": f"Recovery plan for '{stage_id}': {plan.strategy.value} — {plan.reason}" + (f" | New command: {plan.modified_command[:80]}" if plan.modified_command else ""),
            })
            recovery_result = await execute_recovery(plan, stage, self.scheduler, self.agents, self.working_dir)
            if recovery_result is None:
                self.scheduler.mark_complete(stage_id, StageStatus.FAILED, result)
                self.scheduler.skip_dependents(stage_id)
                await self._broadcast({
                    "stage_id": stage_id,
                    "status": "failed",
                    "log_type": "recovery_failed",
                    "log_message": f"Recovery for '{stage_id}' did not produce a result — stage failed. Skipping dependents.",
                })
            elif recovery_result is not None and recovery_result.status == StageStatus.SUCCESS:
                self.scheduler.mark_complete(stage_id, StageStatus.SUCCESS, recovery_result)
                await self._broadcast({
                    "stage_id": stage_id,
                    "status": "success",
                    "duration_seconds": recovery_result.duration_seconds if recovery_result else 0.0,
                    "log_type": "recovery_success",
                    "log_message": f"Self-healing succeeded for '{stage_id}' in {(recovery_result.duration_seconds if recovery_result else 0.0):.1f}s",
                })
                return recovery_result
            else:
                self.scheduler.mark_complete(stage_id, StageStatus.FAILED, recovery_result)
                self.scheduler.skip_dependents(stage_id)
                await self._broadcast({
                    "stage_id": stage_id,
                    "status": "failed",
                    "log_type": "recovery_failed",
                    "log_message": f"Recovery for '{stage_id}' failed — {(recovery_result.stderr or '')[:100]}",
                })
        except Exception as e:
            logger.error("Recovery failed for stage %s: %s", stage_id, e)
            self.scheduler.mark_complete(stage_id, StageStatus.FAILED, result)
            self.scheduler.skip_dependents(stage_id)
            await self._broadcast({
                "stage_id": stage_id,
                "status": "failed",
                "log_type": "recovery_failed",
                "log_message": f"Recovery error for '{stage_id}': {str(e)[:120]}",
            })

        # Mark as failed if all else fails
        self.scheduler.mark_complete(stage_id, StageStatus.FAILED, result)
        if stage.critical:
            self.scheduler.skip_dependents(stage_id)
        
        await self._broadcast({
            "stage_id": stage_id,
            "status": "failed",
            "log_type": "stage_failed",
            "log_message": f"Stage '{stage_id}' failed after all recovery attempts.",
        })
        return result


async def run_pipeline(
    spec: PipelineSpec,
    working_dir: str = ".",
    on_update: Callable[[dict], Awaitable[None]] | None = None,
) -> PipelineExecutionResult:
    """Entry point for executing a pipeline."""
    executor = PipelineExecutor(spec, working_dir, on_update)
    return await executor.run()
