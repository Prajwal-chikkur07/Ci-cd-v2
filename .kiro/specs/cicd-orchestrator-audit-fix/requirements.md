# Requirements Document

## Introduction

This spec covers a comprehensive audit, test, debug, and fix pass over the full-stack AI-powered CI/CD Pipeline Orchestrator system. The system consists of:

- **Backend**: Python FastAPI server with a DAG-based execution engine, 5 specialized agents (build, test, security, deploy, verify), WebSocket streaming, SQLite/PostgreSQL persistence, and a self-healing recovery system.
- **Frontend**: React/TypeScript SPA with real-time WebSocket updates, DAG visualization (ReactFlow), parallel execution tabs, stage detail panels, and five pages (Dashboard, Pipelines, Agents, Logs, Settings).
- **Execution Engine**: Async pipeline executor with DAG scheduling, parallel stage dispatch, artifact passing, error pattern matching, and cloud adapter support.

The goal is to ensure every listed feature is fully implemented, correctly connected end-to-end (frontend ↔ backend ↔ execution engine), and covered by automated tests (unit + integration + e2e).

---

## Glossary

- **Pipeline**: A named, ordered set of stages derived from a repository URL and a plain-English deployment goal.
- **Stage**: A single executable unit within a pipeline, assigned to one Agent, with a command, dependencies, timeout, and retry count.
- **DAG**: Directed Acyclic Graph representing stage dependencies and execution order.
- **Agent**: One of five specialized executors — Build, Test, Security, Deploy, Verify — each responsible for a class of stage commands.
- **Execution Engine**: The `PipelineExecutor` + `DAGScheduler` subsystem that dispatches stages in dependency order, handles retries, and invokes the Replanner on failure.
- **Replanner**: The self-healing subsystem (`replanner.py` + `error_patterns.py`) that analyzes failures and produces a `RecoveryPlan`.
- **WebSocket Manager**: The `ConnectionManager` in `websocket.py` that broadcasts real-time stage events to connected frontend clients.
- **Artifact Store**: The `ArtifactStore` class that persists build outputs between stages within a pipeline run.
- **Recovery Strategy**: One of `FIX_AND_RETRY`, `SKIP_STAGE`, or `ABORT` — the action the Replanner recommends after a stage failure.
- **History Entry**: A persisted record of a pipeline run including spec, stage results, logs, duration, and overall status.
- **Chain**: A sequential execution of multiple pipelines where failure in one stops the rest.
- **DAG Visualization**: The ReactFlow-based graph rendered in the frontend showing stage nodes, dependency edges, and live status colors.
- **StageUpdate**: A WebSocket message payload carrying `stage_id`, `status`, `log_type`, `log_message`, and optional fields like `deploy_url`, `recovery_strategy`.
- **GoalParser**: The NLP-based component that extracts cloud target, environment, region, and deployment strategy from a plain-English goal string.

---

## Requirements

### Requirement 1: Pipeline CRUD Operations

**User Story:** As a developer, I want to create, read, update, and delete pipelines, so that I can manage my deployment configurations over time.

#### Acceptance Criteria

1. WHEN a valid repository URL and goal are submitted to `POST /pipelines`, THE API SHALL clone the repository, analyze it, generate a `PipelineSpec`, persist it to the database, and return the full spec within 60 seconds.
2. WHEN `GET /pipelines` is called, THE API SHALL return a list of all persisted pipelines ordered by creation date descending, each including the pipeline spec, latest execution results, overall status, and duration.
3. WHEN `GET /pipelines/{pipeline_id}` is called with a valid ID, THE API SHALL return the full `PipelineSpec` for that pipeline.
4. IF `GET /pipelines/{pipeline_id}` is called with an unknown ID, THEN THE API SHALL return HTTP 404 with a descriptive error message.
5. WHEN `PATCH /pipelines/{pipeline_id}` is called with updated `name`, `goal`, or `stages`, THE API SHALL persist the changes and return the updated spec.
6. WHEN `DELETE /pipelines/{pipeline_id}` is called, THE API SHALL remove the pipeline and all associated stage results from the database and return HTTP 200.
7. IF `DELETE /pipelines/{pipeline_id}` is called with an unknown ID, THEN THE API SHALL return HTTP 404.
8. THE Frontend SHALL display a form allowing the user to enter a repository URL, deployment goal, optional name, and Docker toggle to create a pipeline.
9. WHEN a pipeline is created successfully, THE Frontend SHALL navigate to the pipeline detail view and display the generated DAG.
10. THE Frontend SHALL provide an edit interface allowing the user to modify pipeline name, goal, and individual stage commands.
11. WHEN the user triggers "Regenerate Pipeline", THE Frontend SHALL re-submit the original repo URL and goal to `POST /pipelines` and replace the current pipeline spec.

