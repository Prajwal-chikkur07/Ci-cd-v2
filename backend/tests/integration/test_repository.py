"""Integration tests for the database repository layer using in-memory SQLite."""
from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.db.models import Base
from src.db import repository as repo
from src.db.session import async_session as _real_session
from src.models.messages import PipelineExecutionResult, StageResult, StageStatus
from src.models.pipeline import DeploymentVersion
from tests.conftest import make_pipeline_spec, make_stage

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(autouse=True)
async def _patch_session(monkeypatch):
    """Replace the real DB session with an in-memory SQLite session for each test."""
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Patch the async_session used directly inside repository.py
    import src.db.repository as repo_module
    monkeypatch.setattr(repo_module, "async_session", factory)

    yield

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


# ---------------------------------------------------------------------------
# Pipeline CRUD
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_save_and_get_pipeline():
    spec = make_pipeline_spec(name="my-pipeline")
    await repo.save_pipeline(spec)
    loaded = await repo.get_pipeline(spec.pipeline_id)
    assert loaded is not None
    assert loaded.pipeline_id == spec.pipeline_id
    assert loaded.name == "my-pipeline"


@pytest.mark.asyncio
async def test_get_pipeline_returns_none_for_unknown_id():
    result = await repo.get_pipeline("nonexistent-id")
    assert result is None


@pytest.mark.asyncio
async def test_list_pipelines_returns_all():
    spec1 = make_pipeline_spec(name="pipe-1")
    spec2 = make_pipeline_spec(name="pipe-2")
    await repo.save_pipeline(spec1)
    await repo.save_pipeline(spec2)
    pipelines = await repo.list_pipelines()
    ids = [p.pipeline_id for p in pipelines]
    assert spec1.pipeline_id in ids
    assert spec2.pipeline_id in ids


@pytest.mark.asyncio
async def test_list_pipelines_empty():
    pipelines = await repo.list_pipelines()
    assert pipelines == []


@pytest.mark.asyncio
async def test_update_pipeline():
    spec = make_pipeline_spec(name="original")
    await repo.save_pipeline(spec)
    spec.name = "updated"
    spec.goal = "new goal"
    success = await repo.update_pipeline(spec)
    assert success is True
    loaded = await repo.get_pipeline(spec.pipeline_id)
    assert loaded.name == "updated"
    assert loaded.goal == "new goal"


@pytest.mark.asyncio
async def test_update_pipeline_returns_false_for_unknown():
    spec = make_pipeline_spec()
    result = await repo.update_pipeline(spec)
    assert result is False


@pytest.mark.asyncio
async def test_delete_pipeline():
    spec = make_pipeline_spec()
    await repo.save_pipeline(spec)
    deleted = await repo.delete_pipeline(spec.pipeline_id)
    assert deleted is True
    assert await repo.get_pipeline(spec.pipeline_id) is None


@pytest.mark.asyncio
async def test_delete_pipeline_returns_false_for_unknown():
    result = await repo.delete_pipeline("nonexistent")
    assert result is False


# ---------------------------------------------------------------------------
# Execution results
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_save_and_get_results():
    spec = make_pipeline_spec()
    await repo.save_pipeline(spec)

    exec_result = PipelineExecutionResult(
        pipeline_id=spec.pipeline_id,
        overall_status="success",
        goal_achieved=True,
        stages={
            "build": StageResult(
                stage_id="build",
                status=StageStatus.SUCCESS,
                exit_code=0,
                stdout="Build OK",
                duration_seconds=2.5,
            )
        },
        duration_seconds=2.5,
    )
    await repo.save_results(spec.pipeline_id, exec_result)

    loaded = await repo.get_results(spec.pipeline_id)
    assert loaded is not None
    assert loaded.overall_status == "success"
    assert loaded.goal_achieved is True
    assert "build" in loaded.stages
    assert loaded.stages["build"].status == StageStatus.SUCCESS


@pytest.mark.asyncio
async def test_get_results_returns_none_when_no_results():
    spec = make_pipeline_spec()
    await repo.save_pipeline(spec)
    result = await repo.get_results(spec.pipeline_id)
    assert result is None


