"""Integration tests for Phase 2: Error Recovery & Artifact Passing."""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch

from src.executor.error_patterns import detect_error_pattern, apply_fix
from src.executor.artifact_store import ArtifactStore
from src.executor.replanner import analyze_failure
from src.models.messages import StageResult, StageStatus, RecoveryStrategy
from src.models.pipeline import Stage, AgentType, PipelineSpec


class TestErrorRecoveryIntegration:
    """Test error recovery with realistic scenarios."""
    
    @pytest.mark.asyncio
    async def test_missing_dependency_recovery(self):
        """Test recovery from missing Python dependency."""
        # Simulate a failed stage with missing dependency error
        result = StageResult(
            stage_id="build",
            status=StageStatus.FAILED,
            exit_code=1,
            stderr="ModuleNotFoundError: No module named 'requests'",
        )
        
        # Create a mock stage
        stage = Mock(spec=Stage)
        stage.id = "build"
        stage.command = "python app.py"
        stage.critical = True
        
        # Create a mock spec
        spec = Mock(spec=PipelineSpec)
        
        # Analyze failure
        plan = await analyze_failure(stage, result, spec)
        
        # Verify recovery plan
        assert plan.strategy == RecoveryStrategy.FIX_AND_RETRY
        assert "requests" in plan.reason
        assert "pip install requests" in plan.modified_command
    
    @pytest.mark.asyncio
    async def test_permission_denied_recovery(self):
        """Test recovery from permission denied error."""
        result = StageResult(
            stage_id="deploy",
            status=StageStatus.FAILED,
            exit_code=1,
            stderr="Permission denied: /app/script.sh",
        )
        
        stage = Mock(spec=Stage)
        stage.id = "deploy"
        stage.command = "./script.sh"
        stage.critical = True
        
        spec = Mock(spec=PipelineSpec)
        
        plan = await analyze_failure(stage, result, spec)
        
        assert plan.strategy == RecoveryStrategy.FIX_AND_RETRY
        assert "chmod" in plan.modified_command
    
    @pytest.mark.asyncio
    async def test_npm_ci_fallback_recovery(self):
        """Test recovery from npm ci failure."""
        result = StageResult(
            stage_id="build",
            status=StageStatus.FAILED,
            exit_code=1,
            stderr="npm ci ENOENT: no such file or directory",
        )
        
        stage = Mock(spec=Stage)
        stage.id = "build"
        stage.command = "npm ci && npm start"
        stage.critical = True
        
        spec = Mock(spec=PipelineSpec)
        
        plan = await analyze_failure(stage, result, spec)
        
        assert plan.strategy == RecoveryStrategy.FIX_AND_RETRY
        assert "npm install" in plan.modified_command
    
    @pytest.mark.asyncio
    async def test_flask_async_recovery(self):
        """Test recovery from Flask async extra missing."""
        result = StageResult(
            stage_id="build",
            status=StageStatus.FAILED,
            exit_code=1,
            stderr="RuntimeError: Install Flask with the 'async' extra",
        )
        
        stage = Mock(spec=Stage)
        stage.id = "build"
        stage.command = "python app.py"
        stage.critical = True
        
        spec = Mock(spec=PipelineSpec)
        
        plan = await analyze_failure(stage, result, spec)
        
        assert plan.strategy == RecoveryStrategy.FIX_AND_RETRY
        assert "flask[async]" in plan.modified_command


