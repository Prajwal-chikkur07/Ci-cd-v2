# Implementation Plan: CI/CD Orchestrator Audit & Fix

## Overview

Comprehensive audit, fix, and test pass over the full-stack AI-powered CI/CD Pipeline Orchestrator. Tasks are organized into: backend fixes, frontend fixes, test infrastructure, unit tests, property-based tests, integration tests, frontend unit tests, and E2E tests.

## Tasks

- [x] 1. Set up test infrastructure
  - [x] 1.1 Configure pytest and Hypothesis for backend tests
    - Create `backend/tests/` directory structure: `unit/`, `integration/`, `conftest.py`
    - Write `backend/tests/conftest.py` with async SQLite fixture, Hypothesis profiles (`ci`=100, `dev`=20), and shared pipeline/stage factories
    - Add `hypothesis` and `pytest-httpx` to `backend/pyproject.toml` dev dependencies
    - Update `[tool.pytest.ini_options]` in `pyproject.toml` to point `testpaths` at `backend/tests`
    - _Requirements: 19, 20_

  - [x] 1.2 Configure Vitest and Playwright for frontend tests
    - Install `vitest`, `@vitest/ui`, `@testing-library/react`, `@testing-library/user-event`, `jsdom`, `@playwright/test` in `frontend/`
    - Create `frontend/vite.config.ts` (or update existing) with `test: { environment: 'jsdom' }` block
    - Create `e2e/playwright.config.ts` pointing at `http://localhost:5173` with `webServer` config
    - Create `frontend/src/__tests__/` and `e2e/` directories
    - _Requirements: 21_

- [x] 2. Backend audit and fixes — Core execution engine
  - [x] 2.1 Audit and fix DAGScheduler
    - Review `backend/src/executor/scheduler.py`: verify cycle detection, topological ordering, `get_ready_stages()`, `mark_complete()`, `skip_dependents()`, `reset_failed_stages()`
    - Fix any bugs found in dependency resolution or status tracking
    - Ensure `reset_failed_stages()` correctly un-skips stages whose failed predecessors are now pending
    - _Requirements: 3.1, 3.3, 3.4, 3.5, 6.1, 6.2_

  - [x] 2.2 Audit and fix PipelineExecutor
    - Review `backend/src/executor/dispatcher.py`: verify parallel dispatch with `asyncio.gather`, timeout enforcement, hidden failure detection, port conflict auto-recovery
    - Ensure `_collect_upstream_context()` injects all required env vars: `STAGE_<ID>_STATUS`, `STAGE_<ID>_EXIT_CODE`, `STAGE_<ID>_DURATION`, `ARTIFACT_<STAGE_ID>_<INDEX>`
    - Verify `_validate_goal()` correctly checks goal keywords and health_check/docker_build stages
    - Fix any issues with stage retry logic or recovery invocation
    - _Requirements: 3.2, 3.3, 3.4, 3.7, 16.2, 16.3_

  - [x] 2.3 Audit and fix Replanner and error patterns
    - Review `backend/src/executor/replanner.py` and `backend/src/executor/error_patterns.py`
    - Verify all 7 error patterns are correctly defined with regex, fix_type, and extract_info
    - Ensure `detect_error_pattern()` returns correct pattern name and match info
    - Ensure `apply_fix()` generates correct modified commands for each fix type
    - Verify `analyze_failure()` decision tree: pattern detection → rule-based → extended patterns → non-critical skip → abort
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8, 5.9_

  - [x] 2.4 Audit and fix ArtifactStore
    - Review `backend/src/executor/artifact_store.py`
    - Verify `save_artifact()`, `get_artifacts()`, `get_all_upstream_artifacts()`, `cleanup_old_artifacts()`, `cleanup_pipeline_artifacts()` work correctly
    - Ensure artifact paths are correctly injected into downstream stage env vars
    - _Requirements: 16.1, 16.2, 16.4, 16.5_

  - [x] 2.5 Audit and fix WebSocket manager
    - Review `backend/src/api/websocket.py`
    - Verify `ConnectionManager.connect()`, `disconnect()`, `broadcast()` handle dead connections correctly
    - Ensure dead connections are removed during broadcast without crashing
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 22.4_

