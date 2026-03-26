"""
Shared pytest fixtures and Hypothesis profiles for the backend test suite.
"""
from __future__ import annotations

import pytest
import pytest_asyncio
from hypothesis import HealthCheck, settings
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.db.models import Base
from src.models.pipeline import AgentType, PipelineSpec, RepoAnalysis, Stage

# ---------------------------------------------------------------------------
# Hypothesis profiles
# ---------------------------------------------------------------------------

settings.register_profile("ci", max_examples=100, suppress_health_check=[HealthCheck.too_slow])
settings.register_profile("dev", max_examples=20, suppress_health_check=[HealthCheck.too_slow])
settings.load_profile("ci")

# ---------------------------------------------------------------------------
# Async SQLite in-memory fixtures
# ---------------------------------------------------------------------------

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="function")
async def async_engine():
    """Create a fresh in-memory SQLite engine for each test."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def async_session(async_engine):
    """Provide an AsyncSession bound to the in-memory engine."""
    session_factory = async_sessionmaker(
        async_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture(scope="function")
async def init_test_db(async_engine):
    """Create all ORM tables in the in-memory database."""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


# ---------------------------------------------------------------------------
# Model factories
# ---------------------------------------------------------------------------


def make_stage(
    stage_id: str = "stage-build",
    agent: AgentType = AgentType.BUILD,
    command: str = "echo build",
    depends_on: list[str] | None = None,
    timeout_seconds: int = 300,
    retry_count: int = 0,
    critical: bool = True,
    env_vars: dict[str, str] | None = None,
) -> Stage:
    """Return a Stage with sensible defaults, overridable per-test."""
    return Stage(
        id=stage_id,
        agent=agent,
        command=command,
        depends_on=depends_on or [],
        timeout_seconds=timeout_seconds,
        retry_count=retry_count,
        critical=critical,
        env_vars=env_vars or {},
    )


def make_pipeline_spec(
    name: str = "test-pipeline",
    repo_url: str = "https://github.com/example/repo",
    goal: str = "deploy to staging",
    language: str = "python",
    stages: list[Stage] | None = None,
    use_docker: bool = False,
) -> PipelineSpec:
    """Return a PipelineSpec with sensible defaults, overridable per-test."""
    if stages is None:
        stages = [make_stage()]

    analysis = RepoAnalysis(
        language=language,
        framework=None,
        package_manager="pip",
        has_dockerfile=use_docker,
        has_requirements_txt=True,
        has_tests=True,
        test_runner="pytest",
    )

    return PipelineSpec(
        name=name,
        repo_url=repo_url,
        goal=goal,
        analysis=analysis,
        stages=stages,
        use_docker=use_docker,
    )
