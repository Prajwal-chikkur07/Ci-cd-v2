"""Unit tests for the rule-based replanner and recovery execution."""
from __future__ import annotations

import pytest

from src.executor.replanner import get_rule_based_plan, analyze_failure
from src.models.messages import RecoveryStrategy, StageResult, StageStatus
from tests.conftest import make_pipeline_spec, make_stage


def _failed_result(stderr: str = "", stdout: str = "", exit_code: int = 1) -> StageResult:
    return StageResult(
        stage_id="test-stage",
        status=StageStatus.FAILED,
        exit_code=exit_code,
        stderr=stderr,
        stdout=stdout,
    )


# ---------------------------------------------------------------------------
# get_rule_based_plan
# ---------------------------------------------------------------------------


def test_rule_flask_async():
    stage = make_stage(command="flask run")
    result = _failed_result(stderr="RuntimeError: Install Flask with the 'async' extra")
    plan = get_rule_based_plan(stage, result)
    assert plan is not None
    assert plan.strategy == RecoveryStrategy.FIX_AND_RETRY
    assert "flask[async]" in (plan.modified_command or "")


def test_rule_missing_python_module():
    stage = make_stage(command="python app.py")
    result = _failed_result(stderr="ModuleNotFoundError: No module named 'uvicorn'")
    plan = get_rule_based_plan(stage, result)
    assert plan is not None
    assert plan.strategy == RecoveryStrategy.FIX_AND_RETRY
    assert "uvicorn" in (plan.modified_command or "")


def test_rule_command_not_found():
    stage = make_stage(command="pytest tests/")
    result = _failed_result(stderr="sh: pytest: command not found")
    plan = get_rule_based_plan(stage, result)
    assert plan is not None
    assert plan.strategy == RecoveryStrategy.FIX_AND_RETRY


def test_rule_port_in_use():
    stage = make_stage(command="python -m flask run --port 5000")
    result = _failed_result(stderr="Address already in use")
    plan = get_rule_based_plan(stage, result)
    assert plan is not None
    assert plan.strategy == RecoveryStrategy.FIX_AND_RETRY


def test_rule_npm_ci_fallback():
    stage = make_stage(command="npm ci")
    result = _failed_result(stderr="ENOENT: no such file or directory, open 'package-lock.json'")
    plan = get_rule_based_plan(stage, result)
    assert plan is not None
    assert plan.strategy == RecoveryStrategy.FIX_AND_RETRY
    assert "npm install" in (plan.modified_command or "")


def test_rule_no_match_returns_none():
    stage = make_stage(command="echo hello")
    result = _failed_result(stderr="some random error")
    plan = get_rule_based_plan(stage, result)
    assert plan is None


# ---------------------------------------------------------------------------
# analyze_failure (async)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_analyze_failure_returns_plan_for_known_error():
    stage = make_stage(command="python app.py")
    result = _failed_result(stderr="ModuleNotFoundError: No module named 'fastapi'")
    spec = make_pipeline_spec()
    plan = await analyze_failure(stage, result, spec)
    assert plan.strategy == RecoveryStrategy.FIX_AND_RETRY


@pytest.mark.asyncio
async def test_analyze_failure_aborts_for_unknown_critical_error():
    stage = make_stage(command="some-unknown-tool", critical=True)
    result = _failed_result(stderr="completely unknown error xyz123", exit_code=127)
    spec = make_pipeline_spec()
    plan = await analyze_failure(stage, result, spec)
    assert plan.strategy == RecoveryStrategy.ABORT


@pytest.mark.asyncio
async def test_analyze_failure_skips_non_critical_stage():
    stage = make_stage(command="some-tool", critical=False)
    result = _failed_result(stderr="completely unknown error xyz123", exit_code=1)
    spec = make_pipeline_spec()
    plan = await analyze_failure(stage, result, spec)
    assert plan.strategy == RecoveryStrategy.SKIP_STAGE


@pytest.mark.asyncio
async def test_analyze_failure_skips_test_stage_with_no_tests():
    from src.models.pipeline import AgentType
    stage = make_stage(agent=AgentType.TEST, command="pytest tests/", critical=True)
    result = _failed_result(stdout="collected 0 items", exit_code=5)
    spec = make_pipeline_spec()
    plan = await analyze_failure(stage, result, spec)
    assert plan.strategy == RecoveryStrategy.SKIP_STAGE


@pytest.mark.asyncio
async def test_analyze_failure_pip_no_cache():
    stage = make_stage(command="pip install -r requirements.txt")
    result = _failed_result(stderr="ERROR: Could not install packages due to an OSError")
    spec = make_pipeline_spec()
    plan = await analyze_failure(stage, result, spec)
    assert plan.strategy == RecoveryStrategy.FIX_AND_RETRY
    assert "--no-cache-dir" in (plan.modified_command or "")


@pytest.mark.asyncio
async def test_analyze_failure_permission_denied():
    stage = make_stage(command="./deploy.sh")
    result = _failed_result(stderr="Permission denied: ./deploy.sh")
    spec = make_pipeline_spec()
    plan = await analyze_failure(stage, result, spec)
    assert plan.strategy == RecoveryStrategy.FIX_AND_RETRY
    assert "chmod" in (plan.modified_command or "")
