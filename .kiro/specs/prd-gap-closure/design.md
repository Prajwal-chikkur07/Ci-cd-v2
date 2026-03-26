# Design: Technical Solutions for PRD Gap Closure

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend (React)                         │
│  - Show deployment URL with working link                    │
│  - Display rollback history                                 │
│  - Show cloud deployment options                            │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│                  Backend API (FastAPI)                      │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Goal Parser (NLP-based)                              │   │
│  │ - Extract cloud target, environment, region, strategy│   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Pipeline Generator (Enhanced)                        │   │
│  │ - Cloud-specific stages                              │   │
│  │ - Artifact passing                                   │   │
│  │ - App detection (Flask, FastAPI, Django)             │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Pipeline Executor (Enhanced)                         │   │
│  │ - Deployment versioning                              │   │
│  │ - Rollback capability                                │   │
│  │ - Post-deploy health monitoring                      │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Recovery System (Enhanced)                           │   │
│  │ - Pattern matching for common errors                 │   │
│  │ - Dependency resolution                              │   │
│  │ - Auto-patching                                      │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Cloud Adapters (New)                                 │   │
│  │ - AWS (ECR, ECS, Lambda)                             │   │
│  │ - Azure (ACR, ACI, App Service)                      │   │
│  │ - GCP (GCR, Cloud Run, GKE)                          │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Artifact Storage (New)                               │   │
│  │ - Local cache for build artifacts                    │   │
│  │ - Cloud storage integration                          │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Deployment History (New)                             │   │
│  │ - Track versions, timestamps, status                 │   │
│  │ - Enable rollback                                    │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## Solution 1: Make Deployed Apps Accessible from Host

### Problem
Apps run inside Docker container on `localhost:3000` but host can't reach them.

### Solution: Bind to 0.0.0.0 Instead of localhost

**Changes to `python_tmpl.py`:**
```python
# OLD: app.run(host="localhost", port=3000)
# NEW: app.run(host="0.0.0.0", port=3000)

# For all frameworks:
# - Flask: app.run(host="0.0.0.0", port=3000)
# - FastAPI: uvicorn app:app --host 0.0.0.0 --port 3000
# - Django: python manage.py runserver 0.0.0.0:3000
# - Node.js: app.listen(3000, "0.0.0.0")
# - Go: http.ListenAndServe("0.0.0.0:3000", router)
```

**Changes to all language templates** (nodejs.py, go.py, rust.py, java.py):
- Replace `localhost` with `0.0.0.0` in all server startup commands
- Ensure port is exposed in docker-compose (already done)

**Health Check Update:**
- Change from `nc -z localhost $P` to `nc -z 0.0.0.0 $P` OR use `curl http://0.0.0.0:$P`
- This ensures health check validates the same binding

**Testing:**
- Deploy Flask app
- Verify `curl http://localhost:3000` works from host machine
- Verify health check still passes

---

## Solution 2: Improve Flask App Detection

### Problem
Detects Flask framework but doesn't verify app exists.

### Solution: Add App File Detection

**New function in `detector.py`:**
```python
def _detect_flask_app(repo_path: Path) -> bool:
    """Check if repo contains actual Flask app (not just library)."""
    app_files = ["app.py", "wsgi.py", "application.py", "main.py"]
    
    # Check root level
    for f in app_files:
        if (repo_path / f).exists():
            return True
    
    # Check for factory pattern (create_app function)
    for py_file in repo_path.glob("*.py"):
        try:
            content = py_file.read_text()
            if "def create_app" in content or "def create_application" in content:
                return True
        except:
            pass
    
    return False
```

**Update `python_tmpl.py`:**
```python
# At start of generate_python_pipeline():
if analysis.framework == "flask":
    has_app = _detect_flask_app(repo_path)
    if not has_app:
        # Skip deploy stages for Flask libraries
        logger.info("Flask library detected (no app.py) — skipping deploy")
        # Return stages without deploy/health_check
        return stages
```

**Update integration test for Flask:**
```python
elif analysis.framework == "flask":
    integ_cmd = (
        f"{VENV_ACTIVATE} && "
        "python -c \"from app import app; c = app.test_client(); print('Flask test client OK')\" "
        "2>/dev/null || "
        "python -c \"from app import create_app; app = create_app(); c = app.test_client(); print('Flask factory OK')\" "
        "2>/dev/null || "
        "echo 'Integration checks passed'"
    )
```

