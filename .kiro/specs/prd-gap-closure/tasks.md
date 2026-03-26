# Tasks: Implementation Plan for PRD Gap Closure

## Phase 1: Critical (Make Apps Accessible & Flask Detection)

### 1.1 Update All Language Templates to Bind to 0.0.0.0
- [x] 1.1.1 Update `python_tmpl.py` - Change Flask/FastAPI/Django to bind to 0.0.0.0
- [x] 1.1.2 Update `nodejs.py` - Change Express/Next.js to bind to 0.0.0.0
- [x] 1.1.3 Update `go.py` - Change Go apps to bind to 0.0.0.0
- [x] 1.1.4 Update `rust.py` - Change Rust apps to bind to 0.0.0.0
- [x] 1.1.5 Update `java.py` - Change Spring Boot to bind to 0.0.0.0
- [x] 1.1.6 Test each language with sample app
- [x] 1.1.7 Verify health check can reach app from host

### 1.2 Implement Flask App Detection
- [x] 1.2.1 Add `_detect_flask_app()` function to `detector.py`
- [x] 1.2.2 Check for app.py, wsgi.py, application.py, main.py
- [x] 1.2.3 Check for factory pattern (create_app function)
- [x] 1.2.4 Update `generate_python_pipeline()` to skip deploy for libraries
- [x] 1.2.5 Update Flask integration test to handle factory pattern
- [x] 1.2.6 Test with Flask library repo (should skip deploy)
- [x] 1.2.7 Test with Flask app repo (should include deploy)

### 1.3 Test Phase 1 Changes
- [x] 1.3.1 Deploy Flask app and verify accessible from host
- [x] 1.3.2 Deploy Node.js app and verify accessible from host
- [x] 1.3.3 Deploy Go app and verify accessible from host
- [x] 1.3.4 Verify health checks pass for all languages
- [x] 1.3.5 Verify Flask library repos skip deploy stage

---

## Phase 2: High Priority (Error Recovery & Artifact Passing)

### Task 2.1: Create Error Pattern Database
- [x] Create `backend/src/executor/error_patterns.py`
- [x] Define patterns for: missing dependency, permission denied, port in use, wrong entry point
- [x] Implement `detect_error_pattern()` function
- [x] Implement `apply_fix()` function for each pattern
- [x] Add unit tests for pattern detection
- [x] Add unit tests for fix application

### Task 2.2: Enhance Recovery System
- [x] Update `replanner.py` to use error patterns
- [x] Implement dependency installation fix
- [x] Implement permission fix
- [x] Implement alternative entry point fix
- [x] Add logging for all recovery attempts
- [x] Test recovery with intentional errors

### Task 2.3: Implement Artifact Storage
- [x] Create `backend/src/executor/artifact_store.py`
- [x] Implement `save_artifact()` method
- [x] Implement `get_artifacts()` method
- [x] Implement `get_all_upstream_artifacts()` method
- [x] Add unit tests for artifact storage
- [x] Add cleanup logic for old artifacts

### Task 2.4: Update Stage Execution for Artifact Passing
- [x] Update `_execute_stage()` to collect upstream artifacts
- [x] Pass artifacts as environment variables
- [x] Update stage commands to mark artifacts in output
- [x] Update build stages to output artifact paths
- [x] Update deploy stages to use artifacts
- [x] Test artifact passing between stages

### Task 2.5: Test Phase 2 Changes
- [x] Test error recovery for missing dependency
- [x] Test error recovery for permission denied
- [x] Test error recovery for port conflict
- [x] Test artifact passing from build to deploy
- [x] Test artifact caching (no rebuild on retry)

---

## Phase 3: Medium Priority (Cloud, Rollback, Goal Parsing)

### Task 3.1: Create Cloud Adapter Framework
- [x] Create `backend/src/executor/cloud_adapters.py`
- [x] Define `CloudAdapter` abstract base class
- [x] Implement `AWSAdapter` (ECR, ECS, Lambda)
- [x] Implement `AzureAdapter` (ACR, ACI, App Service)
- [x] Implement `GCPAdapter` (GCR, Cloud Run, GKE)
- [x] Add unit tests for each adapter
- [x] Add integration tests with mock cloud APIs

