# Requirements: Close PRD Gaps in CI/CD Pipeline Orchestrator

## Feature Name
`prd-gap-closure` - Implement missing features to fully match the Product Requirements Document

## Overview
The current CI/CD Pipeline Orchestrator implements ~70% of the PRD requirements. This document identifies the critical gaps between what was promised and what's currently working, and defines the requirements to close them.

## Current State vs PRD Promise

### What the PRD Promises
1. **Auto-generate pipelines** from any repo URL + deployment goal
2. **Self-healing pipelines** that fix failures without human intervention
3. **Deploy to any target** (local, AWS, Azure, GCP, Kubernetes)
4. **Full observability** with real-time logs and status
5. **Intelligent retry logic** that decides when to retry, skip, or rollback
6. **Security scans** run automatically on every pipeline
7. **Health checks** verify deployment is live and accessible

### What Actually Works
- ✅ Auto-generate pipelines (basic language/framework detection)
- ✅ Self-healing (limited to port conflicts only)
- ✅ Deploy to local environment (but not accessible from host)
- ✅ Full observability (real-time logs work)
- ⚠️ Retry logic (only retries same command, no intelligence)
- ✅ Security scans (pip-audit runs)
- ⚠️ Health checks (pass inside container, but app unreachable from outside)

---

## Critical Issues to Fix

### Issue 1: Deployed Apps Not Accessible from Host Machine

**Problem**
- User deploys Flask app to `localhost:3000`
- Health check passes (runs inside Docker container, can reach the app)
- User tries to access `http://localhost:3000` from browser → Connection refused
- App is running but isolated inside the backend container

**Why This Breaks the PRD**
- PRD says: "User gets a notification: done, with a full run report" + deployment URL
- Reality: URL is shown but clicking it fails
- Breaks the core promise: "takes code from a developer's laptop to a live server"

**Root Cause**
- Deploy stage runs inside Docker container
- App listens on container's `localhost:3000`
- Port 3000 is exposed in docker-compose but app doesn't bind to `0.0.0.0`
- Container's localhost ≠ host's localhost

**Impact**
- Users cannot verify deployments work
- "Deploy locally" goal is broken
- Health check is misleading (passes but app unreachable)

---

### Issue 2: Flask App Detection Incomplete

**Problem**
- System detects "Flask framework" by finding "flask" in requirements.txt
- But doesn't verify an actual Flask app exists (app.py, wsgi.py, etc.)
- Falls back to generic entry points that fail for Flask libraries
- Result: Deploy stage succeeds but app never starts

**Why This Breaks the PRD**
- PRD says: "System analyzes repo and generates full pipeline plan"
- Reality: System generates plan but can't execute it for Flask repos
- Breaks the promise: "It figures out the rest — automatically"

**Root Cause**
- Detector only checks if "flask" is in dependencies
- Doesn't check if there's an actual app to run
- No distinction between Flask library vs Flask application

**Impact**
- Flask library repos fail to deploy
- Health check fails with "no app entry point found"
- Recovery system can't fix it (no automated fix for missing app)

---

### Issue 3: Cloud Deployment Not Implemented

**Problem**
- PRD lists AWS, Azure, GCP as deployment targets
- Code only supports local deployment
- `deploy_target` field exists but is ignored during execution
- No cloud-specific stages or credentials handling

**Why This Breaks the PRD**
- PRD says: "Deploy to AWS staging" as example goal
- Reality: Only "deploy locally" works
- Breaks the promise: "Deploy to any target"

**Root Cause**
- Pipeline generator creates generic deploy stages
- No AWS/Azure/GCP specific commands
- No credential/auth handling
- No cloud-specific health checks

**Impact**
- Cannot deploy to production
- Startup teams can't use the platform for real deployments
- Only works for local development

---

### Issue 4: No Rollback Capability

**Problem**
- When deployment fails, system retries or skips
- No way to rollback to previous version
- No deployment history tracking
- If deploy succeeds but app crashes, no recovery

**Why This Breaks the PRD**
- PRD says: "System replans automatically — retries, patches, or rolls back"
- Reality: No rollback implemented
- Breaks the promise: "Self-healing without human intervention"

**Root Cause**
- No deployment versioning
- No previous state tracking
- Recovery system only handles pre-deployment failures
- No post-deployment health monitoring

**Impact**
- Bad deployments can't be undone
- No safety net for production
- Breaks trust in "autonomous" system

---

### Issue 5: Limited Self-Healing Logic

