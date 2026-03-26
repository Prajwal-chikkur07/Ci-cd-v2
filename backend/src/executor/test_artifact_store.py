"""Unit tests for artifact storage."""

import pytest
import tempfile
import shutil
from pathlib import Path
from src.executor.artifact_store import ArtifactStore


class MockScheduler:
    """Mock scheduler for testing."""
    
    def __init__(self):
        self.graph = MockGraph()


class MockGraph:
    """Mock graph for testing."""
    
    def __init__(self):
        self._predecessors = {}
    
    def predecessors(self, node):
        return self._predecessors.get(node, [])
    
    def set_predecessors(self, node, preds):
        self._predecessors[node] = preds


@pytest.fixture
def artifact_store():
    """Create a temporary artifact store for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = ArtifactStore(base_path=tmpdir)
        yield store


@pytest.fixture
def test_file():
    """Create a temporary test file."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
        f.write("test content")
        path = f.name
    yield path
    Path(path).unlink()


@pytest.fixture
def test_directory():
    """Create a temporary test directory with files."""
    tmpdir = tempfile.mkdtemp()
    (Path(tmpdir) / "file1.txt").write_text("content1")
    (Path(tmpdir) / "file2.txt").write_text("content2")
    yield tmpdir
    shutil.rmtree(tmpdir)


class TestArtifactStoreSave:
    """Test artifact saving."""
    
    def test_save_artifact_file(self, artifact_store, test_file):
        """Test saving a single file artifact."""
        result = artifact_store.save_artifact(
            "pipeline1", "stage1", test_file
        )
        
        assert result is not None
        assert Path(result).exists()
        assert Path(result).read_text() == "test content"
    
    def test_save_artifact_directory(self, artifact_store, test_directory):
        """Test saving a directory artifact."""
        result = artifact_store.save_artifact(
            "pipeline1", "stage1", test_directory
        )
        
        assert result is not None
        assert Path(result).exists()
        assert Path(result).is_dir()
        assert (Path(result) / "file1.txt").exists()
    
    def test_save_artifact_with_custom_name(self, artifact_store, test_file):
        """Test saving artifact with custom name."""
        result = artifact_store.save_artifact(
            "pipeline1", "stage1", test_file, artifact_name="custom.txt"
        )
        
        assert result is not None
        assert "custom.txt" in result
        assert Path(result).exists()
    
    def test_save_nonexistent_artifact(self, artifact_store):
        """Test saving nonexistent artifact."""
        result = artifact_store.save_artifact(
            "pipeline1", "stage1", "/nonexistent/path"
        )
        
        assert result is None
    
    def test_save_multiple_artifacts(self, artifact_store, test_file):
        """Test saving multiple artifacts from same stage."""
        result1 = artifact_store.save_artifact(
            "pipeline1", "stage1", test_file, artifact_name="artifact1.txt"
        )
        result2 = artifact_store.save_artifact(
            "pipeline1", "stage1", test_file, artifact_name="artifact2.txt"
        )
        
        assert result1 is not None
        assert result2 is not None
        assert result1 != result2


class TestArtifactStoreRetrieval:
    """Test artifact retrieval."""
    
    def test_get_artifacts_empty(self, artifact_store):
        """Test getting artifacts when none exist."""
        result = artifact_store.get_artifacts("pipeline1", "stage1")
        
        assert result == []
    
    def test_get_artifacts_single(self, artifact_store, test_file):
        """Test getting single artifact."""
        artifact_store.save_artifact(
            "pipeline1", "stage1", test_file
        )
        
        result = artifact_store.get_artifacts("pipeline1", "stage1")
        
        assert len(result) == 1
        assert Path(result[0]).exists()
    
    def test_get_artifacts_multiple(self, artifact_store, test_file):
        """Test getting multiple artifacts."""
        artifact_store.save_artifact(
            "pipeline1", "stage1", test_file, artifact_name="artifact1.txt"
        )
        artifact_store.save_artifact(
            "pipeline1", "stage1", test_file, artifact_name="artifact2.txt"
        )
        
        result = artifact_store.get_artifacts("pipeline1", "stage1")
        
        assert len(result) == 2
    
    def test_get_upstream_artifacts(self, artifact_store, test_file):
        """Test getting upstream artifacts."""
        # Save artifacts from upstream stages
        artifact_store.save_artifact(
            "pipeline1", "stage1", test_file, artifact_name="build.tar"
        )
        artifact_store.save_artifact(
            "pipeline1", "stage2", test_file, artifact_name="test.log"
        )
        
        # Create mock scheduler
        scheduler = MockScheduler()
        scheduler.graph.set_predecessors("stage3", ["stage1", "stage2"])
        
        result = artifact_store.get_all_upstream_artifacts(
            "pipeline1", "stage3", scheduler
        )
        
        assert "stage1" in result
        assert "stage2" in result
        assert len(result["stage1"]) == 1
        assert len(result["stage2"]) == 1