---

### Requirement 2: DAG Visualization

**User Story:** As a developer, I want to see a visual graph of my pipeline stages and their dependencies, so that I can understand execution order and identify bottlenecks.

#### Acceptance Criteria

1. THE DAG_Visualizer SHALL render each pipeline stage as a node in a directed acyclic graph using ReactFlow.
2. WHEN a pipeline spec is loaded, THE DAG_Visualizer SHALL compute a left-to-right layout using the Dagre algorithm and position nodes without overlaps.
3. THE DAG_Visualizer SHALL draw directed edges from each dependency stage to its dependent stage.
4. WHEN a stage status changes, THE DAG_Visualizer SHALL update the node color in real time: pending=gray, running=blue, success=green, failed=red, skipped=yellow.
5. WHEN the user clicks a stage node, THE DAG_Visualizer SHALL open the Stage Detail Panel for that stage.
6. IF a pipeline has no stages, THEN THE DAG_Visualizer SHALL display an empty state message.
7. THE DAG_Visualizer SHALL display the agent type label and stage ID on each node.

---

### Requirement 3: Pipeline Execution Engine

**User Story:** As a developer, I want to execute a pipeline and have stages run in the correct dependency order, so that my build, test, and deploy steps complete reliably.

#### Acceptance Criteria

1. WHEN `POST /pipelines/{pipeline_id}/execute` is called, THE Execution_Engine SHALL execute all pipeline stages in topological order respecting the DAG dependency graph.
2. WHEN multiple stages have no unresolved dependencies, THE Execution_Engine SHALL execute them concurrently using `asyncio.gather`.
3. WHEN a stage completes with exit code 0, THE Execution_Engine SHALL mark it `SUCCESS` and unblock its dependent stages.
4. WHEN a stage completes with a non-zero exit code, THE Execution_Engine SHALL mark it `FAILED` and invoke the Replanner before marking dependents `SKIPPED`.
5. WHEN a non-critical stage fails, THE Execution_Engine SHALL mark it `SKIPPED` and continue execution of independent stages.
6. WHEN all stages reach a terminal state (SUCCESS, FAILED, or SKIPPED), THE Execution_Engine SHALL compute the overall pipeline status and persist results to the database.
7. THE Execution_Engine SHALL enforce per-stage timeouts defined in `Stage.timeout_seconds` and mark timed-out stages as `FAILED`.
8. WHEN `spec.use_docker` is true, THE Execution_Engine SHALL run each stage command inside a Docker container using the appropriate language image.
9. IF the pipeline's `work_dir` is missing at execution time, THEN THE Execution_Engine SHALL re-clone the repository before executing.
10. THE Execution_Engine SHALL support parallel execution of multiple independent pipelines simultaneously without state interference.

---

### Requirement 4: Real-Time WebSocket Streaming

**User Story:** As a developer, I want to see live stage status updates and log output as my pipeline runs, so that I can monitor progress without polling.

#### Acceptance Criteria