@pytest.mark.asyncio
async def test_save_results_overwrites_previous():
    spec = make_pipeline_spec()
    await repo.save_pipeline(spec)

    first = PipelineExecutionResult(
        pipeline_id=spec.pipeline_id,
        overall_status="failed",
        goal_achieved=False,
        stages={"build": StageResult(stage_id="build", status=StageStatus.FAILED)},
    )
    await repo.save_results(spec.pipeline_id, first)

    second = PipelineExecutionResult(
        pipeline_id=spec.pipeline_id,
        overall_status="success",
        goal_achieved=True,
        stages={"build": StageResult(stage_id="build", status=StageStatus.SUCCESS)},
    )
    await repo.save_results(spec.pipeline_id, second)

    loaded = await repo.get_results(spec.pipeline_id)
    assert loaded.overall_status == "success"
    assert loaded.stages["build"].status == StageStatus.SUCCESS


@pytest.mark.asyncio
async def test_results_preserve_deploy_url_in_metadata():
    spec = make_pipeline_spec()
    await repo.save_pipeline(spec)

    stage_result = StageResult(
        stage_id="deploy",
        status=StageStatus.SUCCESS,
        metadata={"deploy_url": "http://localhost:8080"},
    )
    exec_result = PipelineExecutionResult(
        pipeline_id=spec.pipeline_id,
        overall_status="success",
        goal_achieved=True,
        stages={"deploy": stage_result},
    )
    await repo.save_results(spec.pipeline_id, exec_result)

    loaded = await repo.get_results(spec.pipeline_id)
    assert loaded.final_output.get("app_url") == "http://localhost:8080"


# ---------------------------------------------------------------------------
# Deployment versions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_save_and_get_deployment_version():
    spec = make_pipeline_spec()
    await repo.save_pipeline(spec)

    version = DeploymentVersion(
        pipeline_id=spec.pipeline_id,
        image="myapp:v1",
        environment="staging",
        status="success",
        health_check_passed=True,
        metadata={"deployment_id": "dep-001"},
    )
    await repo.save_deployment_version(version)

    loaded = await repo.get_deployment_version(version.version_id)
    assert loaded is not None
    assert loaded.image == "myapp:v1"
    assert loaded.health_check_passed is True
    assert loaded.metadata["deployment_id"] == "dep-001"


@pytest.mark.asyncio
async def test_get_previous_deployment_version():
    spec = make_pipeline_spec()
    await repo.save_pipeline(spec)

    v1 = DeploymentVersion(
        pipeline_id=spec.pipeline_id,
        image="myapp:v1",
        environment="staging",
        status="success",
    )
    v2 = DeploymentVersion(
        pipeline_id=spec.pipeline_id,
        image="myapp:v2",
        environment="staging",
        status="success",
    )
    await repo.save_deployment_version(v1)
    await repo.save_deployment_version(v2)

    prev = await repo.get_previous_deployment_version(spec.pipeline_id)
    assert prev is not None
    # Should return the most recent successful version
    assert prev.image in ("myapp:v1", "myapp:v2")


@pytest.mark.asyncio
async def test_get_deployment_history():
    spec = make_pipeline_spec()
    await repo.save_pipeline(spec)

    for i in range(3):
        v = DeploymentVersion(
            pipeline_id=spec.pipeline_id,
            image=f"myapp:v{i}",
            environment="staging",
            status="success",
        )
        await repo.save_deployment_version(v)

    history = await repo.get_deployment_history(spec.pipeline_id, limit=10)
    assert len(history) == 3


@pytest.mark.asyncio
async def test_update_deployment_version_status():
    spec = make_pipeline_spec()
    await repo.save_pipeline(spec)

    version = DeploymentVersion(
        pipeline_id=spec.pipeline_id,
        image="myapp:v1",
        environment="staging",
        status="success",
    )
    await repo.save_deployment_version(version)

    success = await repo.update_deployment_version_status(version.version_id, "rolled_back")
    assert success is True

    loaded = await repo.get_deployment_version(version.version_id)
    assert loaded.status == "rolled_back"
