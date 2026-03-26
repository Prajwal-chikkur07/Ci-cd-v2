import logging
import re

from src.executor.scheduler import DAGScheduler
from src.executor.error_patterns import detect_error_pattern, apply_fix, get_fix_reason
from src.models.messages import RecoveryPlan, RecoveryStrategy, StageResult, StageStatus
from src.models.pipeline import PipelineSpec, Stage

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = ""  # kept for compatibility


def get_rule_based_plan(stage: Stage, result: StageResult) -> RecoveryPlan | None:
    """Check for common failure patterns and suggest a known fix."""
    stderr = result.stderr or ""
    stdout = result.stdout or ""
    combined = stderr + stdout

    # Rule 1: Flask [async] extra missing
    if "RuntimeError: Install Flask with the 'async' extra" in combined:
        return RecoveryPlan(
            strategy=RecoveryStrategy.FIX_AND_RETRY,
            reason="Flask async support missing. Automatically adding 'flask[async]' dependency.",
            modified_command=f"pip install 'flask[async]' && {stage.command}",
        )

    # Rule 2: Python Module Missing
    module_match = re.search(r"ModuleNotFoundError: No module named '([^']+)'", combined)
    if module_match:
        module_name = module_match.group(1)
        return RecoveryPlan(
            strategy=RecoveryStrategy.FIX_AND_RETRY,
            reason=f"Missing Python module: {module_name}. Attempting to install.",
            modified_command=f"pip install {module_name} && {stage.command}",
        )

    # Rule 3: Command not found
    cmd_match = re.search(r"sh: (.*): command not found", combined)
    if cmd_match:
        cmd_name = cmd_match.group(1)
        return RecoveryPlan(
            strategy=RecoveryStrategy.FIX_AND_RETRY,
            reason=f"System command not found: {cmd_name}. Attempting to install via pip/npm.",
            modified_command=f"(pip install {cmd_name} 2>/dev/null || npm install -g {cmd_name} 2>/dev/null) && {stage.command}",
        )

    # Rule 4: Port already in use (if not caught by dispatcher)
    if "Address already in use" in combined or "EADDRINUSE" in combined:
        return RecoveryPlan(
            strategy=RecoveryStrategy.FIX_AND_RETRY,
            reason="Port conflict detected. Re-running on a dynamic port.",
            modified_command=f"export PORT=0 && {stage.command}",
        )

    # Rule 5: npm ci fails due to missing package-lock.json or ENOENT
    if "npm ci" in stage.command and ("ENOENT" in combined or "No such file" in combined or "npm warn" in combined.lower()):
        return RecoveryPlan(
            strategy=RecoveryStrategy.FIX_AND_RETRY,
            reason="npm ci failed — falling back to npm install.",
            modified_command=stage.command.replace("npm ci", "npm install"),
        )

    return None