1. WHEN a pipeline execution starts, THE WebSocket_Manager SHALL broadcast a `pipeline_start` event to all clients subscribed to that pipeline's channel.
2. WHEN a stage begins executing, THE WebSocket_Manager SHALL broadcast a `stage_start` event containing `stage_id`, `status: running`, and the first 80 characters of the command.
3. WHEN a stage produces stdout output, THE WebSocket_Manager SHALL broadcast a `stage_output` event containing the line text within 500ms of it being produced.
4. WHEN a stage completes successfully, THE WebSocket_Manager SHALL broadcast a `stage_success` event containing `stage_id`, `status: success`, and `duration_seconds`.
5. WHEN a stage fails, THE WebSocket_Manager SHALL broadcast a `stage_failed` event containing `stage_id`, `status: failed`, `exit_code`, and the last 200 characters of stderr.
6. WHEN the pipeline finishes, THE WebSocket_Manager SHALL broadcast a `pipeline_done` event containing overall status, counts of succeeded/failed/skipped stages, and goal achievement status.
7. THE Frontend WebSocket client SHALL reconnect automatically up to 3 times with a 2-second delay between attempts if the connection drops.
8. WHEN a `stage_output` event is received, THE Frontend SHALL append the line to the Execution Log panel in real time.
9. WHEN a `stage_success` or `stage_failed` event is received, THE Frontend SHALL update the corresponding DAG node color immediately.
10. WHEN a `deploy_url` field is present in a WebSocket event, THE Frontend SHALL display the URL as a clickable link in the status banner.

---

### Requirement 5: Recovery System

**User Story:** As a developer, I want the pipeline to automatically detect and fix common failures, so that I don't need to manually intervene for routine errors.

#### Acceptance Criteria

1. WHEN a stage fails, THE Replanner SHALL analyze the combined stdout and stderr output against the error pattern database to identify the failure category.
2. WHEN a `missing_dependency` pattern is detected, THE Replanner SHALL generate a `FIX_AND_RETRY` plan that prepends the appropriate package installation command to the original stage command.
3. WHEN a `permission_denied` pattern is detected, THE Replanner SHALL generate a `FIX_AND_RETRY` plan that prepends a `chmod` command to the original stage command.
4. WHEN a `port_in_use` pattern is detected at deploy time, THE Replanner SHALL generate a `FIX_AND_RETRY` plan that replaces the conflicting port with the next available free port.
5. WHEN a `wrong_entry_point` pattern is detected, THE Replanner SHALL generate a `FIX_AND_RETRY` plan that substitutes an alternative entry point file.
6. WHEN no known error pattern matches, THE Replanner SHALL generate an `ABORT` plan with a descriptive reason.
7. WHEN a `FIX_AND_RETRY` plan is executed and the retry succeeds, THE Execution_Engine SHALL mark the stage `SUCCESS` and continue the pipeline.
8. WHEN a `FIX_AND_RETRY` plan is executed and the retry also fails, THE Execution_Engine SHALL mark the stage `FAILED` and skip its dependents.
9. WHEN a `SKIP_STAGE` plan is selected for a non-critical stage, THE Execution_Engine SHALL mark the stage `SKIPPED` and continue.
10. WHEN a recovery plan is generated, THE WebSocket_Manager SHALL broadcast a `recovery_plan` event containing the strategy, reason, and modified command.
11. THE Frontend SHALL display the recovery plan details in the Stage Detail Panel when a recovery event is received.
12. WHEN a stage has `retry_count > 0`, THE Execution_Engine SHALL retry the original command up to that many times before invoking the Replanner.

---

### Requirement 6: Re-Run Failed Stages

**User Story:** As a developer, I want to re-run only the failed stages of a pipeline without re-running successful ones, so that I can fix issues quickly without wasting time.

#### Acceptance Criteria

1. WHEN `POST /pipelines/{pipeline_id}/execute-failed` is called, THE Execution_Engine SHALL reset all `FAILED` stages to `PENDING` and restore all `SUCCESS` and `SKIPPED` stages from the previous run.
2. WHEN failed stages are reset, THE Execution_Engine SHALL also reset any `SKIPPED` stages whose only failed dependency is now `PENDING`.
3. IF no failed stages exist for the pipeline, THEN THE API SHALL return HTTP 400 with the message "No failed stages to re-run".
4. THE Frontend SHALL display a "Re-run Failed" button when the pipeline has at least one failed stage.
5. WHEN the user clicks "Re-run Failed", THE Frontend SHALL call `POST /pipelines/{pipeline_id}/execute-failed` and resume real-time WebSocket updates.

---

### Requirement 7: Pipeline Chaining

