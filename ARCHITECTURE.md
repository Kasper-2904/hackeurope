# Architecture

## Overview
Monorepo architecture with a web app, Python API, shared context store, OA planning engine, reviewer final-gate engine, and adapters for GitHub/local agents.

## Technology Choices
- Backend: Python service(s)
- Frontend: React
- Agent orchestration SDK: Claude SDK
- UI prototyping/acceleration: Lovable (handoff into React codebase)

## Core Components
- `apps/web`: developer and PM dashboards (React).
- `apps/api`: Python API for ingestion, planning, approvals, sync, and final review.
- `packages/shared-context`: schemas and services for shared context documents.
- `packages/orchestrator-core`: OA planning, assignment, explainability.
- `packages/reviewer-core`: final whole-task review and merge-readiness scoring.
- `packages/integrations`: GitHub adapter + local-agent registry/sync adapter.
- `packages/shared`: shared types, validation, auth helpers, constants.

## Shared Context Files (Canonical)
- `docs/shared_context/PROJECT_OVERVIEW.md`
- `docs/shared_context/TEAM_MEMBERS.md`
- `docs/shared_context/LOCAL_AGENTS.md`
- `docs/shared_context/PROJECT_PLAN.md`
- `docs/shared_context/TEAM_CONTEXT.md`
- `docs/shared_context/TASK_GRAPH.md`
- `docs/shared_context/INTEGRATIONS_GITHUB.md`

## Shared Context Schema (MVP)
- `Project`: description, goals, milestones, timeline.
- `TeamMember`: role, skills, capacity, current assignments.
- `LocalAgent`: owner, capabilities summary, version, status, heartbeat.
- `Task`: status, dependencies, priority, plan version, approvals.
- `Subtask`: assignee, assigned local agent, draft status, sync status.
- `ReviewResult`: blocker/non-blocker findings, rationale, readiness decision.

## Two-Way Local Sync Architecture (MVP)
1. Local Sync Daemon runs beside local agent on developer machine.
2. Daemon pulls platform updates:
- assignments
- task/subtask status changes
- plan version changes
3. Daemon pushes local events:
- draft created/updated
- developer approved draft
- subtask completed
4. Sync API enforces:
- `event_id` + idempotency key
- `event_version` ordering
- optimistic concurrency (`409` + latest state on conflict)
5. Reconciliation job periodically checks local/platform drift and repairs state.

## Workflow Architecture
1. `Task Submitted` event enters API.
2. OA reads shared context and builds initial plan.
3. OA optionally queries local-agent capability endpoints.
4. Plan enters PM approval state.
5. On approval, assignments are activated and distributed.
6. Local agents generate drafts; developers finalize subtasks.
7. Reviewer Agent runs final gate once all subtasks are complete.

## UI Architecture
- Developer view:
  - left: task list
  - center/right: task detail panel (agents, progress, risks, errors, action items)
  - big-context mode for project-wide visibility
- PM view:
  - project overview with goals/milestones/timeline/GitHub
  - team progress and task-stage overview
  - final review findings and critical risks

## API Surface (MVP)
- `POST /api/v1/tasks`
- `GET /api/v1/tasks/{id}`
- `POST /api/v1/plans/generate`
- `POST /api/v1/plans/{id}/approve`
- `POST /api/v1/plans/{id}/reject`
- `POST /api/v1/local-agents/register`
- `GET /api/v1/sync/assignments/{developer_id}`
- `POST /api/v1/sync/events`
- `POST /api/v1/reviewer/finalize/{task_id}`
- `GET /api/v1/dashboard/developer/{user_id}`
- `GET /api/v1/dashboard/pm/{project_id}`

## Data and Storage
- Primary DB for normalized context and workflow state.
- Event log for approvals, plan updates, sync events, reviewer findings.
- Local-agent metadata store for capability/status/version data.

## Non-Functional Design Choices
- Deterministic validation around Claude SDK outputs.
- Strict role-based authorization for PM/developer/admin actions.
- Full audit trail for approvals, sync updates, and reviewer decisions.
- No real-time reviewer loop in MVP; reviewer runs at finalization stage.

## Repository Layout
- `apps/web`
- `apps/api`
- `packages/shared-context`
- `packages/orchestrator-core`
- `packages/reviewer-core`
- `packages/integrations`
- `packages/shared`
- `docs/shared_context`
- `tests/unit`
- `tests/integration`
- `tests/e2e`
