# Tasks

## Milestone 1: Shared Context and Platform Contracts

### M1-T1 Define shared context schema and markdown contracts (owner: Marin)
- Status: Todo
- Description: Finalize schemas and canonical markdown file structure under `docs/shared_context/`.
- Acceptance Criteria:
  - All required shared-context `.md` files exist with documented sections.
  - Schema fields map cleanly to API models.
- Test Strategy:
  - Unit tests for schema validation.
  - Doc structure validation test.

### M1-T2 Implement GitHub ingestion adapter (owner: Kasper)
- Status: Todo
- Description: Build connector and normalization for GitHub task/PR/CI context.
- Acceptance Criteria:
  - Ingestion jobs fetch and normalize core GitHub entities.
  - Adapter failures are retried and surfaced.
- Test Strategy:
  - Integration tests with mocked GitHub responses.

### M1-T3 Implement local-agent registry + lifecycle metadata (owner: Martin)
- Status: Todo
- Description: Build API/storage for local-agent registration, capabilities, version, and heartbeat.
- Acceptance Criteria:
  - Local agent can be registered/listed per team member.
  - Capability/status metadata is queryable by OA.
- Test Strategy:
  - Integration tests for register/list/update/error paths.

### M1-T4 Define PM approval workflow and plan versioning (owner: Farhan)
- Status: Todo
- Description: Implement plan states (`draft`, `pending_pm_approval`, `approved`, `rejected`) and version history.
- Acceptance Criteria:
  - OA plan cannot execute before PM approval.
  - Approval/rejection actions are audited.
- Test Strategy:
  - Unit + integration tests for state transitions and audit records.

## Milestone 2: Orchestration, Sync, and Review Gate

### M2-T1 Build OA planning engine with local-agent capability checks (owner: Marin)
- Status: Todo
- Description: OA creates assignment plan using shared context and local-agent capability queries.
- Acceptance Criteria:
  - OA outputs assignee + local-agent mapping per subtask.
  - Plan includes rationale for each assignment.
- Test Strategy:
  - Unit tests for planning constraints.
  - Integration tests for capability query fallback behavior.

### M2-T2 Implement two-way local sync API and daemon contract (owner: Kasper)
- Status: Todo
- Description: Define/implement outbound local events and inbound assignment update protocol.
- Acceptance Criteria:
  - Local approvals/completions update platform state.
  - Idempotency/version conflict handling works (`409` recovery path).
- Test Strategy:
  - Integration tests for event ordering, replay, and conflict resolution.

### M2-T3 Implement final reviewer gate (owner: Martin)
- Status: Todo
- Description: Add final all-subtasks-submitted review stage with blocker/non-blocker findings.
- Acceptance Criteria:
  - Reviewer runs only when subtasks are complete.
  - Final review produces merge-readiness decision and rationale.
- Test Strategy:
  - End-to-end tests for pass and block scenarios.

### M2-T4 Implement local-agent draft handoff and developer finalize flow (owner: Farhan)
- Status: Todo
- Description: Connect approved assignments to local-agent drafts and developer finalize actions.
- Acceptance Criteria:
  - Developers can view draft, edit, and finalize subtask.
  - Finalize action emits sync event and updates platform context.
- Test Strategy:
  - Integration tests for draft lifecycle and sync propagation.

## Milestone 3: Dashboard Experiences

### M3-T1 Developer dashboard: task list + detail panel + risk graph (owner: Kasper)
- Status: Todo
- Description: Build developer UI with task list/sub-actions and detail panel for agents/progress/errors/risks.
- Acceptance Criteria:
  - Selecting a task updates detail panel with required data.
  - Risk/progress visualization is present and readable.
- Test Strategy:
  - Component tests and e2e task navigation.

### M3-T2 Developer big-context view (owner: Martin)
- Status: Todo
- Description: Build project-wide context mode (other tasks, agent allocations, project description, timeline).
- Acceptance Criteria:
  - Developer can toggle into big-context mode.
  - Cross-team task/agent context is visible and filterable.
- Test Strategy:
  - Component tests for filters/sections.
  - E2E toggle/navigation test.

### M3-T3 PM macro dashboard (owner: Farhan)
- Status: Todo
- Description: Build PM view with goals, milestones, timeline, team progress, task stages, and final-review findings.
- Acceptance Criteria:
  - PM sees project health summary and critical items at a glance.
  - PM can navigate to plan approval and final-review decisions.
- Test Strategy:
  - Component tests and E2E PM approval/review flow.

### M3-T4 Shared context explorer and explainability UI (owner: Marin)
- Status: Todo
- Description: Build views for shared context entities and OA/Reviewer rationale traces.
- Acceptance Criteria:
  - OA/Reviewer decisions show explainable factors.
  - Users can inspect linked team/agent/task context.
- Test Strategy:
  - Component tests for rationale rendering.
  - Integration tests for context retrieval.

## Milestone 4: Integration and Demo Readiness

### M4-T1 Cross-module integration and contract stabilization (owner: Marin)
- Status: Todo
- Description: Align APIs/schemas across ingestion, planning, sync, reviewer, and dashboards.
- Acceptance Criteria:
  - No schema mismatch across modules.
  - Full workflow runs without manual patching.
- Test Strategy:
  - End-to-end full-flow tests from task submission to final review.

### M4-T2 Performance and reliability hardening (owner: Kasper)
- Status: Todo
- Description: Improve latency, retries, and degraded-mode behavior.
- Acceptance Criteria:
  - p95 dashboard API target met.
  - Source outage handling is visible and non-fatal.
- Test Strategy:
  - Load smoke tests and fault-injection integration tests.

### M4-T3 Security, roles, and audit completeness (owner: Martin)
- Status: Todo
- Description: Finalize role checks and audit trails across PM/dev/admin actions.
- Acceptance Criteria:
  - Unauthorized actions are blocked.
  - Approval/review/sync-critical events are auditable.
- Test Strategy:
  - Integration tests for role matrix and audit assertions.

### M4-T4 QA, demo script, and release checklist (owner: Farhan)
- Status: Todo
- Description: Prepare final QA pass, demo runbook, and launch checklist.
- Acceptance Criteria:
  - Demo scenario is reproducible.
  - Known risks and mitigations are documented.
- Test Strategy:
  - Full regression run and scripted dry-run rehearsal.

## Parallelization Plan (Team of 4)
- Kasper track: GitHub ingestion + two-way sync contract + developer dashboard + reliability.
- Martin track: local-agent registry + final reviewer gate + big-context UI + security/audit.
- Farhan track: PM approval workflow + draft handoff + PM dashboard + QA/demo.
- Marin track: shared schema/docs + OA planning + explainability/context explorer + integration stabilization.