**User Story:** As a developer, I want to chain multiple pipelines so that they execute sequentially, with each pipeline starting only after the previous one succeeds.

#### Acceptance Criteria

1. WHEN `POST /pipelines/{pipeline_id}/chain` is called with a list of pipeline IDs, THE Execution_Engine SHALL execute the pipelines sequentially in the order: trigger pipeline first, then each chained pipeline.
2. WHEN a pipeline in the chain fails, THE Execution_Engine SHALL stop the chain and not execute subsequent pipelines.
3. THE API SHALL return a `chain_results` map containing the status of each pipeline that was attempted.
4. THE Frontend SHALL provide a UI to select and chain multiple pipelines from the pipeline list.

---

### Requirement 8: Execution Logs Panel

**User Story:** As a developer, I want to see a persistent, searchable log of all pipeline events, so that I can debug failures and audit past runs.

#### Acceptance Criteria

1. THE Execution_Log_Panel SHALL display all log entries for the current pipeline run in chronological order.
2. WHEN a new log entry arrives via WebSocket, THE Execution_Log_Panel SHALL append it to the bottom and auto-scroll.
3. THE Execution_Log_Panel SHALL color-code entries by type: stage_output=white, stage_success=green, stage_failed=red, recovery_plan=orange, pipeline_done=blue.
4. THE Logs_Page SHALL display logs from all historical pipeline runs with search and filter capabilities.
5. WHEN the user searches in the Logs_Page, THE Logs_Page SHALL filter entries matching the search term in real time.
6. THE Logs_Page SHALL provide a download button that exports the filtered log entries as a plain-text file.
7. WHEN a pipeline run completes, THE Execution_Engine SHALL persist all log entries as part of the execution result so they survive page refresh.

---

### Requirement 9: Stage Detail Panel

**User Story:** As a developer, I want to inspect the full details of any stage, so that I can understand exactly what ran, what output was produced, and why it failed.

#### Acceptance Criteria

1. WHEN the user selects a stage (by clicking the DAG node or a list item), THE Stage_Detail_Panel SHALL display: stage ID, agent type, full command, status, exit code, duration, stdout, stderr, environment variables, and any recovery plan.
2. THE Stage_Detail_Panel SHALL update in real time as new stdout lines arrive for a running stage.
3. WHEN a recovery plan exists for the stage, THE Stage_Detail_Panel SHALL display the strategy, reason, and modified command.
4. THE Stage_Detail_Panel SHALL display the list of artifact paths produced by the stage.
5. WHEN no stage is selected, THE Stage_Detail_Panel SHALL be hidden or show an empty state.

---

### Requirement 10: Agent Activity Tracking

**User Story:** As a developer, I want to see which agents are active and what they are doing, so that I can understand system load and identify bottlenecks.

#### Acceptance Criteria

1. THE Agent_Activity_Panel SHALL display the current status of all 5 agents: Build, Test, Security, Deploy, Verify.
2. WHEN an agent is executing a stage, THE Agent_Activity_Panel SHALL show the agent as "active" with the current stage ID.
3. WHEN an agent is idle, THE Agent_Activity_Panel SHALL show the agent as "idle".
4. THE Agents_Page SHALL display historical metrics per agent: total stages executed, success rate, average duration.
5. THE Agent_Activity_Panel SHALL update in real time as WebSocket events arrive.

---

### Requirement 11: Dashboard

**User Story:** As a developer, I want a dashboard showing system health and recent activity, so that I can quickly assess the state of all my pipelines.

#### Acceptance Criteria

1. THE Dashboard SHALL display aggregate statistics: total pipelines, total runs, success rate, and average pipeline duration.
2. THE Dashboard SHALL display a list of the 5 most recently executed pipelines with their status, duration, and a link to the detail view.
3. THE Dashboard SHALL display the current health status of all 5 agents.
4. WHEN the page loads, THE Dashboard SHALL fetch fresh data from `GET /pipelines` and render within 2 seconds.
5. THE Dashboard SHALL display duration sparklines showing the trend of the last 10 runs for each pipeline.

---

### Requirement 12: Pipelines Page