**Problem**
- Recovery system only handles port conflicts
- Cannot fix: missing dependencies, wrong entry points, config errors
- Retries same command that failed (no intelligence)
- No pattern matching for common errors

**Why This Breaks the PRD**
- PRD says: "System replans automatically — retries, patches, or rolls back"
- Reality: System only retries, doesn't patch
- Breaks the promise: "No intelligence to fix it" → "System fixes it"

**Root Cause**
- Recovery analyzer is basic (only checks for port conflicts)
- No error pattern database
- No automated patching logic
- No dependency resolution

**Impact**
- Most failures require human intervention
- Defeats the purpose of "self-healing"
- Users still need DevOps expertise

---

### Issue 6: No Artifact/Output Passing Between Stages

**Problem**
- Stages run independently
- No way to pass outputs from one stage to next
- Each stage re-discovers information (e.g., build artifacts)
- No caching of build outputs

**Why This Breaks the PRD**
- PRD says: "Pass outputs from one stage safely to the next stage"
- Reality: Stages don't communicate
- Breaks efficiency: "takes code from a developer's laptop to a live server" (should be fast)

**Root Cause**
- Stage execution is isolated
- No artifact storage mechanism
- No environment variable passing between stages
- No build cache

**Impact**
- Pipelines are slow (rebuild everything each stage)
- Cannot use build artifacts in deploy
- Inefficient for large projects

---

### Issue 7: Goal Translation Too Simplistic

**Problem**
- Goal parsing uses simple keyword matching
- "deploy to AWS staging" → only matches "deploy" keyword
- Doesn't extract: target (AWS), environment (staging), region, etc.
- Cannot handle complex goals like "deploy to AWS us-east-1 with blue-green strategy"

**Why This Breaks the PRD**
- PRD says: "Translate a plain-English goal like 'deploy to AWS staging' into structured stages"
- Reality: Only extracts "deploy" keyword
- Breaks the promise: "Figures out the rest automatically"

**Root Cause**
- Goal parser is regex-based keyword matching
- No NLP or semantic understanding
- No extraction of parameters (region, environment, strategy)
- No validation of goal feasibility

**Impact**
- Users must use specific keywords
- Cannot specify deployment strategy
- Limited flexibility

---

## Requirements by Priority

### P0: Critical (Blocks Core Functionality)

#### R1: Make Deployed Apps Accessible from Host
**Requirement**: Deployed applications must be reachable from the host machine at the provided URL

**Acceptance Criteria**
- [ ] When deploy stage completes, app listens on `0.0.0.0` (not just `localhost`)
- [ ] Health check can reach app from host machine
- [ ] Deployment URL shown in UI is actually clickable and works
- [ ] Works for Python (Flask, FastAPI, Django), Node.js, Go, Rust, Java

**Why**: Without this, the entire "deploy locally" feature is broken. Users cannot verify deployments work.

---

#### R2: Improve Flask App Detection
**Requirement**: System must distinguish between Flask libraries and Flask applications

**Acceptance Criteria**
- [ ] Detect if repo contains actual Flask app (app.py, wsgi.py, application.py, or factory pattern)
- [ ] Skip deploy stage for Flask libraries (no app to run)
- [ ] For factory pattern apps, generate correct entry point
- [ ] Provide clear error message if no app found

**Why**: Currently fails silently for Flask libraries, confusing users.

---

#### R3: Implement Cloud Deployment Support
**Requirement**: System must support deploying to AWS, Azure, and GCP

**Acceptance Criteria**
- [ ] Parse cloud target from goal (e.g., "deploy to AWS staging")
- [ ] Generate cloud-specific deploy stages (build image, push to registry, deploy to cloud)
- [ ] Handle cloud credentials (from env vars or config)
- [ ] Support multiple environments (staging, production)
- [ ] Cloud-specific health checks (check cloud endpoints, not localhost)

**Why**: PRD explicitly promises cloud deployment. Without it, only works for local dev.

---

#### R4: Add Rollback Capability
**Requirement**: System must be able to rollback failed deployments to previous version

**Acceptance Criteria**
- [ ] Track deployment history (version, timestamp, status)
- [ ] On deploy failure, offer rollback option
- [ ] Rollback restores previous version
- [ ] Rollback is automatic for critical failures (optional)
- [ ] Works for local and cloud deployments

**Why**: PRD promises "rolls back" as recovery strategy. Without it, bad deployments are permanent.

---

### P1: High (Significantly Improves Self-Healing)

