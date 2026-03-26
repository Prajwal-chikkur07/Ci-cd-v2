"""Integration tests for WebSocket real-time updates.

These tests verify that the WebSocket endpoint broadcasts the correct events
during pipeline execution. They use the ConnectionManager directly to avoid
the complexity of a real WebSocket upgrade in the test environment.
"""
from __future__ import annotations

import asyncio
import json
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from unittest.mock import AsyncMock, patch

from src.api.main import app
from src.api.websocket import manager
from src.db.models import Base
from tests.conftest import make_pipeline_spec, make_stage

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(autouse=True)
async def _patch_db(monkeypatch):
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    import src.db.repository as repo_module
    monkeypatch.setattr(repo_module, "async_session", factory)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


# ---------------------------------------------------------------------------
# ConnectionManager unit tests (no real WebSocket needed)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_connection_manager_broadcast_sends_to_all_connections():
    """ConnectionManager.broadcast should send JSON to all connected clients."""
    from src.api.websocket import ConnectionManager

    mgr = ConnectionManager()
    pipeline_id = "test-pipe"

    # Create mock WebSocket objects
    ws1 = AsyncMock()
    ws2 = AsyncMock()

    await mgr.connect(ws1, pipeline_id)
    await mgr.connect(ws2, pipeline_id)

    await mgr.broadcast(pipeline_id, {"log_type": "stage_start", "stage_id": "build"})

    ws1.send_text.assert_called_once()
    ws2.send_text.assert_called_once()

    # Verify the message is valid JSON
    sent = json.loads(ws1.send_text.call_args[0][0])
    assert sent["log_type"] == "stage_start"
    assert sent["stage_id"] == "build"


@pytest.mark.asyncio
async def test_connection_manager_disconnect_removes_client():
    """After disconnect, client should not receive further broadcasts."""
    from src.api.websocket import ConnectionManager

    mgr = ConnectionManager()
    pipeline_id = "test-pipe"

    ws = AsyncMock()
    await mgr.connect(ws, pipeline_id)
    mgr.disconnect(ws, pipeline_id)

    await mgr.broadcast(pipeline_id, {"log_type": "info"})

    ws.send_text.assert_not_called()


@pytest.mark.asyncio
async def test_connection_manager_broadcast_different_pipelines():
    """Broadcast to pipeline A should not reach pipeline B clients."""
    from src.api.websocket import ConnectionManager

    mgr = ConnectionManager()

    ws_a = AsyncMock()
    ws_b = AsyncMock()

    await mgr.connect(ws_a, "pipeline-a")
    await mgr.connect(ws_b, "pipeline-b")

    await mgr.broadcast("pipeline-a", {"log_type": "stage_start"})

    ws_a.send_text.assert_called_once()
    ws_b.send_text.assert_not_called()


@pytest.mark.asyncio
async def test_connection_manager_handles_dead_connection_gracefully():
    """If a WebSocket send fails, the manager should not crash."""
    from src.api.websocket import ConnectionManager

    mgr = ConnectionManager()
    pipeline_id = "test-pipe"

    ws = AsyncMock()
    ws.send_text.side_effect = Exception("Connection closed")

    await mgr.connect(ws, pipeline_id)

    # Should not raise
    await mgr.broadcast(pipeline_id, {"log_type": "info"})


# ---------------------------------------------------------------------------
# Pipeline execution broadcasts correct events (via on_update callback)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pipeline_execution_broadcasts_start_and_done(client):
    """Executing a pipeline should broadcast pipeline_start and pipeline_done events."""
    from src.db import repository as db

    spec = make_pipeline_spec(stages=[make_stage("build", command="echo hello")])
    spec.work_dir = "/tmp"
    await db.save_pipeline(spec)

    broadcast_calls: list[dict] = []

    original_broadcast = manager.broadcast

    async def capture_broadcast(pipeline_id: str, data: dict) -> None:
        broadcast_calls.append(data)
        await original_broadcast(pipeline_id, data)

    with patch.object(manager, "broadcast", side_effect=capture_broadcast):
        resp = await client.post(f"/pipelines/{spec.pipeline_id}/execute")

    assert resp.status_code == 200
    log_types = [c.get("log_type") for c in broadcast_calls]
    assert "pipeline_start" in log_types
    assert "pipeline_done" in log_types
    assert "stage_start" in log_types
    assert "stage_success" in log_types


@pytest.mark.asyncio
async def test_pipeline_execution_broadcasts_stdout_lines(client):
    """Live stdout lines should be broadcast as stage_output events."""
    from src.db import repository as db

    spec = make_pipeline_spec(stages=[make_stage("build", command="echo hello_world_test")])
    spec.work_dir = "/tmp"
    await db.save_pipeline(spec)

    output_events: list[dict] = []
    original_broadcast = manager.broadcast

    async def capture_broadcast(pipeline_id: str, data: dict) -> None:
        if data.get("log_type") == "stage_output":
            output_events.append(data)
        await original_broadcast(pipeline_id, data)

    with patch.object(manager, "broadcast", side_effect=capture_broadcast):
        await client.post(f"/pipelines/{spec.pipeline_id}/execute")

    assert any("hello_world_test" in e.get("log_message", "") for e in output_events)


@pytest.mark.asyncio
async def test_pipeline_execution_broadcasts_recovery_on_failure(client):
    """When a stage fails, recovery_start and recovery_plan events should be broadcast."""
    from src.db import repository as db

    spec = make_pipeline_spec(
        stages=[make_stage("build", command="python3 -c 'import nonexistent_xyz_module'")]
    )
    spec.work_dir = "/tmp"
    await db.save_pipeline(spec)

    recovery_events: list[dict] = []
    original_broadcast = manager.broadcast

    async def capture_broadcast(pipeline_id: str, data: dict) -> None:
        if data.get("log_type") in ("recovery_start", "recovery_plan"):
            recovery_events.append(data)
        await original_broadcast(pipeline_id, data)

    with patch.object(manager, "broadcast", side_effect=capture_broadcast):
        await client.post(f"/pipelines/{spec.pipeline_id}/execute")

    assert len(recovery_events) > 0


@pytest.mark.asyncio
async def test_pipeline_execution_broadcasts_stage_failed_on_critical_failure(client):
    """A critical stage failure should broadcast stage_failed event."""
    from src.db import repository as db

    spec = make_pipeline_spec(stages=[make_stage("build", command="exit 1")])
    spec.work_dir = "/tmp"
    await db.save_pipeline(spec)

    failed_events: list[dict] = []
    original_broadcast = manager.broadcast

    async def capture_broadcast(pipeline_id: str, data: dict) -> None:
        if data.get("log_type") in ("stage_failed", "recovery_failed"):
            failed_events.append(data)
        await original_broadcast(pipeline_id, data)

    with patch.object(manager, "broadcast", side_effect=capture_broadcast):
        await client.post(f"/pipelines/{spec.pipeline_id}/execute")

    assert len(failed_events) > 0