**User Story:** As a developer, I want a dedicated page listing all my pipelines with filtering and history, so that I can manage and compare runs over time.

#### Acceptance Criteria

1. THE Pipelines_Page SHALL display all pipelines in a table or card list with columns: name, repo URL, goal, language, status, last run duration, and actions.
2. THE Pipelines_Page SHALL provide filter controls for status (success, failed, not_executed) and language.
3. WHEN the user applies a filter, THE Pipelines_Page SHALL update the list in real time without a page reload.
4. THE Pipelines_Page SHALL provide per-pipeline action buttons: Execute, Edit, Re-run Failed, Delete, and Chain.
5. THE Pipelines_Page SHALL display execution history for each pipeline showing the last N runs with status and duration.

---

### Requirement 13: Settings Page

**User Story:** As a developer, I want a settings page to configure my profile, API keys, and integrations, so that I can customize the system to my environment.

#### Acceptance Criteria

1. THE Settings_Page SHALL display a profile section allowing the user to update display name and email.
2. THE Settings_Page SHALL display an API keys section where the user can view, add, and revoke API keys for LLM providers (Gemini, Anthropic).
3. THE Settings_Page SHALL display an integrations section for configuring cloud provider credentials (AWS, Azure, GCP).
4. WHEN the user saves settings, THE Settings_Page SHALL persist the values and display a success confirmation.
5. THE Settings_Page SHALL mask sensitive values (API keys, secrets) in the display.

---

### Requirement 14: Browser Notifications and Auto-Open URL

**User Story:** As a developer, I want browser notifications when a pipeline completes and the deployed URL to open automatically, so that I can stay informed without watching the screen.

#### Acceptance Criteria

1. WHEN a pipeline completes successfully, THE Frontend SHALL send a browser notification with the pipeline name and "Deployment succeeded" message if the user has granted notification permission.
2. WHEN a pipeline fails, THE Frontend SHALL send a browser notification with the pipeline name and "Deployment failed" message.
3. WHEN a `deploy_url` is received in a WebSocket event, THE Frontend SHALL display the URL as a clickable link and offer a button to open it in a new tab.
4. WHERE the user has enabled "auto-open URL" in settings, THE Frontend SHALL automatically open the deployed URL in a new tab when a successful deploy event is received.

---

### Requirement 15: Execution History Persistence

**User Story:** As a developer, I want my pipeline execution history to persist across page refreshes and container restarts, so that I don't lose my run records.

#### Acceptance Criteria

1. WHEN a pipeline execution completes, THE Database SHALL persist the full `PipelineExecutionResult` including all stage results, stdout, stderr, duration, and overall status.
2. WHEN the frontend loads, THE Frontend SHALL fetch the execution history from `GET /pipelines` and restore the pipeline list.
3. WHEN the user navigates to a pipeline detail URL directly, THE Frontend SHALL fetch the pipeline spec from `GET /pipelines/{pipeline_id}` and restore the view.
4. THE Database SHALL retain execution history across container restarts using a persistent volume.
5. WHEN a pipeline is deleted, THE Database SHALL cascade-delete all associated stage results and deployment versions.

---

### Requirement 16: Artifact Passing Between Stages

**User Story:** As a developer, I want build artifacts to be automatically passed to downstream stages, so that the deploy stage can use the compiled output without rebuilding.

#### Acceptance Criteria

1. WHEN a stage completes successfully, THE Artifact_Store SHALL save any artifact paths found in the stage output to persistent storage keyed by `pipeline_id` and `stage_id`.
2. WHEN a downstream stage is about to execute, THE Execution_Engine SHALL inject artifact paths from all upstream stages as environment variables (`ARTIFACT_<STAGE_ID>_<INDEX>`).
3. WHEN a downstream stage is about to execute, THE Execution_Engine SHALL also inject upstream stage metadata as environment variables (`STAGE_<ID>_STATUS`, `STAGE_<ID>_EXIT_CODE`, `STAGE_<ID>_DURATION`).
4. THE Artifact_Store SHALL provide a cleanup mechanism to remove artifacts older than 24 hours.
5. THE Stage_Detail_Panel SHALL display the list of artifact paths produced by each stage.

