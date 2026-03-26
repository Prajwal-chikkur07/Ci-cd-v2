"""Unit tests for PipelineExecutor and helper functions in dispatcher.py."""
from __future__ import annotations

import pytest

from src.executor.dispatcher import extract_deploy_url, PipelineExecutor
from src.models.messages import StageStatus
from tests.conftest import make_pipeline_spec, make_stage


# ---------------------------------------------------------------------------
# extract_deploy_url
# ---------------------------------------------------------------------------


def test_extract_url_from_stdout_http():
    url = extract_deploy_url("Server running at http://localhost:3000", "", "")
    assert url == "http://localhost:3000"


def test_extract_url_from_command_port_flag():
    url = extract_deploy_url("", "", "docker run -p 8080:80 myapp")
    assert url == "http://localhost:8080"


def test_extract_url_listening_on_port():
    url = extract_deploy_url("", "Listening on port 5000", "")
    assert url == "http://localhost:5000"


def test_extract_url_returns_none_when_no_port():
    url = extract_deploy_url("Build complete", "No errors", "make build")
    assert url is None


def test_extract_url_prefers_stdout_over_command():
    url = extract_deploy_url("http://localhost:9000", "", "docker run -p 8080:80 app")
    # stdout match should be found first
    assert url == "http://localhost:9000"


# ---------------------------------------------------------------------------
# PipelineExecutor — goal validation
# ---------------------------------------------------------------------------


def test_validate_goal_all_success():
    spec = make_pipeline_spec(goal="deploy to production", stages=[make_stage("build")])
    executor = PipelineExecutor(spec)
    from src.models.messages import StageResult
    results = {"build": StageResult(stage_id="build", status=StageStatus.SUCCESS)}
    assert executor._validate_goal(results) is True


def test_validate_goal_fails_when_stage_failed():
    spec = make_pipeline_spec(goal="deploy to production", stages=[make_stage("build")])
    executor = PipelineExecutor(spec)
    from src.models.messages import StageResult
    results = {"build": StageResult(stage_id="build", status=StageStatus.FAILED)}
    assert executor._validate_goal(results) is False


def test_validate_goal_run_keyword_requires_health_check():
    spec = make_pipeline_spec(
        goal="run locally",
        stages=[
            make_stage("build"),
            make_stage("health_check", depends_on=["build"]),
        ],
    )
    executor = PipelineExecutor(spec)
    from src.models.messages import StageResult
    results = {
        "build": StageResult(stage_id="build", status=StageStatus.SUCCESS),
        "health_check": StageResult(stage_id="health_check", status=StageStatus.SUCCESS),
    }
    assert executor._validate_goal(results) is True


def test_validate_goal_run_keyword_fails_without_health_check_success():
    spec = make_pipeline_spec(
        goal="run locally",
        stages=[
            make_stage("build"),
            make_stage("health_check", depends_on=["build"]),
        ],
    )
    executor = PipelineExecutor(spec)
    from src.models.messages import StageResult
    results = {
        "build": StageResult(stage_id="build", status=StageStatus.SUCCESS),
        "health_check": StageResult(stage_id="health_check", status=StageStatus.FAILED),
    }
    assert executor._validate_goal(results) is False


# ---------------------------------------------------------------------------
# PipelineExecutor — full run with mocked agents
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_executor_runs_single_stage_successfully():
    """Executor should run a single echo stage and return success."""
    spec = make_pipeline_spec(stages=[make_stage("build", command="echo hello")])
    updates = []

    async def on_update(data: dict) -> None:
        updates.append(data)

    executor = PipelineExecutor(spec, working_dir="/tmp", on_update=on_update)
    result = await executor.run()

    assert result.overall_status == "success"
    assert result.goal_achieved is True
    assert "build" in result.stages
    assert result.stages["build"].status == StageStatus.SUCCESS
    # Should have broadcast at least start + success events
    log_types = [u.get("log_type") for u in updates]
    assert "pipeline_start" in log_types
    assert "stage_start" in log_types
    assert "stage_success" in log_types
    assert "pipeline_done" in log_types


