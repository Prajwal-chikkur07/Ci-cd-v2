"""Unit tests for Pydantic models — serialization, validation, defaults."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.models.messages import (
    PipelineExecutionResult,
    RecoveryPlan,
    RecoveryStrategy,
    StageRequest,
    StageResult,
    StageStatus,
)
from src.models.pipeline import AgentType, DeploymentVersion, PipelineSpec, RepoAnalysis, Stage
from tests.conftest import make_pipeline_spec, make_stage


# ---------------------------------------------------------------------------
# Stage
# ---------------------------------------------------------------------------


def test_stage_defaults():
    s = Stage(id="build", agent=AgentType.BUILD, command="make build")
    assert s.depends_on == []
    assert s.timeout_seconds == 300
    assert s.retry_count == 0
    assert s.critical is True
    assert s.env_vars == {}


def test_stage_rejects_empty_id():
    with pytest.raises(ValidationError):
        Stage(id="", agent=AgentType.BUILD, command="make build")


# ---------------------------------------------------------------------------
# PipelineSpec
# ---------------------------------------------------------------------------


def test_pipeline_spec_generates_uuid():
    spec = make_pipeline_spec()
    assert len(spec.pipeline_id) == 36  # UUID4 format


def test_pipeline_spec_roundtrip_json():
    spec = make_pipeline_spec()
    json_str = spec.model_dump_json()
    restored = PipelineSpec.model_validate_json(json_str)
    assert restored.pipeline_id == spec.pipeline_id
    assert len(restored.stages) == len(spec.stages)


def test_pipeline_spec_with_multiple_stages():
    stages = [
        make_stage("build"),
        make_stage("test", depends_on=["build"]),
        make_stage("deploy", depends_on=["test"]),
    ]
    spec = make_pipeline_spec(stages=stages)
    assert len(spec.stages) == 3


# ---------------------------------------------------------------------------
# StageResult
# ---------------------------------------------------------------------------


def test_stage_result_defaults():
    r = StageResult(stage_id="build", status=StageStatus.SUCCESS)
    assert r.exit_code == -1
    assert r.stdout == ""
    assert r.stderr == ""
    assert r.duration_seconds == 0.0
    assert r.artifacts == []
    assert r.metadata == {}


def test_stage_result_json_roundtrip():
    r = StageResult(
        stage_id="build",
        status=StageStatus.FAILED,
        exit_code=1,
        stderr="error",
        duration_seconds=1.5,
    )
    restored = StageResult.model_validate_json(r.model_dump_json())
    assert restored.status == StageStatus.FAILED
    assert restored.exit_code == 1


# ---------------------------------------------------------------------------
# PipelineExecutionResult
# ---------------------------------------------------------------------------


def test_pipeline_execution_result_success():
    result = PipelineExecutionResult(
        pipeline_id="abc",
        overall_status="success",
        goal_achieved=True,
        stages={"build": StageResult(stage_id="build", status=StageStatus.SUCCESS)},
        duration_seconds=5.0,
    )
    assert result.goal_achieved is True
    assert result.final_output == {}


def test_pipeline_execution_result_json_roundtrip():
    result = PipelineExecutionResult(
        pipeline_id="abc",
        overall_status="failed",
        goal_achieved=False,
        stages={"build": StageResult(stage_id="build", status=StageStatus.FAILED)},
    )
    restored = PipelineExecutionResult.model_validate_json(result.model_dump_json())
    assert restored.overall_status == "failed"
    assert restored.stages["build"].status == StageStatus.FAILED


# ---------------------------------------------------------------------------
# RecoveryPlan
# ---------------------------------------------------------------------------


def test_recovery_plan_fix_and_retry():
    plan = RecoveryPlan(
        strategy=RecoveryStrategy.FIX_AND_RETRY,
        reason="Missing module",
        modified_command="pip install requests && python app.py",
    )
    assert plan.strategy == RecoveryStrategy.FIX_AND_RETRY
    assert plan.modified_command is not None


def test_recovery_plan_abort_no_command():
    plan = RecoveryPlan(strategy=RecoveryStrategy.ABORT, reason="Unknown error")
    assert plan.modified_command is None
    assert plan.rollback_steps == []


# ---------------------------------------------------------------------------
# DeploymentVersion
# ---------------------------------------------------------------------------


def test_deployment_version_defaults():
    v = DeploymentVersion(
        pipeline_id="pipe-1",
        image="myapp:latest",
        environment="staging",
        status="success",
    )
    assert v.health_check_passed is False
    assert v.metadata == {}
    assert len(v.version_id) == 36


def test_deployment_version_json_roundtrip():
    v = DeploymentVersion(
        pipeline_id="pipe-1",
        image="myapp:v2",
        environment="production",
        status="success",
        health_check_passed=True,
        metadata={"deployment_id": "dep-123"},
    )
    restored = DeploymentVersion.model_validate_json(v.model_dump_json())
    assert restored.health_check_passed is True
    assert restored.metadata["deployment_id"] == "dep-123"