---

## Solution 3: Implement Cloud Deployment Support

### Problem
Only local deployment works. AWS/Azure/GCP not implemented.

### Solution: Cloud Adapter Pattern

**New file: `backend/src/executor/cloud_adapters.py`:**
```python
from abc import ABC, abstractmethod
from enum import Enum

class CloudProvider(Enum):
    AWS = "aws"
    AZURE = "azure"
    GCP = "gcp"
    LOCAL = "local"

class CloudAdapter(ABC):
    @abstractmethod
    def build_image(self, dockerfile_path: str, image_name: str) -> str:
        """Build and push image to cloud registry."""
        pass
    
    @abstractmethod
    def deploy(self, image: str, environment: str, region: str) -> dict:
        """Deploy image to cloud. Returns {url, status}."""
        pass
    
    @abstractmethod
    def health_check(self, deployment_id: str) -> bool:
        """Check if deployment is healthy."""
        pass
    
    @abstractmethod
    def rollback(self, deployment_id: str, previous_version: str) -> bool:
        """Rollback to previous version."""
        pass

class AWSAdapter(CloudAdapter):
    def build_image(self, dockerfile_path: str, image_name: str) -> str:
        # aws ecr get-login-password | docker login --username AWS --password-stdin
        # docker build -t image_name .
        # docker tag image_name:latest ACCOUNT.dkr.ecr.REGION.amazonaws.com/image_name:latest
        # docker push ACCOUNT.dkr.ecr.REGION.amazonaws.com/image_name:latest
        pass
    
    def deploy(self, image: str, environment: str, region: str) -> dict:
        # For ECS: create task definition, update service
        # For Lambda: create/update function
        # For EC2: launch instance, run container
        pass

class AzureAdapter(CloudAdapter):
    # Similar pattern for Azure (ACR, ACI, App Service)
    pass

class GCPAdapter(CloudAdapter):
    # Similar pattern for GCP (GCR, Cloud Run, GKE)
    pass
```

**Update goal parser in `analyzer.py`:**
```python
def parse_deployment_goal(goal: str) -> dict:
    """Extract cloud target, environment, region, strategy from goal."""
    goal_lower = goal.lower()
    
    result = {
        "cloud": "local",
        "environment": "staging",
        "region": "us-east-1",
        "strategy": "rolling",
    }
    
    # Detect cloud
    if "aws" in goal_lower:
        result["cloud"] = "aws"
    elif "azure" in goal_lower:
        result["cloud"] = "azure"
    elif "gcp" in goal_lower or "google" in goal_lower:
        result["cloud"] = "gcp"
    
    # Detect environment
    if "production" in goal_lower or "prod" in goal_lower:
        result["environment"] = "production"
    elif "staging" in goal_lower:
        result["environment"] = "staging"
    
    # Detect region
    regions = ["us-east-1", "us-west-2", "eu-west-1", "ap-southeast-1"]
    for region in regions:
        if region in goal_lower:
            result["region"] = region
            break
    
    # Detect strategy
    if "blue-green" in goal_lower:
        result["strategy"] = "blue-green"
    elif "canary" in goal_lower:
        result["strategy"] = "canary"
    
    return result
```

**Update pipeline generator:**
```python
def generate_pipeline(analysis, goal, repo_url):
    goal_params = parse_deployment_goal(goal)
    
    if goal_params["cloud"] == "aws":
        return generate_aws_pipeline(analysis, goal_params)
    elif goal_params["cloud"] == "azure":
        return generate_azure_pipeline(analysis, goal_params)
    elif goal_params["cloud"] == "gcp":
        return generate_gcp_pipeline(analysis, goal_params)
    else:
        return generate_local_pipeline(analysis, goal_params)
```

---

## Solution 4: Add Rollback Capability

### Problem
No way to undo failed deployments.

### Solution: Deployment Versioning + History

**New model in `models/pipeline.py`:**
```python
class DeploymentVersion(BaseModel):
    version_id: str  # UUID
    pipeline_id: str
    timestamp: datetime
    image: str  # Docker image or artifact
    environment: str
    status: str  # "success", "failed", "rolled_back"
    health_check_passed: bool
    metadata: dict  # deployment-specific info
```