class TestArtifactPassingIntegration:
    """Test artifact passing between stages."""
    
    @pytest.mark.asyncio
    async def test_artifact_save_and_retrieve(self):
        """Test saving and retrieving artifacts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ArtifactStore(base_path=tmpdir)
            
            # Create a test artifact
            artifact_file = Path(tmpdir) / "test_artifact.txt"
            artifact_file.write_text("test content")
            
            # Save artifact
            saved_path = store.save_artifact(
                "pipeline1", "build", str(artifact_file)
            )
            
            assert saved_path is not None
            assert Path(saved_path).exists()
            
            # Retrieve artifact
            artifacts = store.get_artifacts("pipeline1", "build")
            
            assert len(artifacts) == 1
            assert Path(artifacts[0]).read_text() == "test content"
    
    @pytest.mark.asyncio
    async def test_upstream_artifacts_collection(self):
        """Test collecting artifacts from upstream stages."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ArtifactStore(base_path=tmpdir)
            
            # Create test artifacts
            build_artifact = Path(tmpdir) / "build_output.tar"
            build_artifact.write_text("build output")
            
            test_artifact = Path(tmpdir) / "test_results.log"
            test_artifact.write_text("test results")
            
            # Save artifacts from upstream stages
            store.save_artifact("pipeline1", "build", str(build_artifact))
            store.save_artifact("pipeline1", "test", str(test_artifact))
            
            # Create mock scheduler
            class MockGraph:
                def predecessors(self, node):
                    if node == "deploy":
                        return ["build", "test"]
                    return []
            
            class MockScheduler:
                def __init__(self):
                    self.graph = MockGraph()
            
            scheduler = MockScheduler()
            
            # Get upstream artifacts
            upstream = store.get_all_upstream_artifacts(
                "pipeline1", "deploy", scheduler
            )
            
            assert "build" in upstream
            assert "test" in upstream
            assert len(upstream["build"]) == 1
            assert len(upstream["test"]) == 1
    
    @pytest.mark.asyncio
    async def test_artifact_cleanup(self):
        """Test artifact cleanup."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ArtifactStore(base_path=tmpdir)
            
            # Create and save artifacts
            artifact_file = Path(tmpdir) / "artifact.txt"
            artifact_file.write_text("content")
            
            store.save_artifact("pipeline1", "build", str(artifact_file))
            
            # Verify artifact exists
            artifacts = store.get_artifacts("pipeline1", "build")
            assert len(artifacts) == 1
            
            # Cleanup
            result = store.cleanup_pipeline_artifacts("pipeline1")
            
            assert result is True
            artifacts = store.get_artifacts("pipeline1", "build")
            assert len(artifacts) == 0
    
    @pytest.mark.asyncio
    async def test_artifact_size_calculation(self):
        """Test artifact size calculation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ArtifactStore(base_path=tmpdir)
            
            # Create test artifact
            artifact_file = Path(tmpdir) / "artifact.txt"
            content = "test content"
            artifact_file.write_text(content)
            
            # Save artifact
            store.save_artifact("pipeline1", "build", str(artifact_file))
            
            # Get size
            size = store.get_artifact_size("pipeline1", "build")
            
            assert size == len(content)


class TestErrorPatternDetection:
    """Test error pattern detection with various error messages."""
    
    @pytest.mark.asyncio
    async def test_detect_multiple_error_types(self):
        """Test detecting different error types."""
        test_cases = [
            ("ModuleNotFoundError: No module named 'numpy'", "missing_dependency"),
            ("Permission denied: /app/file", "permission_denied"),
            ("Address already in use: 0.0.0.0:3000", "port_in_use"),
            ("ERROR: Flask app entry point not found", "wrong_entry_point"),
            ("npm ci ENOENT: no such file", "npm_ci_fallback"),
            ("linker `cc` not found", "linker_not_found"),
            ("RuntimeError: Install Flask with the 'async' extra", "flask_async_missing"),
        ]
        
        for error_msg, expected_pattern in test_cases:
            pattern_name, info = await detect_error_pattern(error_msg, "")
            assert pattern_name == expected_pattern, f"Failed for: {error_msg}"
    
    @pytest.mark.asyncio
    async def test_fix_application_for_patterns(self):
        """Test applying fixes for detected patterns."""
        test_cases = [
            ("install_dependency", "python app.py", {"package": "requests"}, "pip install requests"),
            ("fix_permissions", "./script.sh", {}, "chmod -R 755"),
            ("npm_install_fallback", "npm ci && npm start", {}, "npm install"),
            ("install_flask_async", "python app.py", {}, "flask[async]"),
        ]
        
        for fix_type, command, info, expected_substring in test_cases:
            fixed = await apply_fix(fix_type, command, info)
            assert fixed is not None
            assert expected_substring in fixed, f"Failed for fix_type: {fix_type}"


class TestRecoveryPlanGeneration:
    """Test recovery plan generation for various scenarios."""
    
    @pytest.mark.asyncio
    async def test_recovery_plan_for_missing_module(self):
        """Test recovery plan generation for missing module."""
        result = StageResult(
            stage_id="build",
            status=StageStatus.FAILED,
            exit_code=1,
            stderr="ModuleNotFoundError: No module named 'flask'",
        )
        
        stage = Mock(spec=Stage)
        stage.id = "build"
        stage.command = "python -m pip install -r requirements.txt && python app.py"
        stage.critical = True
        
        spec = Mock(spec=PipelineSpec)
        
        plan = await analyze_failure(stage, result, spec)
        
        assert plan.strategy == RecoveryStrategy.FIX_AND_RETRY
        assert plan.modified_command is not None
        assert "flask" in plan.modified_command.lower()
    
    @pytest.mark.asyncio
    async def test_recovery_plan_for_non_critical_failure(self):
        """Test recovery plan for non-critical stage failure."""
        result = StageResult(
            stage_id="lint",
            status=StageStatus.FAILED,
            exit_code=1,
            stderr="Linting failed",
        )
        
        stage = Mock(spec=Stage)
        stage.id = "lint"
        stage.command = "pylint app.py"
        stage.critical = False  # Non-critical
        
        spec = Mock(spec=PipelineSpec)
        
        plan = await analyze_failure(stage, result, spec)
        
        assert plan.strategy == RecoveryStrategy.SKIP_STAGE