- [ ] 3. Backend audit and fixes — API endpoints
  - [x] 3.1 Audit and fix pipeline CRUD endpoints
    - Review `backend/src/api/main.py`: `POST /pipelines`, `GET /pipelines`, `GET /pipelines/{id}`, `PATCH /pipelines/{id}`, `DELETE /pipelines/{id}`
    - Verify `GET /pipelines` returns list ordered by `created_at` descending with results, status, and duration
    - Verify `DELETE` cascades stage results and returns 404 for unknown IDs
    - Verify `PATCH` correctly updates name, goal, and stages
    - Verify `POST /pipelines` validates non-empty goal (422 on empty string)
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 22.7_

  - [x] 3.2 Audit and fix execution endpoints
    - Review `POST /pipelines/{id}/execute`, `POST /pipelines/{id}/execute-failed`, `POST /pipelines/{id}/chain`
    - Verify re-clone logic when `work_dir` is missing
    - Verify `execute-failed` returns 400 when no failed stages exist
    - Verify chain stops on first failure and returns `chain_results` for all attempted pipelines
    - Verify circular dependency in stages returns 422
    - _Requirements: 3.9, 6.1, 6.2, 6.3, 7.1, 7.2, 7.3, 22.8_

  - [ ] 3.3 Audit and fix rollback and deployment history endpoints
    - Review `POST /pipelines/{id}/rollback` and `GET /pipelines/{id}/deployment-history`
    - Verify rollback returns 404 when no previous successful version exists
    - Verify `to_version` query param rolls back to specific version
    - Verify deployment version status is updated to `rolled_back` on success
    - _Requirements: 18.1, 18.2, 18.3, 18.4, 18.5, 18.6_

  - [ ] 3.4 Audit and fix database repository
    - Review `backend/src/db/repository.py`: `save_results()`, `get_results()`, `save_pipeline()`, `get_pipeline()`, `list_pipelines()`, `delete_pipeline()`
    - Verify `get_results()` correctly reconstructs `PipelineExecutionResult` from `StageResultRow` records
    - Verify `delete_pipeline()` cascades deletion of stage results and deployment versions
    - Verify `list_pipelines()` orders by `created_at` descending
    - _Requirements: 1.2, 15.1, 15.4, 15.5_

  - [ ] 3.5 Audit and fix GoalParser
    - Review `backend/src/creator/goal_parser.py`
    - Verify all four extractors: cloud, environment, region, strategy
    - Verify `_validate_goal()` rejects goals with no action verb and goals with multiple clouds/environments
    - Verify `GET /parse-goal` endpoint returns all required fields
    - _Requirements: 17.1, 17.2, 17.3, 17.4, 17.5, 17.6_