#### R5: Enhance Recovery System with Pattern Matching
**Requirement**: Recovery system must recognize common error patterns and apply fixes

**Acceptance Criteria**
- [ ] Detect missing dependencies and install them
- [ ] Detect wrong entry point and try alternatives
- [ ] Detect port conflicts and retry on different port
- [ ] Detect permission errors and fix permissions
- [ ] Detect config errors and suggest fixes
- [ ] Log all recovery attempts for debugging

**Why**: Current system only handles port conflicts. Most failures require human intervention.

---

#### R6: Implement Artifact Passing Between Stages
**Requirement**: Stages must be able to share outputs and artifacts

**Acceptance Criteria**
- [ ] Build stage outputs artifacts (compiled code, docker image, etc.)
- [ ] Deploy stage can access build artifacts
- [ ] Environment variables passed from stage to stage
- [ ] Artifacts cached to avoid rebuilding
- [ ] Works for all languages

**Why**: Pipelines are slow because each stage rebuilds. Artifacts should be reused.

---

#### R7: Improve Goal Parsing with NLP
**Requirement**: System must extract deployment parameters from natural language goals

**Acceptance Criteria**
- [ ] Extract cloud target (AWS, Azure, GCP, local)
- [ ] Extract environment (staging, production, dev)
- [ ] Extract region (us-east-1, eu-west-1, etc.)
- [ ] Extract deployment strategy (blue-green, canary, rolling)
- [ ] Validate goal is feasible before generating pipeline
- [ ] Provide helpful error if goal is unclear

**Why**: Current keyword matching is too simplistic. Users need flexibility.

---

### P2: Medium (Improves Reliability)

#### R8: Add Post-Deployment Health Monitoring
**Requirement**: System must monitor deployed app health after deployment

**Acceptance Criteria**
- [ ] Health check runs periodically after deploy (not just once)
- [ ] Detect if app crashes after deploy
- [ ] Trigger rollback if app becomes unhealthy
- [ ] Log health check history
- [ ] Configurable health check interval and thresholds

**Why**: Current health check only runs once. App could crash after health check passes.

---

#### R9: Implement Dependency Resolution
**Requirement**: System must automatically resolve and install missing dependencies

**Acceptance Criteria**
- [ ] Detect missing system dependencies (apt, brew, etc.)
- [ ] Detect missing language dependencies (pip, npm, cargo, etc.)
- [ ] Automatically install missing dependencies
- [ ] Handle version conflicts
- [ ] Log all installed dependencies

**Why**: Many failures are due to missing dependencies. Should be automatic.

---

#### R10: Add Security Scan Enforcement
**Requirement**: Security scans must be mandatory and block deployment if vulnerabilities found

**Acceptance Criteria**
- [ ] Security scan runs on every pipeline
- [ ] Scan results block deployment if critical vulnerabilities found
- [ ] Allow override for non-critical vulnerabilities
- [ ] Generate security report
- [ ] Track vulnerability trends over time

**Why**: PRD says "Security scans are skipped or run inconsistently". Should be enforced.

---

## Success Metrics

### Functional Metrics
- [ ] 100% of deployed apps are accessible from host machine
- [ ] Flask app detection accuracy > 95%
- [ ] Cloud deployments work for AWS, Azure, GCP
- [ ] Rollback succeeds 100% of the time
- [ ] Recovery system fixes 80%+ of common errors without human intervention

### User Experience Metrics
- [ ] Time to deploy reduced from hours to minutes
- [ ] Deployment success rate > 95%
- [ ] User satisfaction with self-healing > 4/5
- [ ] Zero manual interventions needed for standard deployments

### Reliability Metrics
- [ ] No deployments fail due to missing dependencies
- [ ] No deployments fail due to port conflicts
- [ ] No deployments fail due to wrong entry points
- [ ] Health checks accurately reflect app status

---

## Out of Scope (For Future)

These are important but not blocking the PRD requirements:

- [ ] Multi-region deployments
- [ ] Cost optimization
- [ ] Performance tuning
- [ ] Advanced monitoring/alerting
- [ ] Custom pipeline stages
- [ ] Pipeline templates
- [ ] Team collaboration features
- [ ] Audit logging

---

## Dependencies

- Requires understanding of cloud APIs (AWS, Azure, GCP)
- Requires NLP library for goal parsing
- Requires artifact storage system
- Requires deployment versioning system

---

## Next Steps

1. Review and approve requirements
2. Create design document with technical solutions
3. Break down into implementation tasks
4. Prioritize by impact and effort