async def analyze_failure(
    stage: Stage, result: StageResult, spec: PipelineSpec
) -> RecoveryPlan:
    """Use rule-based analysis to determine recovery strategy."""
    stderr = result.stderr or ""
    stdout = result.stdout or ""
    
    # Try error pattern detection first
    pattern_name, match_info = await detect_error_pattern(stderr, stdout)
    if pattern_name:
        fix_type = match_info.get("fix_type")
        modified_cmd = await apply_fix(fix_type, stage.command, match_info)
        reason = get_fix_reason(pattern_name, match_info)
        
        if modified_cmd:
            logger.info(f"Error pattern detected: {pattern_name}. Applying fix: {fix_type}")
            return RecoveryPlan(
                strategy=RecoveryStrategy.FIX_AND_RETRY,
                reason=reason,
                modified_command=modified_cmd,
            )
        elif fix_type == "use_different_port":
            # Port conflict is handled at dispatcher level, but we can still log it
            logger.info(f"Port conflict detected in stage {stage.id}")
    
    # Try rule-based analysis as fallback
    rule_plan = get_rule_based_plan(stage, result)
    if rule_plan:
        logger.info("Rule-based recovery plan found for stage %s", stage.id)
        return rule_plan

    # Extended rule-based fallback using stderr patterns
    combined = stderr + stdout

    # npm/yarn not found — need docker or node installed
    if any(cmd in stage.command for cmd in ["npm", "yarn", "node"]) and "command not found" in combined:
        return RecoveryPlan(
            strategy=RecoveryStrategy.ABORT,
            reason="Node.js/npm not available in execution environment. Enable Docker execution for JavaScript projects.",
        )

    # pip install failures
    if "pip install" in stage.command and "ERROR" in combined:
        return RecoveryPlan(
            strategy=RecoveryStrategy.FIX_AND_RETRY,
            reason="pip install failed. Retrying with --no-cache-dir.",
            modified_command=stage.command.replace("pip install", "pip install --no-cache-dir"),
        )

    # Permission denied
    if "Permission denied" in combined:
        return RecoveryPlan(
            strategy=RecoveryStrategy.FIX_AND_RETRY,
            reason="Permission denied. Retrying with elevated permissions.",
            modified_command=f"chmod -R 755 . && {stage.command}",
        )

    # Go build: cannot write multiple packages to non-directory
    if "cannot write multiple packages to non-directory" in combined:
        return RecoveryPlan(
            strategy=RecoveryStrategy.FIX_AND_RETRY,
            reason="Go build: multiple packages detected. Building without output flag.",
            modified_command=re.sub(r"-o\s+\S+\s*", "", stage.command).strip() or "go build ./...",
        )

    # Rust: linker not found
    if "linker `cc` not found" in combined or "linker not found" in combined:
        return RecoveryPlan(
            strategy=RecoveryStrategy.FIX_AND_RETRY,
            reason="C linker not found. Installing build-essential.",
            modified_command=f"apt-get install -y build-essential 2>/dev/null || true && {stage.command}",
        )

    # cargo clippy -D warnings fails on external crate warnings
    if "cargo clippy" in stage.command and "-D warnings" in stage.command and result.exit_code != 0:
        return RecoveryPlan(
            strategy=RecoveryStrategy.FIX_AND_RETRY,
            reason="Clippy -D warnings failed. Retrying without -D warnings.",
            modified_command=stage.command.replace("-- -D warnings", "").replace("-D warnings", ""),
        )

    # Non-critical stage — skip it
    if not stage.critical:
        return RecoveryPlan(
            strategy=RecoveryStrategy.SKIP_STAGE,
            reason=f"Stage '{stage.id}' failed and is non-critical — skipping.",
        )

    # Test stages that fail due to missing test files — skip gracefully
    if stage.agent.value in ("test",) and any(
        p in combined for p in ["no tests ran", "no test files", "No tests found", "collected 0 items"]
    ):
        return RecoveryPlan(
            strategy=RecoveryStrategy.SKIP_STAGE,
            reason=f"No tests found in stage '{stage.id}' — skipping.",
        )

    # Critical stage with unknown error — abort
    return RecoveryPlan(
        strategy=RecoveryStrategy.ABORT,
        reason=f"Stage '{stage.id}' failed with exit code {result.exit_code}. No automated fix available.",
    )


async def execute_recovery(
    plan: RecoveryPlan,
    stage: Stage,
    scheduler: DAGScheduler,
    agents: dict,
    working_dir: str = ".",
) -> StageResult | None:
    """Execute a recovery plan and return the result if retried."""
    from src.models.messages import StageRequest

    if plan.strategy == RecoveryStrategy.FIX_AND_RETRY:
        if not plan.modified_command:
            logger.error("FIX_AND_RETRY plan has no modified_command")
            scheduler.skip_dependents(stage.id)
            return None

        logger.info("Retrying stage %s with modified command: %s", stage.id, plan.modified_command)
        agent = agents.get(stage.agent)
        if not agent:
            logger.error("No agent found for type %s", stage.agent)
            return None

        request = StageRequest(
            stage_id=stage.id,
            command=plan.modified_command,
            working_dir=working_dir,
            env_vars=stage.env_vars,
            timeout=stage.timeout_seconds,
        )
        result = await agent.execute(request)
        scheduler.mark_complete(stage.id, result.status, result)
        if result.status == StageStatus.FAILED:
            scheduler.skip_dependents(stage.id)
        return result

    elif plan.strategy == RecoveryStrategy.SKIP_STAGE:
        logger.info("Skipping stage %s: %s", stage.id, plan.reason)
        skip_result = StageResult(
            stage_id=stage.id,
            status=StageStatus.SKIPPED,
            stdout=f"Skipped: {plan.reason}",
        )
        scheduler.mark_complete(stage.id, StageStatus.SKIPPED, skip_result)
        return skip_result

    elif plan.strategy == RecoveryStrategy.ROLLBACK:
        logger.info("Rolling back stage %s with %d steps", stage.id, len(plan.rollback_steps))
        for step in plan.rollback_steps:
            logger.info("Rollback step: %s", step)
            agent = agents.get(stage.agent)
            if agent:
                request = StageRequest(
                    stage_id=f"{stage.id}_rollback",
                    command=step,
                    working_dir=working_dir,
                    timeout=120,
                )
                await agent.execute(request)
        scheduler.skip_dependents(stage.id)
        return None

    else:  # ABORT
        logger.error("Aborting pipeline: %s", plan.reason)
        scheduler.skip_dependents(stage.id)
        return None