- [ ] 4. Checkpoint — Backend audit complete
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 5. Frontend audit and fixes — Pages and components
  - [ ] 5.1 Audit and fix DashboardPage
    - Review `frontend/src/pages/DashboardPage.tsx`
    - Verify aggregate stats: total pipelines, total runs, success rate, average duration
    - Verify list of 5 most recent pipelines with status, duration, and link to detail view
    - Verify agent health status display
    - Ensure data is fetched from `GET /pipelines` on load and renders within 2 seconds
    - _Requirements: 11.1, 11.2, 11.3, 11.4_

  - [ ] 5.2 Audit and fix PipelinesPage
    - Review `frontend/src/pages/PipelinesPage.tsx`
    - Verify table/card list with columns: name, repo URL, goal, language, status, last run duration, actions
    - Verify filter controls for status and language update list in real time
    - Verify per-pipeline action buttons: Execute, Edit, Re-run Failed, Delete, Chain
    - Verify execution history display per pipeline
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5_

  - [ ] 5.3 Audit and fix AgentsPage
    - Review `frontend/src/pages/AgentsPage.tsx`
    - Verify historical metrics per agent: total stages executed, success rate, average duration
    - _Requirements: 10.4_

  - [ ] 5.4 Audit and fix LogsPage
    - Review `frontend/src/pages/LogsPage.tsx`
    - Verify logs from all historical pipeline runs are displayed in chronological order
    - Verify real-time search filter narrows entries matching the search term
    - Verify download button exports filtered log entries as plain text
    - _Requirements: 8.4, 8.5, 8.6_

  - [ ] 5.5 Audit and fix SettingsPage
    - Review `frontend/src/pages/SettingsPage.tsx`
    - Verify profile section (display name, email), API keys section (view/add/revoke), integrations section (cloud credentials)
    - Verify sensitive values are masked in display
    - Verify save action persists values and shows success confirmation
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5_

  - [ ] 5.6 Audit and fix PipelineDAG and StageNode
    - Review `frontend/src/components/PipelineDAG.tsx` and `frontend/src/components/StageNode.tsx`
    - Verify Dagre left-to-right layout with no overlapping nodes
    - Verify directed edges from dependency to dependent
    - Verify real-time node color updates: pending=gray, running=blue, success=green, failed=red, skipped=yellow
    - Verify click on node opens Stage Detail Panel
    - Verify empty state message when pipeline has no stages
    - Verify agent type label and stage ID displayed on each node
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7_

  - [ ] 5.7 Audit and fix StageDetailPanel
    - Review `frontend/src/components/StageDetailPanel.tsx`
    - Verify display of: stage ID, agent type, full command, status, exit code, duration, stdout, stderr, env vars, recovery plan
    - Verify real-time stdout updates for running stages
    - Verify recovery plan display: strategy, reason, modified command
    - Verify artifact paths list
    - Verify hidden/empty state when no stage selected
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

  - [ ] 5.8 Audit and fix ExecutionControls
    - Review `frontend/src/components/ExecutionControls.tsx`
    - Verify Run, Re-run Failed, Stop, Regenerate buttons
    - Verify "Re-run Failed" button only appears when at least one stage is failed
    - Verify "Re-run Failed" calls `POST /pipelines/{id}/execute-failed` and resumes WebSocket updates
    - _Requirements: 6.4, 6.5_

  - [ ] 5.9 Audit and fix ExecutionLog
    - Review `frontend/src/components/ExecutionLog.tsx`
    - Verify chronological display of all log entries
    - Verify auto-scroll on new entry
    - Verify color coding: stage_output=white, stage_success=green, stage_failed=red, recovery_plan=orange, pipeline_done=blue
    - _Requirements: 8.1, 8.2, 8.3_

  - [ ] 5.10 Audit and fix StatusBanner and browser notifications
    - Review `frontend/src/components/StatusBanner.tsx`
    - Verify deploy URL displayed as clickable link when `deploy_url` field present in WebSocket event
    - Verify browser notification sent on pipeline success and failure
    - Verify auto-open URL behavior when enabled in settings
    - _Requirements: 4.10, 14.1, 14.2, 14.3, 14.4_

  - [ ] 5.11 Audit and fix WebSocket client hook
    - Review `frontend/src/hooks/useWebSocket.ts`
    - Verify automatic reconnect up to 3 times with 2-second delay
    - Verify JSON parse errors are caught and logged as warnings without crashing
    - Verify `stage_output` events append to Execution Log in real time
    - Verify `stage_success`/`stage_failed` events update DAG node colors immediately
    - _Requirements: 4.7, 4.8, 4.9, 22.6_

  - [ ] 5.12 Audit and fix PipelineContext and history persistence
    - Review `frontend/src/context/PipelineContext.tsx`
    - Verify `listPipelines()` is called on mount and history is restored
    - Verify `loadFromHistory()` restores pipeline spec, stage statuses, results, and logs
    - Verify parallel execution state management: `registerExecution`, `unregisterExecution`, `switchToExecution`
    - _Requirements: 15.2, 15.3_

  - [ ] 5.13 Audit and fix CreatePipeline and EditPipeline
    - Review `frontend/src/components/CreatePipeline.tsx` and `frontend/src/components/EditPipeline.tsx`
    - Verify create form: repo URL, goal, optional name, Docker toggle
    - Verify navigation to pipeline detail view after successful creation
    - Verify edit interface for name, goal, and individual stage commands
    - Verify Regenerate Pipeline re-submits to `POST /pipelines` and replaces current spec
    - _Requirements: 1.8, 1.9, 1.10, 1.11_