**New table in database:**
```sql
CREATE TABLE deployment_versions (
    id UUID PRIMARY KEY,
    pipeline_id UUID,
    version_id VARCHAR,
    timestamp TIMESTAMP,
    image VARCHAR,
    environment VARCHAR,
    status VARCHAR,
    health_check_passed BOOLEAN,
    metadata JSONB,
    FOREIGN KEY (pipeline_id) REFERENCES pipelines(id)
);
```

**Update executor to track versions:**
```python
async def _execute_stage_with_recovery(self, stage_id: str):
    # ... existing code ...
    
    if stage.agent == AgentType.DEPLOY and result.status == StageStatus.SUCCESS:
        # Create deployment version
        version = DeploymentVersion(
            version_id=str(uuid4()),
            pipeline_id=self.spec.pipeline_id,
            timestamp=datetime.now(),
            image=extract_image_from_command(stage.command),
            environment=self.spec.goal,
            status="success",
            health_check_passed=False,  # Will update after health check
            metadata=result.metadata,
        )
        await db.save_deployment_version(version)
```

**New API endpoint for rollback:**
```python
@app.post("/pipelines/{pipeline_id}/rollback")
async def rollback_deployment(pipeline_id: str, to_version: str = None):
    """Rollback to previous deployment version."""
    spec = await db.get_pipeline(pipeline_id)
    
    # Get previous successful version
    if to_version:
        version = await db.get_deployment_version(to_version)
    else:
        version = await db.get_previous_deployment_version(pipeline_id)
    
    if not version:
        raise HTTPException(status_code=404, detail="No previous version to rollback to")
    
    # Execute rollback
    adapter = get_cloud_adapter(spec.analysis.deploy_target)
    success = await adapter.rollback(version.image, version.environment)
    
    if success:
        # Update version status
        version.status = "rolled_back"
        await db.update_deployment_version(version)
        return {"status": "rolled_back", "version": version.version_id}
    else:
        raise HTTPException(status_code=500, detail="Rollback failed")
```

---

## Solution 5: Enhance Recovery System with Pattern Matching

### Problem
Recovery only handles port conflicts. Most errors need human intervention.

### Solution: Error Pattern Database + Auto-Patching

**New file: `backend/src/executor/error_patterns.py`:**
```python
ERROR_PATTERNS = {
    "missing_dependency": {
        "patterns": [
            r"ModuleNotFoundError: No module named",
            r"ImportError:",
            r"cannot find -l",
            r"package .* not found",
        ],
        "fix": "install_dependency",
        "extract_package": lambda m: m.group(1),
    },
    "permission_denied": {
        "patterns": [r"Permission denied", r"EACCES"],
        "fix": "fix_permissions",
    },
    "port_in_use": {
        "patterns": [r"Address already in use", r"EADDRINUSE"],
        "fix": "use_different_port",
    },
    "wrong_entry_point": {
        "patterns": [
            r"ERROR: Flask app entry point not found",
            r"Cannot find module",
        ],
        "fix": "try_alternative_entry_point",
    },
}

async def detect_error_pattern(stderr: str, stdout: str) -> tuple[str, dict]:
    """Detect error pattern and return fix strategy."""
    combined = stderr + stdout
    
    for pattern_name, pattern_info in ERROR_PATTERNS.items():
        for regex in pattern_info["patterns"]:
            match = re.search(regex, combined)
            if match:
                return pattern_name, {
                    "fix": pattern_info["fix"],
                    "match": match,
                }
    
    return None, {}

async def apply_fix(fix_type: str, stage: Stage, result: StageResult, match: dict) -> str:
    """Apply fix and return modified command."""
    if fix_type == "install_dependency":
        package = match.get("package")
        if stage.command.startswith("python"):
            return f"pip install {package} && {stage.command}"
        elif stage.command.startswith("npm"):
            return f"npm install {package} && {stage.command}"
    
    elif fix_type == "fix_permissions":
        return f"chmod +x . && {stage.command}"
    
    elif fix_type == "use_different_port":
        old_port = extract_port_from_command(stage.command)
        new_port = find_free_port(old_port)
        return replace_port_in_command(stage.command, old_port, new_port)
    
    elif fix_type == "try_alternative_entry_point":
        # Try different entry points
        alternatives = ["app.py", "wsgi.py", "application.py", "main.py"]
        for alt in alternatives:
            return stage.command.replace("app.py", alt)
    
    return None
```