class TestArtifactStoreCleanup:
    """Test artifact cleanup."""

    def test_cleanup_old_artifacts_none_old(self, artifact_store, test_file):
        """Test cleanup_old_artifacts returns 0 when no artifacts are old enough."""
        artifact_store.save_artifact("pipeline1", "stage1", test_file)
        # max_age_hours=0 means everything is "old", but freshly created files
        # have mtime == now, so with a very large threshold nothing is deleted
        count = artifact_store.cleanup_old_artifacts("pipeline1", max_age_hours=9999)
        assert count == 0

    def test_cleanup_old_artifacts_removes_old(self, artifact_store, test_file):
        """Test cleanup_old_artifacts removes artifacts older than threshold."""
        import os, time
        artifact_store.save_artifact("pipeline1", "stage1", test_file, artifact_name="old.txt")
        stage_dir = artifact_store.base_path / "pipeline1" / "stage1"
        old_artifact = stage_dir / "old.txt"
        # Back-date the file by 2 hours
        old_time = time.time() - 7200
        os.utime(old_artifact, (old_time, old_time))

        count = artifact_store.cleanup_old_artifacts("pipeline1", max_age_hours=1)
        assert count == 1
        assert not old_artifact.exists()

    def test_cleanup_old_artifacts_nonexistent_pipeline(self, artifact_store):
        """Test cleanup_old_artifacts returns 0 for nonexistent pipeline."""
        count = artifact_store.cleanup_old_artifacts("nonexistent", max_age_hours=24)
        assert count == 0

    def test_cleanup_pipeline_artifacts(self, artifact_store, test_file):
        """Test cleaning up all artifacts for a pipeline."""
        artifact_store.save_artifact(
            "pipeline1", "stage1", test_file
        )
        artifact_store.save_artifact(
            "pipeline1", "stage2", test_file
        )
        
        # Verify artifacts exist
        artifacts = artifact_store.get_artifacts("pipeline1", "stage1")
        assert len(artifacts) > 0
        
        # Cleanup
        result = artifact_store.cleanup_pipeline_artifacts("pipeline1")
        
        assert result is True
        artifacts = artifact_store.get_artifacts("pipeline1", "stage1")
        assert len(artifacts) == 0
    
    def test_cleanup_nonexistent_pipeline(self, artifact_store):
        """Test cleaning up nonexistent pipeline."""
        result = artifact_store.cleanup_pipeline_artifacts("nonexistent")
        
        assert result is True


class TestArtifactStoreSize:
    """Test artifact size calculation."""
    
    def test_get_artifact_size_empty(self, artifact_store):
        """Test getting size when no artifacts exist."""
        size = artifact_store.get_artifact_size("pipeline1", "stage1")
        
        assert size == 0
    
    def test_get_artifact_size_single_file(self, artifact_store, test_file):
        """Test getting size of single artifact."""
        artifact_store.save_artifact(
            "pipeline1", "stage1", test_file
        )
        
        size = artifact_store.get_artifact_size("pipeline1", "stage1")
        
        assert size > 0
        assert size == len("test content")
    
    def test_get_artifact_size_multiple_files(self, artifact_store, test_directory):
        """Test getting size of multiple artifacts."""
        artifact_store.save_artifact(
            "pipeline1", "stage1", test_directory
        )
        
        size = artifact_store.get_artifact_size("pipeline1", "stage1")
        
        assert size > 0
        # Should include both files
        assert size >= len("content1") + len("content2")