- [ ] 6. Checkpoint — Frontend audit complete
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 7. Backend unit tests
  - [ ] 7.1 Write unit tests for DAGScheduler
    - Create `backend/tests/unit/test_scheduler.py`
    - Test topological ordering for linear, branching, and diamond DAGs
    - Test cycle detection raises `ValueError`
    - Test unknown `depends_on` reference raises `ValueError`
    - Test `get_ready_stages()` returns only stages with all predecessors complete
    - Test `mark_complete()` updates status and stores result
    - Test `skip_dependents()` marks all transitive descendants as SKIPPED
    - Test `reset_failed_stages()` resets FAILED→PENDING and un-skips eligible SKIPPED stages
    - _Requirements: 19.1_

  - [ ]* 7.2 Write property test for DAGScheduler topological correctness
    - **Property 1: DAG Topological Correctness**
    - **Validates: Requirements 3.1, 3.3, 3.4, 22.8**

  - [ ]* 7.3 Write property test for stage status transition invariant
    - **Property 3: Stage Status Transition Invariant**
    - **Validates: Requirements 3.3, 3.4, 3.5, 6.1, 6.2**

  - [ ]* 7.4 Write property test for re-run failed stages preserves successes
    - **Property 9: Re-Run Failed Stages Preserves Successes**
    - **Validates: Requirements 6.1, 6.2**

  - [ ] 7.5 Write unit tests for GoalParser
    - Create `backend/tests/unit/test_goal_parser.py`
    - Test cloud extraction for each provider keyword (aws, azure, gcp) and default to local
    - Test environment extraction for each keyword and default to staging
    - Test region extraction for AWS, Azure, GCP region lists and generic pattern
    - Test strategy extraction for each keyword and default to rolling
    - Test `_validate_goal()` rejects no-action-verb goals and multi-cloud/multi-env goals
    - Test `_get_error_message()` returns correct messages for each invalid case
    - _Requirements: 19.2_

  - [ ]* 7.6 Write property test for GoalParser idempotence
    - **Property 14: Goal Parser Idempotence**
    - **Validates: Requirements 17.1, 17.2, 17.3, 17.4, 17.6**

  - [ ] 7.7 Write unit tests for error patterns
    - Create `backend/tests/unit/test_error_patterns.py`
    - Test each of the 7 error patterns matches its target trigger strings
    - Test each pattern does NOT match unrelated strings
    - Test `apply_fix()` generates correct modified commands for each fix type
    - Test `get_fix_reason()` returns non-empty string for each pattern name
    - _Requirements: 19.3_

  - [ ]* 7.8 Write property test for error pattern detection correctness
    - **Property 6: Error Pattern Detection Correctness**
    - **Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5**

  - [ ]* 7.9 Write property test for recovery plan completeness
    - **Property 7: Recovery Plan Completeness**
    - **Validates: Requirements 5.2, 5.3, 5.4, 5.5, 5.6**

  - [ ] 7.10 Write unit tests for ArtifactStore
    - Create `backend/tests/unit/test_artifact_store.py`
    - Test `save_artifact()` copies file to correct path and returns stored path
    - Test `get_artifacts()` returns all saved artifact paths for a stage
    - Test `get_all_upstream_artifacts()` collects from all predecessor stages
    - Test `cleanup_old_artifacts()` removes artifacts older than threshold and returns count
    - Test `cleanup_pipeline_artifacts()` removes entire pipeline artifact tree
    - _Requirements: 19.4_

  - [ ]* 7.11 Write property test for artifact store round-trip
    - **Property 12: Artifact Store Round-Trip**
    - **Validates: Requirements 16.1, 16.2**

  - [ ]* 7.12 Write property test for upstream artifact injection
    - **Property 13: Upstream Artifact Injection**
    - **Validates: Requirements 16.2, 16.3**

  - [ ] 7.13 Write unit tests for ConnectionManager
    - Create `backend/tests/unit/test_websocket.py`
    - Test `connect()` adds WebSocket to pipeline's connection list
    - Test `disconnect()` removes WebSocket and cleans up empty pipeline entry
    - Test `broadcast()` sends message to all connected clients
    - Test `broadcast()` removes dead connections that raise `WebSocketDisconnect` or `RuntimeError`
    - _Requirements: 19.5_

  - [ ]* 7.14 Write property test for dead WebSocket connection cleanup
    - **Property 15: Dead WebSocket Connection Cleanup**
    - **Validates: Requirements 4.7, 22.4**

  - [ ] 7.15 Write unit tests for dispatcher utilities
    - Create `backend/tests/unit/test_dispatcher.py`
    - Test `extract_deploy_url()` for all 4 port patterns in stdout, stderr, and command strings
    - Test hidden failure detection overrides SUCCESS to FAILED for known fatal error strings
    - Test port conflict auto-recovery rewrites command and updates downstream VERIFY stage
    - _Requirements: 19.6_

  - [ ] 7.16 Write unit tests for DeploymentVersion model
    - Create `backend/tests/unit/test_models.py`
    - Test `DeploymentVersion` serialization to JSON and deserialization back to model
    - Test field defaults: `version_id` is UUID, `timestamp` is set, `health_check_passed` defaults to False
    - Test `StageResult` field defaults: `exit_code=-1`, `artifacts=[]`, `metadata={}`
    - _Requirements: 19.7_

  - [ ]* 7.17 Write property test for execution result persistence round-trip
    - **Property 11: Execution Result Persistence Round-Trip**
    - **Validates: Requirements 15.1, 8.7**

  - [ ]* 7.18 Write property test for pipeline list ordering
    - **Property 16: Pipeline List Ordering**
    - **Validates: Requirements 1.2**

