"""Unit tests for DAGScheduler — dependency resolution, cycle detection, re-run logic."""
from __future__ import annotations

import pytest

from src.executor.scheduler import DAGScheduler
from src.models.messages import StageResult, StageStatus
from tests.conftest import make_pipeline_spec, make_stage


# ---------------------------------------------------------------------------
# Construction & validation
# ---------------------------------------------------------------------------


def test_scheduler_builds_from_valid_spec():
    spec = make_pipeline_spec(stages=[make_stage("build"), make_stage("test", depends_on=["build"])])
    sched = DAGScheduler(spec)
    assert set(sched._stages.keys()) == {"build", "test"}


def test_scheduler_raises_on_unknown_dependency():
    spec = make_pipeline_spec(stages=[make_stage("test", depends_on=["nonexistent"])])
    with pytest.raises(ValueError, match="unknown stage"):
        DAGScheduler(spec)


def test_scheduler_raises_on_cycle():
    stages = [
        make_stage("a", depends_on=["b"]),
        make_stage("b", depends_on=["a"]),
    ]
    spec = make_pipeline_spec(stages=stages)
    with pytest.raises(ValueError, match="cycle"):
        DAGScheduler(spec)


# ---------------------------------------------------------------------------
# get_ready_stages
# ---------------------------------------------------------------------------


def test_get_ready_stages_returns_root_stages():
    stages = [
        make_stage("build"),
        make_stage("test", depends_on=["build"]),
    ]
    sched = DAGScheduler(make_pipeline_spec(stages=stages))
    assert sched.get_ready_stages() == ["build"]


def test_get_ready_stages_after_dependency_completes():
    stages = [
        make_stage("build"),
        make_stage("test", depends_on=["build"]),
    ]
    sched = DAGScheduler(make_pipeline_spec(stages=stages))
    result = StageResult(stage_id="build", status=StageStatus.SUCCESS)
    sched.mark_complete("build", StageStatus.SUCCESS, result)
    assert sched.get_ready_stages() == ["test"]


def test_get_ready_stages_skipped_dependency_unblocks_downstream():
    """A SKIPPED predecessor should still unblock downstream stages."""
    stages = [
        make_stage("lint", critical=False),
        make_stage("build", depends_on=["lint"]),
    ]
    sched = DAGScheduler(make_pipeline_spec(stages=stages))
    skip_result = StageResult(stage_id="lint", status=StageStatus.SKIPPED)
    sched.mark_complete("lint", StageStatus.SKIPPED, skip_result)
    assert "build" in sched.get_ready_stages()


def test_get_ready_stages_parallel_roots():
    stages = [make_stage("a"), make_stage("b"), make_stage("c", depends_on=["a", "b"])]
    sched = DAGScheduler(make_pipeline_spec(stages=stages))
    ready = sched.get_ready_stages()
    assert set(ready) == {"a", "b"}


# ---------------------------------------------------------------------------
# mark_complete / mark_running / is_finished
# ---------------------------------------------------------------------------


def test_mark_running_changes_status():
    sched = DAGScheduler(make_pipeline_spec(stages=[make_stage("build")]))
    sched.mark_running("build")
    assert sched.get_status("build") == StageStatus.RUNNING


def test_is_finished_false_while_pending():
    sched = DAGScheduler(make_pipeline_spec(stages=[make_stage("build")]))
    assert not sched.is_finished()


def test_is_finished_true_when_all_complete():
    sched = DAGScheduler(make_pipeline_spec(stages=[make_stage("build")]))
    sched.mark_complete("build", StageStatus.SUCCESS, StageResult(stage_id="build", status=StageStatus.SUCCESS))
    assert sched.is_finished()


# ---------------------------------------------------------------------------
# skip_dependents
# ---------------------------------------------------------------------------


def test_skip_dependents_marks_downstream_skipped():
    stages = [
        make_stage("build"),
        make_stage("test", depends_on=["build"]),
        make_stage("deploy", depends_on=["test"]),
    ]
    sched = DAGScheduler(make_pipeline_spec(stages=stages))
    sched.skip_dependents("build")
    assert sched.get_status("test") == StageStatus.SKIPPED
    assert sched.get_status("deploy") == StageStatus.SKIPPED


def test_skip_dependents_does_not_affect_unrelated_stages():
    stages = [make_stage("a"), make_stage("b"), make_stage("c", depends_on=["a"])]
    sched = DAGScheduler(make_pipeline_spec(stages=stages))
    sched.skip_dependents("a")
    assert sched.get_status("b") == StageStatus.PENDING


# ---------------------------------------------------------------------------
# reset_failed_stages
# ---------------------------------------------------------------------------


def test_reset_failed_stages_resets_to_pending():
    stages = [make_stage("build"), make_stage("test", depends_on=["build"])]
    sched = DAGScheduler(make_pipeline_spec(stages=stages))
    fail_result = StageResult(stage_id="build", status=StageStatus.FAILED)
    sched.mark_complete("build", StageStatus.FAILED, fail_result)
    sched.skip_dependents("build")

    reset = sched.reset_failed_stages()
    assert "build" in reset
    assert sched.get_status("build") == StageStatus.PENDING


def test_reset_failed_stages_un_skips_downstream():
    stages = [make_stage("build"), make_stage("test", depends_on=["build"])]
    sched = DAGScheduler(make_pipeline_spec(stages=stages))
    fail_result = StageResult(stage_id="build", status=StageStatus.FAILED)
    sched.mark_complete("build", StageStatus.FAILED, fail_result)
    sched.skip_dependents("build")

    sched.reset_failed_stages()
    assert sched.get_status("test") == StageStatus.PENDING


def test_reset_failed_stages_returns_empty_when_no_failures():
    sched = DAGScheduler(make_pipeline_spec(stages=[make_stage("build")]))
    assert sched.reset_failed_stages() == []


def test_reset_does_not_un_skip_explicitly_skipped_non_critical():
    """Non-critical stages that were explicitly skipped should stay skipped."""
    stages = [make_stage("lint", critical=False), make_stage("build", depends_on=["lint"])]
    sched = DAGScheduler(make_pipeline_spec(stages=stages))
    skip_result = StageResult(stage_id="lint", status=StageStatus.SKIPPED)
    sched.mark_complete("lint", StageStatus.SKIPPED, skip_result)
    # build is still pending — mark it failed
    fail_result = StageResult(stage_id="build", status=StageStatus.FAILED)
    sched.mark_complete("build", StageStatus.FAILED, fail_result)

    sched.reset_failed_stages()
    # lint was explicitly completed as SKIPPED (has a result) — must stay SKIPPED
    assert sched.get_status("lint") == StageStatus.SKIPPED


# ---------------------------------------------------------------------------
# get_all_results
# ---------------------------------------------------------------------------


def test_get_all_results_returns_completed_stages():
    sched = DAGScheduler(make_pipeline_spec(stages=[make_stage("build")]))
    r = StageResult(stage_id="build", status=StageStatus.SUCCESS)
    sched.mark_complete("build", StageStatus.SUCCESS, r)
    results = sched.get_all_results()
    assert "build" in results
    assert results["build"].status == StageStatus.SUCCESS
