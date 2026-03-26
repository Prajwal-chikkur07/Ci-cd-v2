"""Artifact storage and retrieval for inter-stage communication."""

import logging
import shutil
from pathlib import Path
from typing import Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class ArtifactStore:
    """Manages artifact storage and retrieval between pipeline stages."""
    
    def __init__(self, base_path: str = "/tmp/artifacts"):
        """Initialize artifact store with base path."""
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Artifact store initialized at {self.base_path}")
    
    def save_artifact(
        self, 
        pipeline_id: str, 
        stage_id: str, 
        artifact_path: str,
        artifact_name: Optional[str] = None
    ) -> str:
        """
        Save artifact from stage execution.
        
        Args:
            pipeline_id: ID of the pipeline
            stage_id: ID of the stage that produced the artifact
            artifact_path: Path to the artifact file/directory
            artifact_name: Optional custom name for the artifact
        
        Returns:
            Path where artifact was stored
        """
        try:
            source = Path(artifact_path)
            if not source.exists():
                logger.warning(f"Artifact source does not exist: {artifact_path}")
                return None
            
            # Create destination directory
            dest_dir = self.base_path / pipeline_id / stage_id
            dest_dir.mkdir(parents=True, exist_ok=True)
            
            # Use custom name or source name
            dest_name = artifact_name or source.name
            dest = dest_dir / dest_name
            
            # Copy artifact
            if source.is_dir():
                if dest.exists():
                    shutil.rmtree(dest)
                shutil.copytree(source, dest)
            else:
                shutil.copy2(source, dest)
            
            logger.info(f"Saved artifact: {artifact_path} -> {dest}")
            return str(dest)
        except Exception as e:
            logger.error(f"Failed to save artifact {artifact_path}: {e}")
            return None
    
    def get_artifacts(self, pipeline_id: str, stage_id: str) -> list[str]:
        """
        Get all artifacts from a specific stage.
        
        Args:
            pipeline_id: ID of the pipeline
            stage_id: ID of the stage
        
        Returns:
            List of artifact paths
        """
        try:
            stage_dir = self.base_path / pipeline_id / stage_id
            if not stage_dir.exists():
                return []
            
            artifacts = []
            for item in stage_dir.iterdir():
                artifacts.append(str(item))
            
            logger.info(f"Retrieved {len(artifacts)} artifacts from {stage_id}")
            return artifacts
        except Exception as e:
            logger.error(f"Failed to get artifacts for {stage_id}: {e}")
            return []
    
    def get_all_upstream_artifacts(
        self, 
        pipeline_id: str, 
        stage_id: str, 
        scheduler
    ) -> dict[str, list[str]]:
        """
        Get all artifacts from upstream stages.
        
        Args:
            pipeline_id: ID of the pipeline
            stage_id: ID of the current stage
            scheduler: DAGScheduler instance to get predecessors
        
        Returns:
            Dictionary mapping predecessor stage IDs to their artifacts
        """
        try:
            artifacts = {}
            predecessors = list(scheduler.graph.predecessors(stage_id))
            
            for pred_id in predecessors:
                pred_artifacts = self.get_artifacts(pipeline_id, pred_id)
                if pred_artifacts:
                    artifacts[pred_id] = pred_artifacts
            
            logger.info(f"Retrieved artifacts from {len(artifacts)} upstream stages")
            return artifacts
        except Exception as e:
            logger.error(f"Failed to get upstream artifacts for {stage_id}: {e}")
            return {}
    
    def cleanup_old_artifacts(
        self, 
        pipeline_id: str, 
        max_age_hours: int = 24
    ) -> int:
        """
        Clean up old artifacts to prevent disk bloat.
        
        Args:
            pipeline_id: ID of the pipeline
            max_age_hours: Maximum age of artifacts in hours
        
        Returns:
            Number of artifacts deleted
        """
        try:
            pipeline_dir = self.base_path / pipeline_id
            if not pipeline_dir.exists():
                return 0
            
            cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
            deleted_count = 0
            
            for stage_dir in pipeline_dir.iterdir():
                if not stage_dir.is_dir():
                    continue
                
                for artifact in stage_dir.iterdir():
                    # Get modification time
                    mtime = datetime.fromtimestamp(artifact.stat().st_mtime)
                    
                    if mtime < cutoff_time:
                        try:
                            if artifact.is_dir():
                                shutil.rmtree(artifact)
                            else:
                                artifact.unlink()
                            deleted_count += 1
                            logger.info(f"Deleted old artifact: {artifact}")
                        except Exception as e:
                            logger.error(f"Failed to delete artifact {artifact}: {e}")
            
            logger.info(f"Cleaned up {deleted_count} old artifacts for pipeline {pipeline_id}")
            return deleted_count
        except Exception as e:
            logger.error(f"Failed to cleanup artifacts for {pipeline_id}: {e}")
            return 0
    
    def cleanup_pipeline_artifacts(self, pipeline_id: str) -> bool:
        """
        Clean up all artifacts for a pipeline.
        
        Args:
            pipeline_id: ID of the pipeline
        
        Returns:
            True if successful, False otherwise
        """
        try:
            pipeline_dir = self.base_path / pipeline_id
            if pipeline_dir.exists():
                shutil.rmtree(pipeline_dir)
                logger.info(f"Cleaned up all artifacts for pipeline {pipeline_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to cleanup pipeline artifacts {pipeline_id}: {e}")
            return False
    
    def get_artifact_size(self, pipeline_id: str, stage_id: str) -> int:
        """
        Get total size of artifacts from a stage in bytes.
        
        Args:
            pipeline_id: ID of the pipeline
            stage_id: ID of the stage
        
        Returns:
            Total size in bytes
        """
        try:
            stage_dir = self.base_path / pipeline_id / stage_id
            if not stage_dir.exists():
                return 0
            
            total_size = 0
            for item in stage_dir.rglob("*"):
                if item.is_file():
                    total_size += item.stat().st_size
            
            return total_size
        except Exception as e:
            logger.error(f"Failed to get artifact size for {stage_id}: {e}")
            return 0