- [ ] 8. Checkpoint — Backend unit tests complete
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 9. Backend integration tests
  - [ ] 9.1 Write integration tests for pipeline CRUD API
    - Create `backend/tests/integration/test_api_pipelines.py`
    - Test `POST /pipelines` with a known local fixture repo: verify spec returned with correct stages, persisted to DB
    - Test `GET /pipelines` returns list ordered by `created_at` descending
    - Test `GET /pipelines/{id}` returns correct spec; returns 404 for unknown ID
    - Test `PATCH /pipelines/{id}` updates name, goal, stages; returns 404 for unknown ID
    - Test `DELETE /pipelines/{id}` removes pipeline and stage results; returns 404 for unknown ID
    - Test `POST /pipelines` with empty goal returns 422
    - _Requirements: 20.1, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7_

  - [ ] 9.2 Write integration tests for pipeline execution
    - Create `backend/tests/integration/test_api_execution.py`
    - Test `POST /pipelines/{id}/execute` with a 2-stage pipeline: verify stages execute in dependency order, results persisted
    - Test `POST /pipelines/{id}/execute-failed`: inject failure, call endpoint, verify only failed stages re-run and successes preserved
    - Test `POST /pipelines/{id}/execute-failed` returns 400 when no failed stages exist
    - Test circular dependency in stages returns 422
    - _Requirements: 20.2, 20.3, 3.1, 3.3, 6.1, 6.3_

  - [ ] 9.3 Write integration tests for pipeline chaining
    - Create `backend/tests/integration/test_api_chain.py`
    - Test `POST /pipelines/{id}/chain` with 3 pipelines: verify sequential execution order
    - Test chain stops when first pipeline fails and does not execute subsequent pipelines
    - Verify `chain_results` map contains entries for all attempted pipelines
    - _Requirements: 20.4, 7.1, 7.2, 7.3_

  - [ ] 9.4 Write integration tests for rollback
    - Create `backend/tests/integration/test_api_rollback.py`
    - Test `POST /pipelines/{id}/rollback` rolls back to most recent successful version
    - Test rollback with `to_version` query param rolls back to specific version
    - Test rollback returns 404 when no previous successful version exists
    - Test `GET /pipelines/{id}/deployment-history` returns versions ordered by timestamp descending
    - _Requirements: 20.5, 18.2, 18.3, 18.4, 18.5, 18.6_

  - [ ] 9.5 Write integration tests for WebSocket event sequence
    - Create `backend/tests/integration/test_websocket_events.py`
    - Connect a test WebSocket client before executing a pipeline
    - Verify `pipeline_start` event arrives first
    - Verify each stage produces `stage_start` before `stage_success` or `stage_failed`
    - Verify `pipeline_done` arrives last after all stage terminal events
    - _Requirements: 20.6, 4.1, 4.2, 4.4, 4.5, 4.6_

  - [ ]* 9.6 Write property test for WebSocket event sequence ordering
    - **Property 5: WebSocket Event Sequence**
    - **Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.5, 4.6**

  - [ ] 9.7 Write integration tests for recovery system
    - Create `backend/tests/integration/test_recovery.py`
    - Inject `ModuleNotFoundError` into stage output; verify `FIX_AND_RETRY` plan is generated and broadcast
    - Inject `Permission denied` into stage output; verify `fix_permissions` plan generated
    - Inject `Address already in use` into stage output; verify port conflict recovery
    - Verify non-critical stage failure results in SKIPPED status and pipeline continues
    - _Requirements: 20.7, 5.1, 5.2, 5.3, 5.4_

  - [ ] 9.8 Write integration tests for concurrent pipeline execution
    - Create `backend/tests/integration/test_concurrent.py`
    - Execute 2 pipelines simultaneously using `asyncio.gather`
    - Verify each pipeline's stage results are isolated (no state interference)
    - Verify WebSocket events for each pipeline are broadcast only to that pipeline's subscribers
    - _Requirements: 20.8, 3.10_

  - [ ] 9.9 Write integration tests for edge cases
    - Create `backend/tests/integration/test_edge_cases.py`
    - Test invalid/unreachable repo URL returns 422 or 500 within 30 seconds
    - Test pipeline with empty stages list
    - Test pipeline with stage depending on non-existent stage ID returns 422
    - Test `GET /pipelines/{id}` with unknown ID returns 404
    - _Requirements: 20.9, 22.1, 22.8_

