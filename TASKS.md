# Tasks

## Milestone 1: Shared Context and Planning Foundation

### M1-T1 Define shared context schema and contracts (owner: Marin)
- Status: Todo
- Description: Finalize schema for project/team/member/local-agent/task/subtask/risk entities.
- Acceptance Criteria:
  - Shared context schema documented and validated.
  - Required fields for PM/OA/Reviewer flows are present.
- Test Strategy:
  - Unit tests for schema validation and required-field enforcement.

### M1-T2 Implement GitHub and Miro ingestion adapters (owner: Kasper)
- Status: Todo
- Description: Build connectors and normalization for GitHub + Miro data.
- Acceptance Criteria:
  - Ingestion jobs can fetch and normalize core entities.
  - Adapter failures are retried and surfaced.
- Test Strategy:
  - Integration tests with mocked provider responses.

### M1-T3 Implement local-agent registry and upload flow (owner: Martin)
- Status: Todo
- Description: Build API/storage for local-agent registration, capability summary, and context-file links.
- Acceptance Criteria:
  - Local agent can be registered and listed per team member.
  - Capability and context references are queryable by OA.
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

## Milestone 2: Orchestration and Reviewer Intelligence

### M2-T1 Build OA planning engine with local-agent capability checks (owner: Marin)
- Status: Todo
- Description: OA creates assignment plan using shared context and optional local-agent context queries.
- Acceptance Criteria:
  - OA outputs assignee + local-agent mapping per subtask.
  - Plan includes rationale for every assignment.
- Test Strategy:
  - Unit tests for planning logic and constraint handling.
  - Integration tests for local-agent query fallbacks.

### M2-T2 Implement Reviewer Agent real-time monitoring (owner: Kasper)
- Status: Todo
- Description: Stream project events and compute merge/CI/integration risk signals continuously.
- Acceptance Criteria:
  - High-risk conditions are emitted with severity and rationale.
  - PM and developers can view risk updates near real time.
- Test Strategy:
  - Integration tests for event-to-risk pipeline and alert generation.

### M2-T3 Implement final reviewer pre-merge gate (owner: Martin)
- Status: Todo
- Description: Add final all-subtasks-submitted review stage with actionable findings.
- Acceptance Criteria:
  - Final review runs only when subtasks are complete.
  - Findings include blocker/non-blocker classification.
- Test Strategy:
  - End-to-end tests for successful and blocked finalize flows.

### M2-T4 Implement local-agent draft handoff to developers (owner: Farhan)
- Status: Todo
- Description: Connect approved assignments to local-agent drafts and developer finalize actions.
- Acceptance Criteria:
  - Developers can view draft, edit, and mark subtask finalized.
  - Draft provenance (agent + timestamp + version) is stored.
- Test Strategy:
  - Integration tests for draft lifecycle and finalization actions.

## Milestone 3: Dashboard Experiences

### M3-T1 Developer dashboard: task list + detail panel + risk graph (owner: Kasper)
- Status: Todo
- Description: Build developer UI with task list/sub-actions and detail panel showing assigned agents, progress, errors, and risks.
- Acceptance Criteria:
  - Selecting a task updates detail panel with required data.
  - Risk/progress visualization is present and readable.
- Test Strategy:
  - Component tests for state rendering and interaction.
  - E2E happy-path for task navigation.

### M3-T2 Developer big-context view (owner: Martin)
- Status: Todo
- Description: Build project-wide context mode (other tasks, who/what agent is working on what, project description, past timeline).
- Acceptance Criteria:
  - Developer can toggle into big-context mode.
  - Cross-team task/agent context is visible and filterable.
- Test Strategy:
  - Component tests for filters and context sections.
  - E2E toggle/navigation test.

### M3-T3 PM macro dashboard (owner: Farhan)
- Status: Todo
- Description: Build PM view with projects, goals, milestones, timeline, GitHub linkages, team members, task stages, progress, and critical alerts.
- Acceptance Criteria:
  - PM sees project health summary and critical items at a glance.
  - PM can navigate to plan approvals and risk details.
- Test Strategy:
  - Component tests for overview cards and alert board.
  - E2E PM flow for approve/reject + risk follow-up.

### M3-T4 Shared context explorer and explainability UI (owner: Marin)
- Status: Todo
- Description: Build views for shared context entities and rationale traces from OA/Reviewer decisions.
- Acceptance Criteria:
  - OA/Reviewer decisions show explainable factors.
  - Users can inspect relevant team/agent/task context links.
- Test Strategy:
  - Component tests for rationale rendering.
  - Integration tests for context-link retrieval.

## Milestone 4: Integration, Hardening, and Demo Readiness

### M4-T1 Cross-module integration and contract stabilization (owner: Marin)
- Status: Todo
- Description: Align APIs/schemas across ingestion, planning, reviewer, and dashboards.
- Acceptance Criteria:
  - No schema mismatch across modules.
  - Core workflows execute without manual data patching.
- Test Strategy:
  - End-to-end full flow tests from task submission to final review.

### M4-T2 Performance and reliability hardening (owner: Kasper)
- Status: Todo
- Description: Improve latency, retries, and degraded-mode behavior.
- Acceptance Criteria:
  - p95 dashboard API latency target met.
  - Source outage handling is visible and non-fatal.
- Test Strategy:
  - Load smoke tests and fault-injection integration tests.

### M4-T3 Security, roles, and audit completeness (owner: Martin)
- Status: Todo
- Description: Finalize role checks and audit trails across PM/dev/admin actions.
- Acceptance Criteria:
  - Unauthorized actions are blocked.
  - Approval/review critical events are auditable.
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
- Kasper track: ingestion adapters + reviewer real-time + developer dashboard + reliability.
- Martin track: local-agent registry + final reviewer gate + big-context UI + security/audit.
- Farhan track: PM approval workflow + draft handoff + PM dashboard + QA/demo.
- Marin track: shared schema + OA planning + explainability/context explorer + integration stabilization.