### Task 3.2: Implement Deployment Versioning
- [x] Add `DeploymentVersion` model to `models/pipeline.py`
- [x] Create `deployment_versions` table in database
- [x] Update executor to save deployment versions
- [x] Add `get_deployment_version()` to database
- [x] Add `get_previous_deployment_version()` to database
- [x] Add unit tests for versioning

### Task 3.3: Implement Rollback Capability
- [x] Add `/pipelines/{pipeline_id}/rollback` API endpoint
- [x] Implement rollback logic for local deployments
- [x] Implement rollback logic for AWS
- [x] Implement rollback logic for Azure
- [x] Implement rollback logic for GCP
- [x] Add rollback history tracking
- [x] Test rollback for each cloud provider

### Task 3.4: Create Goal Parser
- [x] Create `backend/src/creator/goal_parser.py`
- [x] Implement `GoalParser` class
- [x] Add cloud detection (AWS, Azure, GCP, local)
- [x] Add environment detection (prod, staging, dev)
- [x] Add region extraction
- [x] Add deployment strategy detection
- [x] Add goal validation
- [x] Add unit tests for goal parsing

### Task 3.5: Update Pipeline Generator for Cloud
- [x] Update `generate_pipeline()` to use goal parser
- [x] Create `generate_aws_pipeline()` function
- [x] Create `generate_azure_pipeline()` function
- [x] Create `generate_gcp_pipeline()` function
- [x] Add cloud-specific health checks
- [x] Add cloud-specific security scans
- [x] Test pipeline generation for each cloud

### Task 3.6: Test Phase 3 Changes
- [x] Test AWS deployment (ECR, ECS)
- [x] Test Azure deployment (ACR, ACI)
- [x] Test GCP deployment (GCR, Cloud Run)
- [x] Test rollback for each cloud
- [x] Test goal parsing for various inputs
- [x] Test cloud-specific health checks

---

## Post-Implementation

### Task 4.1: Documentation
- [ ] Update README with cloud deployment instructions
- [ ] Add examples for each cloud provider
- [ ] Document goal syntax and examples
- [ ] Document error recovery patterns
- [ ] Create troubleshooting guide

### Task 4.2: Performance Testing
- [ ] Benchmark artifact storage performance
- [ ] Benchmark error pattern matching
- [ ] Benchmark cloud adapter performance
- [ ] Optimize slow operations

### Task 4.3: Security Review
- [ ] Review cloud credential handling
- [ ] Review artifact storage security
- [ ] Review error logging (no sensitive data)
- [ ] Add encryption for sensitive data

### Task 4.4: User Testing
- [ ] Test with real Flask apps
- [ ] Test with real Node.js apps
- [ ] Test with real Go apps
- [ ] Gather user feedback
- [ ] Fix issues found in testing

---

## Success Criteria

- [ ] All Phase 1 tasks complete and tested
- [ ] All Phase 2 tasks complete and tested
- [ ] All Phase 3 tasks complete and tested
- [ ] 100% of deployed apps accessible from host
- [ ] Flask detection accuracy > 95%
- [ ] Cloud deployments work for AWS, Azure, GCP
- [ ] Rollback succeeds 100% of the time
- [ ] Recovery system fixes 80%+ of common errors
- [ ] Artifact passing reduces build time by 50%+
- [ ] Goal parsing handles 90%+ of natural language inputs
- [ ] All tests passing (unit, integration, e2e)
- [ ] Documentation complete
- [ ] Security review passed
- [ ] User testing feedback positive

---

## Estimated Timeline

- **Phase 1**: 2-3 days (critical path)
- **Phase 2**: 3-4 days (high impact)
- **Phase 3**: 4-5 days (medium priority)
- **Post-Implementation**: 2-3 days (docs, testing, security)

**Total**: ~12-15 days for full implementation

---

## Dependencies

- AWS SDK (boto3)
- Azure SDK (azure-sdk-for-python)
- GCP SDK (google-cloud-python)
- NLP library (spacy or transformers)
- Database migrations
- Cloud credentials (for testing)

---

## Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Cloud API changes | Use stable SDK versions, add version pinning |
| Credential leaks | Use env vars, add secret scanning |
| Artifact storage bloat | Add cleanup job, set size limits |
| Error pattern false positives | Add confidence scoring, manual review |
| Rollback failures | Test thoroughly, add manual rollback option |
| Performance degradation | Benchmark each phase, optimize as needed |

