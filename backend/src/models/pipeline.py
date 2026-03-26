import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class AgentType(str, Enum):
    BUILD = "build"
    TEST = "test"
    SECURITY = "security"
    DEPLOY = "deploy"
    VERIFY = "verify"


class Stage(BaseModel):
    id: str
    agent: AgentType
    command: str

    @field_validator("id")
    @classmethod
    def id_must_not_be_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Stage id must not be empty")
        return v
    depends_on: list[str] = []
    timeout_seconds: int = 300
    retry_count: int = 0
    critical: bool = True
    env_vars: dict[str, str] = {}


class RepoAnalysis(BaseModel):
    language: str
    framework: Optional[str] = None
    package_manager: str
    has_dockerfile: bool = False
    has_requirements_txt: bool = False
    has_yarn_lock: bool = False
    has_package_lock: bool = False
    has_tests: bool = False
    test_runner: Optional[str] = None
    is_monorepo: bool = False
    deploy_target: Optional[str] = None
    available_scripts: list[str] = []
    has_test_extras: bool = False
    project_subdir: Optional[str] = None  # subdirectory containing the project root
    is_flask_app: bool = True  # True if Flask framework with actual app, False if library


class PipelineSpec(BaseModel):
    pipeline_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    repo_url: str = ""
    goal: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    analysis: RepoAnalysis
    stages: list[Stage]
    work_dir: str = ""
    use_docker: bool = False



class DeploymentVersion(BaseModel):
    """Track deployment versions for rollback capability."""
    
    version_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    pipeline_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    image: str  # Docker image or artifact
    environment: str  # staging, production, dev
    status: str  # success, failed, rolled_back
    health_check_passed: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)
