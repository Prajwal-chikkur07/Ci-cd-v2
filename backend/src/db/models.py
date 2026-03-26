import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class PipelineRow(Base):
    __tablename__ = "pipelines"

    pipeline_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False, default="")
    repo_url = Column(String, nullable=False, default="")
    goal = Column(String, nullable=False, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    work_dir = Column(String, default="")
    # Store full PipelineSpec as JSON (analysis + stages)
    spec_json = Column(Text, nullable=False)
    
    # Tracking results
    overall_status = Column(String, default="not_executed")
    goal_achieved = Column(Text, default="false") # Store as string "true"/"false" for simplicity in SQLite if needed, or Boolean
    execution_duration = Column(String, default="0.0")

    results = relationship("StageResultRow", back_populates="pipeline", cascade="all, delete-orphan")


class StageResultRow(Base):
    __tablename__ = "stage_results"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    pipeline_id = Column(String, ForeignKey("pipelines.pipeline_id"), nullable=False)
    stage_id = Column(String, nullable=False)
    status = Column(String, nullable=False)
    exit_code = Column(String, default="-1")
    stdout = Column(Text, default="")
    stderr = Column(Text, default="")
    duration_seconds = Column(String, default="0.0")
    result_json = Column(Text, nullable=False)

    pipeline = relationship("PipelineRow", back_populates="results")



class DeploymentVersionRow(Base):
    __tablename__ = "deployment_versions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    version_id = Column(String, nullable=False)
    pipeline_id = Column(String, ForeignKey("pipelines.pipeline_id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    image = Column(String, nullable=False)
    environment = Column(String, nullable=False)
    status = Column(String, nullable=False)
    health_check_passed = Column(String, default="false")  # Store as string for SQLite
    deployment_metadata = Column(Text, default="{}")  # Store as JSON string (renamed from metadata to avoid SQLAlchemy conflict)

    pipeline = relationship("PipelineRow", foreign_keys=[pipeline_id])
