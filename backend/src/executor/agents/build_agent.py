import logging

from src.executor.agents.base import BaseAgent
from src.models.messages import StageRequest, StageResult

logger = logging.getLogger(__name__)


class BuildAgent(BaseAgent):
    async def execute(self, request: StageRequest) -> StageResult:
        logger.info("BuildAgent executing stage %s: %s", request.stage_id, request.command)
        result = await self.run_command(
            cmd=request.command,
            cwd=request.working_dir,
            timeout=request.timeout,
            env=request.env_vars or None,
            on_output=request.on_output,
        )
        result.stage_id = request.stage_id
        return result