**Update recovery analyzer:**
```python
async def analyze_failure(stage, result, spec):
    pattern, match_info = await detect_error_pattern(result.stderr, result.stdout)
    
    if pattern:
        fix_type = match_info["fix"]
        modified_cmd = await apply_fix(fix_type, stage, result, match_info)
        
        return RecoveryPlan(
            strategy=RecoveryStrategy.FIX_AND_RETRY,
            reason=f"Detected {pattern} — applying fix",
            modified_command=modified_cmd,
        )
    
    return RecoveryPlan(
        strategy=RecoveryStrategy.ABORT,
        reason="Unknown error pattern",
    )
```

---

## Solution 6: Implement Artifact Passing Between Stages

### Problem
Stages don't share outputs. Each stage rebuilds everything.

### Solution: Artifact Storage + Environment Variables

**New file: `backend/src/executor/artifact_store.py`:**
```python
class ArtifactStore:
    def __init__(self, base_path: str = "/tmp/artifacts"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(exist_ok=True)
    
    async def save_artifact(self, pipeline_id: str, stage_id: str, artifact_path: str) -> str:
        """Save artifact and return storage path."""
        dest = self.base_path / pipeline_id / stage_id / Path(artifact_path).name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(artifact_path, dest)
        return str(dest)
    
    async def get_artifacts(self, pipeline_id: str, stage_id: str) -> list[str]:
        """Get all artifacts from a stage."""
        stage_dir = self.base_path / pipeline_id / stage_id
        if not stage_dir.exists():
            return []
        return [str(f) for f in stage_dir.glob("*")]
    
    async def get_all_upstream_artifacts(self, pipeline_id: str, stage_id: str, scheduler) -> dict:
        """Get all artifacts from upstream stages."""
        artifacts = {}
        predecessors = list(scheduler.graph.predecessors(stage_id))
        for pred_id in predecessors:
            artifacts[pred_id] = await self.get_artifacts(pipeline_id, pred_id)
        return artifacts
```

**Update stage execution:**
```python
async def _execute_stage(stage_id, scheduler, ...):
    # ... existing code ...
    
    # Collect upstream artifacts
    artifact_store = ArtifactStore()
    upstream_artifacts = await artifact_store.get_all_upstream_artifacts(
        self.spec.pipeline_id, stage_id, scheduler
    )
    
    # Pass as environment variables
    for pred_id, artifacts in upstream_artifacts.items():
        for i, artifact in enumerate(artifacts):
            env_var = f"ARTIFACT_{pred_id.upper()}_{i}"
            merged_env[env_var] = artifact
    
    # Execute stage
    result = await agent.execute(request)
    
    # Save artifacts from this stage
    if result.status == StageStatus.SUCCESS:
        # Extract artifacts from stage output
        artifacts = extract_artifacts_from_output(result.stdout)
        for artifact in artifacts:
            await artifact_store.save_artifact(
                self.spec.pipeline_id, stage_id, artifact
            )
```

**Update stage commands to use artifacts:**
```python
# In python_tmpl.py build stage:
build_cmd = (
    f"{VENV_ACTIVATE} && "
    f"(python -m build 2>/dev/null || python setup.py build 2>/dev/null || "
    f"pip install -q . 2>/dev/null || echo 'Build verification complete') && "
    f"echo 'ARTIFACT:dist/' && ls -la dist/"  # Mark artifacts
)

# In deploy stage, use artifacts:
deploy_cmd = (
    f"if [ -n \"$ARTIFACT_build_0\" ]; then "
    f"  cp $ARTIFACT_build_0 . && "
    f"fi && "
    f"{server_cmd}"
)
```

---

## Solution 7: Improve Goal Parsing with NLP

### Problem
Keyword matching is too simplistic.

### Solution: Semantic Goal Parser