- [ ] 10. Checkpoint — Backend integration tests complete
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 11. Frontend unit tests
  - [ ] 11.1 Write unit tests for dagLayout utility
    - Create `frontend/src/__tests__/dagLayout.test.ts`
    - Test `createNodesAndEdges()` returns exactly N nodes for a pipeline with N stages
    - Test all returned node IDs are unique
    - Test no two nodes share identical `(x, y)` position coordinates
    - Test edges are created for each `depends_on` relationship
    - _Requirements: 2.1, 2.2, 2.3_

  - [ ]* 11.2 Write property test for DAG layout non-overlap
    - **Property 17: DAG Layout Non-Overlap**
    - **Validates: Requirements 2.1, 2.2**

  - [ ] 11.3 Write unit tests for statusColors utility
    - Create `frontend/src/__tests__/statusColors.test.ts`
    - Test color mapping returns a non-empty string for every `StageStatus` value
    - Test mapping is injective: no two distinct statuses map to the same color
    - _Requirements: 2.4_

  - [ ]* 11.4 Write property test for status color mapping completeness
    - **Property 18: Status Color Mapping Completeness**
    - **Validates: Requirements 2.4**

  - [ ] 11.5 Write unit tests for PipelineContext
    - Create `frontend/src/__tests__/PipelineContext.test.tsx`
    - Test `setPipeline()` initializes all stage statuses to `pending`
    - Test `updateStageStatus()` updates only the specified stage
    - Test `addLog()` appends entry to `executionLogs`
    - Test `registerExecution()` / `unregisterExecution()` manage `activeExecutions` map
    - Test `switchToExecution()` loads execution state into main view
    - _Requirements: 3.10_

  - [ ] 11.6 Write unit tests for useWebSocket hook
    - Create `frontend/src/__tests__/useWebSocket.test.ts`
    - Mock the browser `WebSocket` class
    - Test hook connects to correct URL on mount
    - Test `onUpdate` callback is called with parsed message on `onmessage`
    - Test hook retries up to 3 times with 2-second delay on `onclose`
    - Test JSON parse errors are caught and do not crash the hook
    - _Requirements: 4.7, 22.6_

  - [ ] 11.7 Write unit tests for ExecutionLog component
    - Create `frontend/src/__tests__/ExecutionLog.test.tsx`
    - Test log entries are rendered in chronological order
    - Test each log type renders with correct CSS color class
    - Test new entry triggers auto-scroll to bottom
    - _Requirements: 8.1, 8.2, 8.3_

  - [ ] 11.8 Write unit tests for StageDetailPanel component
    - Create `frontend/src/__tests__/StageDetailPanel.test.tsx`
    - Test panel displays stage ID, agent type, command, status, exit code, duration
    - Test stdout and stderr are rendered
    - Test recovery plan section shows strategy, reason, and modified command when present
    - Test artifact paths list is rendered
    - Test panel is hidden when no stage is selected
    - _Requirements: 9.1, 9.3, 9.4, 9.5_

