import asyncio
import logging
import os
import re
import time
from abc import ABC, abstractmethod
from typing import Callable, Awaitable

from src.models.messages import StageRequest, StageResult, StageStatus

logger = logging.getLogger(__name__)

# Matches commands that background a process: ends with & or has (... &) && sleep N
_BG_PATTERN = re.compile(r'&&\s*sleep\s+\d+\s*$')


class BaseAgent(ABC):
    """Abstract base class for all pipeline execution agents."""

    @abstractmethod
    async def execute(self, request: StageRequest) -> StageResult:
        """Execute a pipeline stage and return the result."""

    async def run_command(
        self,
        cmd: str,
        cwd: str,
        timeout: int = 300,
        env: dict[str, str] | None = None,
        on_output: Callable[[str], Awaitable[None]] | None = None,
    ) -> StageResult:
        """Run a shell command asynchronously, streaming output line-by-line."""
        start = time.monotonic()
        logger.info("Running command: %s (cwd=%s, timeout=%ds)", cmd, cwd, timeout)

        # Background commands (ending with & or `... && sleep N`) keep stdout pipe open forever.
        # Use communicate() so we don't hang waiting for EOF.
        is_background = cmd.rstrip().endswith('&') or bool(_BG_PATTERN.search(cmd.strip()))

        try:
            merged_env = None
            if env:
                merged_env = {**os.environ, **env}

            if is_background or on_output is None:
                # Simple path: capture all output at once (no streaming)
                # For background commands, we MUST use DEVNULL or the pipes will hang
                stdout_dest = asyncio.subprocess.DEVNULL if is_background else asyncio.subprocess.PIPE
                stderr_dest = asyncio.subprocess.DEVNULL if is_background else asyncio.subprocess.PIPE
                
                process = await asyncio.create_subprocess_shell(
                    cmd,
                    cwd=cwd,
                    stdout=stdout_dest,
                    stderr=stderr_dest,
                    env=merged_env,
                )
                try:
                    if is_background:
                        # For background, we just wait for the shell to exit (the sleep N part)
                        await asyncio.wait_for(process.wait(), timeout=timeout)
                        stdout_bytes, stderr_bytes = b"", b""
                    else:
                        stdout_bytes, stderr_bytes = await asyncio.wait_for(
                            process.communicate(), timeout=timeout
                        )
                except asyncio.TimeoutError:
                    process.kill()
                    await process.wait()
                    duration = time.monotonic() - start
                    return StageResult(
                        stage_id="",
                        status=StageStatus.FAILED,
                        exit_code=-1,
                        stdout="",
                        stderr=f"Command timed out after {timeout}s",
                        duration_seconds=duration,
                    )
                duration = time.monotonic() - start
                exit_code = process.returncode or 0
                stdout = stdout_bytes.decode("utf-8", errors="replace")
                stderr = stderr_bytes.decode("utf-8", errors="replace")
                status = StageStatus.SUCCESS if exit_code == 0 else StageStatus.FAILED
                logger.info("Command finished: exit_code=%d duration=%.1fs", exit_code, duration)
                return StageResult(
                    stage_id="",
                    status=status,
                    exit_code=exit_code,
                    stdout=stdout,
                    stderr=stderr,
                    duration_seconds=duration,
                )

            # Streaming path: merge stderr into stdout and emit line-by-line
            process = await asyncio.create_subprocess_shell(
                cmd,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                env=merged_env,
            )

            stdout_lines: list[str] = []

            async def _read_lines() -> None:
                assert process.stdout is not None
                async for raw_line in process.stdout:
                    line = raw_line.decode("utf-8", errors="replace").rstrip("\n")
                    stdout_lines.append(line)
                    if on_output:
                        try:
                            await on_output(line)
                        except Exception:
                            pass

            try:
                await asyncio.wait_for(_read_lines(), timeout=timeout)
                await process.wait()
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                duration = time.monotonic() - start
                logger.warning("Command timed out after %.1fs: %s", duration, cmd)
                return StageResult(
                    stage_id="",
                    status=StageStatus.FAILED,
                    exit_code=-1,
                    stdout="\n".join(stdout_lines),
                    stderr=f"Command timed out after {timeout}s",
                    duration_seconds=duration,
                )

            duration = time.monotonic() - start
            exit_code = process.returncode or 0
            stdout = "\n".join(stdout_lines)
            status = StageStatus.SUCCESS if exit_code == 0 else StageStatus.FAILED
            logger.info("Command finished: exit_code=%d duration=%.1fs", exit_code, duration)

            return StageResult(
                stage_id="",
                status=status,
                exit_code=exit_code,
                stdout=stdout,
                stderr="",
                duration_seconds=duration,
            )

        except OSError as e:
            duration = time.monotonic() - start
            logger.error("Failed to execute command: %s", e)
            return StageResult(
                stage_id="",
                status=StageStatus.FAILED,
                exit_code=-1,
                stdout="",
                stderr=str(e),
                duration_seconds=duration,
            )