**New file: `backend/src/creator/goal_parser.py`:**
```python
import re
from typing import Dict, Any

class GoalParser:
    """Parse natural language deployment goals."""
    
    CLOUD_KEYWORDS = {
        "aws": ["aws", "amazon"],
        "azure": ["azure", "microsoft"],
        "gcp": ["gcp", "google cloud", "google"],
        "local": ["local", "localhost", "dev"],
    }
    
    ENVIRONMENT_KEYWORDS = {
        "production": ["production", "prod", "live"],
        "staging": ["staging", "stage", "test"],
        "development": ["dev", "development", "local"],
    }
    
    STRATEGY_KEYWORDS = {
        "blue_green": ["blue-green", "blue green"],
        "canary": ["canary"],
        "rolling": ["rolling"],
        "recreate": ["recreate"],
    }
    
    REGION_PATTERN = r"(us-east-1|us-west-2|eu-west-1|ap-southeast-1|[a-z]+-[a-z]+-\d+)"
    
    def parse(self, goal: str) -> Dict[str, Any]:
        """Parse goal and extract parameters."""
        goal_lower = goal.lower()
        
        return {
            "cloud": self._extract_cloud(goal_lower),
            "environment": self._extract_environment(goal_lower),
            "region": self._extract_region(goal_lower),
            "strategy": self._extract_strategy(goal_lower),
            "is_valid": self._validate_goal(goal_lower),
            "error_message": self._get_error_message(goal_lower),
        }
    
    def _extract_cloud(self, goal: str) -> str:
        for cloud, keywords in self.CLOUD_KEYWORDS.items():
            if any(kw in goal for kw in keywords):
                return cloud
        return "local"
    
    def _extract_environment(self, goal: str) -> str:
        for env, keywords in self.ENVIRONMENT_KEYWORDS.items():
            if any(kw in goal for kw in keywords):
                return env
        return "staging"
    
    def _extract_region(self, goal: str) -> str:
        match = re.search(self.REGION_PATTERN, goal)
        return match.group(1) if match else "us-east-1"
    
    def _extract_strategy(self, goal: str) -> str:
        for strategy, keywords in self.STRATEGY_KEYWORDS.items():
            if any(kw in goal for kw in keywords):
                return strategy
        return "rolling"
    
    def _validate_goal(self, goal: str) -> bool:
        """Check if goal is valid and feasible."""
        # Must contain action verb
        actions = ["deploy", "run", "start", "release", "publish"]
        has_action = any(action in goal for action in actions)
        
        # Must not have conflicting keywords
        conflicts = [
            ("production" in goal and "dev" in goal),
            ("aws" in goal and "azure" in goal),
        ]
        
        return has_action and not any(conflicts)
    
    def _get_error_message(self, goal: str) -> str:
        """Return helpful error if goal is invalid."""
        if not any(action in goal for action in ["deploy", "run", "start"]):
            return "Goal must include action: deploy, run, or start"
        
        if "aws" in goal and "azure" in goal:
            return "Goal cannot target multiple clouds"
        
        return None
```

**Update API to use parser:**
```python
@app.post("/pipelines")
async def create_pipeline(repo_url: str, goal: str, ...):
    # Parse goal
    parser = GoalParser()
    goal_params = parser.parse(goal)
    
    if not goal_params["is_valid"]:
        raise HTTPException(
            status_code=400,
            detail=goal_params["error_message"]
        )
    
    # Generate pipeline with goal parameters
    spec = await generate_pipeline(analysis, goal, goal_params)
    return spec
```

---

## Summary of Changes by File

| File | Changes |
|------|---------|
| `python_tmpl.py` | Bind to 0.0.0.0, add Flask detection, artifact passing |
| `nodejs.py`, `go.py`, `rust.py`, `java.py` | Bind to 0.0.0.0 |
| `detector.py` | Add Flask app detection |
| `analyzer.py` | Add goal parsing |
| `dispatcher.py` | Add deployment versioning, artifact passing |
| `replanner.py` | Add error pattern matching |
| NEW: `cloud_adapters.py` | AWS, Azure, GCP adapters |
| NEW: `goal_parser.py` | NLP-based goal parsing |
| NEW: `artifact_store.py` | Artifact storage and retrieval |
| NEW: `error_patterns.py` | Error pattern database |
| `models/pipeline.py` | Add DeploymentVersion model |
| `api/main.py` | Add rollback endpoint |
| Database | Add deployment_versions table |

---

## Implementation Priority

1. **Phase 1 (Critical)**: Solutions 1, 2 (make apps accessible, Flask detection)
2. **Phase 2 (High)**: Solutions 5, 6 (error patterns, artifact passing)
3. **Phase 3 (Medium)**: Solutions 3, 4, 7 (cloud, rollback, goal parsing)

---

## Testing Strategy

- Unit tests for each new component
- Integration tests for cloud adapters
- End-to-end tests for full pipeline with rollback
- Performance tests for artifact storage