- [ ] 12. Checkpoint — Frontend unit tests complete
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 13. Remaining property-based tests
  - [ ]* 13.1 Write property test for parallel stage dispatch
    - **Property 2: Parallel Stage Dispatch**
    - **Validates: Requirements 3.2**

  - [ ]* 13.2 Write property test for timeout enforcement
    - **Property 4: Timeout Enforcement**
    - **Validates: Requirements 3.7, 22.5**

  - [ ]* 13.3 Write property test for retry count exhaustion before replanner
    - **Property 8: Retry Count Exhaustion Before Replanner**
    - **Validates: Requirements 5.12**

  - [ ]* 13.4 Write property test for pipeline chain stop-on-failure
    - **Property 10: Pipeline Chain Stop-on-Failure**
    - **Validates: Requirements 7.1, 7.2**

- [ ] 14. E2E tests
  - [ ] 14.1 Write E2E test: create and execute pipeline
    - Create `e2e/create_and_execute.spec.ts`
    - Fill create pipeline form with repo URL and goal
    - Submit and verify DAG renders with correct number of stage nodes
    - Click Execute and verify status banner shows success or failure after completion
    - _Requirements: 21.1_

  - [ ] 14.2 Write E2E test: real-time WebSocket log streaming
    - Create `e2e/websocket_logs.spec.ts`
    - Execute a pipeline and verify log lines appear in the Execution Log panel in real time
    - Verify at least one `stage_output` entry is visible before pipeline completes
    - _Requirements: 21.2_

  - [ ] 14.3 Write E2E test: stage detail panel
    - Create `e2e/stage_detail.spec.ts`
    - After a pipeline run, click a completed DAG node
    - Verify Stage Detail Panel shows stdout, stderr, and duration for that stage
    - _Requirements: 21.3_

  - [ ] 14.4 Write E2E test: re-run failed stages
    - Create `e2e/rerun_failed.spec.ts`
    - Trigger a pipeline failure (use a repo/goal that produces a known failure)
    - Verify "Re-run Failed" button appears in ExecutionControls
    - Click button and verify only failed stages are re-executed (successful stages remain green)
    - _Requirements: 21.4_

  - [ ] 14.5 Write E2E test: dashboard statistics
    - Create `e2e/dashboard_stats.spec.ts`
    - Complete a pipeline run
    - Navigate to Dashboard page
    - Verify aggregate stats are updated (total pipelines, success rate)
    - _Requirements: 21.5_

  - [ ] 14.6 Write E2E test: pipeline deletion
    - Create `e2e/delete_pipeline.spec.ts`
    - Navigate to Pipelines Page
    - Delete a pipeline using the Delete action button
    - Verify the pipeline entry is removed from the list
    - _Requirements: 21.6_

  - [ ] 14.7 Write E2E test: logs page search filter
    - Create `e2e/logs_search.spec.ts`
    - Navigate to Logs Page
    - Enter a search term in the filter input
    - Verify only log entries matching the search term are displayed
    - _Requirements: 21.7_

  - [ ] 14.8 Write E2E test: browser notification on pipeline completion
    - Create `e2e/browser_notification.spec.ts`
    - Grant notification permission via Playwright context options
    - Complete a pipeline run
    - Verify a browser notification is sent with the pipeline name and result message
    - _Requirements: 21.8_

  - [ ] 14.9 Write E2E test: edit pipeline and re-execute
    - Create `e2e/edit_pipeline.spec.ts`
    - Open a pipeline and click Edit
    - Modify a stage command
    - Save and re-execute
    - Verify the modified command appears in the stage detail panel output
    - _Requirements: 21.9_

  - [ ] 14.10 Write E2E test: pipeline chaining
    - Create `e2e/chain_pipelines.spec.ts`
    - Select two pipelines and chain them via the UI
    - Verify sequential execution: second pipeline starts only after first completes
    - Inject a failure in the first pipeline and verify the chain stops
    - _Requirements: 21.10_

- [ ] 15. Final checkpoint — All tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Property tests use Hypothesis with `@settings(max_examples=100)` and must include a comment: `# Feature: cicd-orchestrator-audit-fix, Property N: <property_text>`
- Backend tests live in `backend/tests/unit/` and `backend/tests/integration/`
- Frontend unit tests live in `frontend/src/__tests__/`
- E2E tests live in `e2e/`
- Checkpoints ensure incremental validation after each major phase