@pytest.mark.asyncio
async def test_executor_respects_stage_dependencies():
    """Stages should execute in dependency order."""
    execution_order: list[str] = []

    spec = make_pipeline_spec(
        stages=[
            make_stage("build", command="echo build"),
            make_stage("test", command="echo test", depends_on=["build"]),
        ]
    )

    async def on_update(data: dict) -> None:
        if data.get("log_type") == "stage_start":
            execution_order.append(data["stage_id"])

    executor = PipelineExecutor(spec, working_dir="/tmp", on_update=on_update)
    await executor.run()

    assert execution_order.index("build") < execution_order.index("test")


@pytest.mark.asyncio
async def test_executor_skips_dependents_on_critical_failure():
    """When a critical stage fails, its dependents should be skipped."""
    spec = make_pipeline_spec(
        stages=[
            make_stage("build", command="exit 1"),
            make_stage("test", command="echo test", depends_on=["build"]),
        ]
    )
    executor = PipelineExecutor(spec, working_dir="/tmp")
    result = await executor.run()

    assert result.overall_status == "failed"
    assert result.stages["build"].status == StageStatus.FAILED
    assert result.stages["test"].status == StageStatus.SKIPPED


@pytest.mark.asyncio
async def test_executor_continues_after_non_critical_failure():
    """Non-critical stage failure should not block downstream stages."""
    spec = make_pipeline_spec(
        stages=[
            make_stage("lint", command="exit 1", critical=False),
            make_stage("build", command="echo build", depends_on=["lint"]),
        ]
    )
    executor = PipelineExecutor(spec, working_dir="/tmp")
    result = await executor.run()

    assert result.stages["lint"].status == StageStatus.SKIPPED
    assert result.stages["build"].status == StageStatus.SUCCESS


@pytest.mark.asyncio
async def test_executor_retries_stage_on_failure():
    """Stage with retry_count > 0 should be retried before giving up."""
    spec = make_pipeline_spec(
        stages=[make_stage("flaky", command="exit 1", retry_count=1)]
    )
    updates = []

    async def on_update(data: dict) -> None:
        updates.append(data)

    executor = PipelineExecutor(spec, working_dir="/tmp", on_update=on_update)
    await executor.run()

    retry_events = [u for u in updates if u.get("log_type") == "retry"]
    assert len(retry_events) >= 1


@pytest.mark.asyncio
async def test_executor_broadcasts_stdout_lines():
    """Live stdout lines should be broadcast as stage_output events."""
    spec = make_pipeline_spec(stages=[make_stage("build", command="echo line1 && echo line2")])
    output_lines: list[str] = []

    async def on_update(data: dict) -> None:
        if data.get("log_type") == "stage_output":
            output_lines.append(data.get("log_message", ""))

    executor = PipelineExecutor(spec, working_dir="/tmp", on_update=on_update)
    await executor.run()

    assert any("line1" in line for line in output_lines)
    assert any("line2" in line for line in output_lines)


@pytest.mark.asyncio
async def test_executor_parallel_independent_stages():
    """Independent stages should be dispatched in parallel."""
    import time
    spec = make_pipeline_spec(
        stages=[
            make_stage("a", command="sleep 0.1 && echo a"),
            make_stage("b", command="sleep 0.1 && echo b"),
        ]
    )
    start = time.monotonic()
    executor = PipelineExecutor(spec, working_dir="/tmp")
    result = await executor.run()
    elapsed = time.monotonic() - start

    assert result.stages["a"].status == StageStatus.SUCCESS
    assert result.stages["b"].status == StageStatus.SUCCESS
    # Parallel execution should be faster than sequential (0.2s)
    assert elapsed < 0.35, f"Expected parallel execution < 0.35s, got {elapsed:.2f}s"