---

### Requirement 17: Goal Parsing

**User Story:** As a developer, I want to describe my deployment goal in plain English and have the system extract the correct parameters, so that I don't need to learn a DSL.

#### Acceptance Criteria

1. WHEN a goal string is submitted, THE GoalParser SHALL extract: cloud target (aws, azure, gcp, local), environment (production, staging, development), region, and deployment strategy (rolling, blue-green, canary, recreate).
2. WHEN the goal contains no recognized cloud keyword, THE GoalParser SHALL default to `local` as the cloud target.
3. WHEN the goal contains no recognized environment keyword, THE GoalParser SHALL default to `staging` as the environment.
4. WHEN the goal contains conflicting cloud keywords (e.g., both "aws" and "azure"), THE GoalParser SHALL return `is_valid: false` with a descriptive error message.
5. THE `GET /parse-goal` endpoint SHALL return the parsed goal parameters as a JSON object.
6. FOR ALL valid goal strings, parsing the same string twice SHALL produce identical results (idempotence).

---

### Requirement 18: Deployment Versioning and Rollback

**User Story:** As a developer, I want to roll back a failed deployment to the previous successful version, so that I can recover quickly from bad releases.

#### Acceptance Criteria

1. WHEN a deploy stage completes successfully, THE Execution_Engine SHALL create a `DeploymentVersion` record with version ID, timestamp, image/artifact reference, environment, and status.
2. WHEN `POST /pipelines/{pipeline_id}/rollback` is called, THE API SHALL identify the most recent successful deployment version and initiate a rollback.
3. WHEN a specific `to_version` query parameter is provided, THE API SHALL roll back to that exact version.
4. IF no previous successful deployment version exists, THEN THE API SHALL return HTTP 404 with the message "No previous deployment version found to rollback to".
5. WHEN a rollback completes, THE API SHALL update the deployment version status to `rolled_back` and return the version details.
6. THE `GET /pipelines/{pipeline_id}/deployment-history` endpoint SHALL return the list of deployment versions ordered by timestamp descending.

---

### Requirement 19: Automated Test Suite — Unit Tests

**User Story:** As a QA engineer, I want a comprehensive unit test suite covering all backend components, so that regressions are caught immediately.

#### Acceptance Criteria

1. THE Unit_Test_Suite SHALL include tests for `DAGScheduler`: verify topological ordering, cycle detection, `get_ready_stages`, `mark_complete`, `skip_dependents`, and `reset_failed_stages`.
2. THE Unit_Test_Suite SHALL include tests for `GoalParser`: verify extraction of cloud, environment, region, strategy, and validation for all supported input patterns.
3. THE Unit_Test_Suite SHALL include tests for `error_patterns`: verify each error pattern regex matches its target strings and does not match unrelated strings.
4. THE Unit_Test_Suite SHALL include tests for `ArtifactStore`: verify save, retrieve, upstream collection, and cleanup operations.
5. THE Unit_Test_Suite SHALL include tests for `ConnectionManager`: verify connect, disconnect, broadcast, and dead-connection cleanup.
6. THE Unit_Test_Suite SHALL include tests for `extract_deploy_url`: verify URL extraction from stdout, stderr, and command strings for all supported port patterns.
7. THE Unit_Test_Suite SHALL include tests for `DeploymentVersion` model: verify serialization, deserialization, and field defaults.
8. FOR ALL parser and serializer components, THE Unit_Test_Suite SHALL include a round-trip property test: `parse(serialize(x)) == x`.

---

### Requirement 20: Automated Test Suite — Integration Tests

**User Story:** As a QA engineer, I want integration tests that verify the backend API endpoints and execution engine work correctly end-to-end, so that component interactions are validated.

#### Acceptance Criteria

1. THE Integration_Test_Suite SHALL include tests for `POST /pipelines` that verify a pipeline is created, persisted, and returned with correct stages for a known repository.
2. THE Integration_Test_Suite SHALL include tests for `POST /pipelines/{pipeline_id}/execute` that verify stages execute in dependency order and results are persisted.
3. THE Integration_Test_Suite SHALL include tests for `POST /pipelines/{pipeline_id}/execute-failed` that verify only failed stages are re-run and successful stages are preserved.
4. THE Integration_Test_Suite SHALL include tests for `POST /pipelines/{pipeline_id}/chain` that verify sequential execution and chain-stop-on-failure behavior.
5. THE Integration_Test_Suite SHALL include tests for `POST /pipelines/{pipeline_id}/rollback` that verify rollback to the most recent and a specific version.
6. THE Integration_Test_Suite SHALL include tests for the WebSocket endpoint that verify `stage_start`, `stage_success`, `stage_failed`, and `pipeline_done` events are broadcast in the correct order.
7. THE Integration_Test_Suite SHALL include tests for the recovery system that inject known error patterns into stage output and verify the correct `RecoveryPlan` is generated.
8. THE Integration_Test_Suite SHALL include tests for concurrent pipeline execution that verify two pipelines running simultaneously do not interfere with each other's state.
9. THE Integration_Test_Suite SHALL include tests for edge cases: invalid repo URL, empty stage list, circular dependency detection, and missing pipeline ID.

---

### Requirement 21: Automated Test Suite — End-to-End Tests

**User Story:** As a QA engineer, I want end-to-end tests that simulate real user flows through the UI, so that the full frontend-to-backend integration is validated.

#### Acceptance Criteria

1. THE E2E_Test_Suite SHALL include a test that creates a pipeline via the UI form, verifies the DAG renders, executes the pipeline, and confirms the status banner shows success or failure.
2. THE E2E_Test_Suite SHALL include a test that verifies real-time WebSocket log lines appear in the Execution Log panel during pipeline execution.
3. THE E2E_Test_Suite SHALL include a test that verifies the Stage Detail Panel shows correct stdout, stderr, and duration after a stage completes.
4. THE E2E_Test_Suite SHALL include a test that verifies the "Re-run Failed" button appears after a failure and triggers re-execution of only failed stages.
5. THE E2E_Test_Suite SHALL include a test that verifies the Dashboard displays updated statistics after a pipeline run completes.
6. THE E2E_Test_Suite SHALL include a test that verifies pipeline deletion removes the entry from the Pipelines Page.
7. THE E2E_Test_Suite SHALL include a test that verifies the Logs Page search filter correctly narrows displayed log entries.
8. THE E2E_Test_Suite SHALL include a test that verifies browser notification permission is requested and a notification is sent on pipeline completion.
9. THE E2E_Test_Suite SHALL include a test for the edit pipeline flow: modify a stage command, save, re-execute, and verify the new command was used.
10. THE E2E_Test_Suite SHALL include a test for pipeline chaining: chain two pipelines, verify sequential execution, and verify the chain stops if the first pipeline fails.

---

### Requirement 22: Error Handling and Edge Cases

**User Story:** As a developer, I want the system to handle invalid inputs and unexpected failures gracefully, so that errors are informative and the system remains stable.

#### Acceptance Criteria

1. WHEN an invalid or unreachable repository URL is submitted, THE API SHALL return HTTP 422 or 500 with a descriptive error message within 30 seconds.
2. WHEN a pipeline execution encounters an unhandled exception in a stage, THE Execution_Engine SHALL catch the exception, mark the stage `FAILED`, and continue processing other independent stages.
3. WHEN the database is unavailable, THE API SHALL return HTTP 503 with a "Service unavailable" message.
4. WHEN a WebSocket client disconnects mid-execution, THE WebSocket_Manager SHALL remove the dead connection and continue broadcasting to remaining clients.
5. IF a stage command produces no output for longer than its `timeout_seconds`, THEN THE Execution_Engine SHALL terminate the process and mark the stage `FAILED` with a timeout error message.
6. WHEN the frontend receives a WebSocket message that cannot be parsed as JSON, THE Frontend SHALL log a warning and continue without crashing.
7. WHEN `POST /pipelines` is called with an empty goal string, THE API SHALL return HTTP 422 with a validation error.
8. WHEN a pipeline spec contains a stage that depends on a non-existent stage ID, THE DAGScheduler SHALL raise a `ValueError` and THE API SHALL return HTTP 422.
