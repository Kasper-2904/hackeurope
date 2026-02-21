# Architecture

## Overview
Monorepo architecture with a web app, orchestration API, shared context store, OA planning engine, reviewer engine, and adapters for GitHub/Miro/local agents.

## Core Components
- `apps/web`: UI for developer and PM dashboards.
- `apps/api`: API layer for ingestion, planning, approvals, execution, and monitoring.
- `packages/shared-context`: schemas and services for structured project context.
- `packages/orchestrator-core`: OA planning, assignment, and explainability logic.
- `packages/reviewer-core`: real-time and final-review risk analysis (merge/CI/integration).
- `packages/integrations`: adapters for GitHub, Miro, and local-agent registry/runtime.
- `packages/shared`: shared types, validation, auth helpers, constants.

## Shared Context Schema (MVP)
- `Project`: description, goals, milestones, timeline, external links.
- `TeamMember`: role, skills, capacity, current assignments.
- `LocalAgent`: owner, capabilities summary, context file refs, availability.
- `Task`: status, dependencies, priority, plan version, approvals.
- `Subtask`: assignee, assigned local agent, draft status, risk flags.
- `RiskSignal`: source, severity, rationale, recommended action.

## Workflow Architecture
1. `Task Submitted` event enters API.
2. OA reads shared context and builds initial plan.
3. OA optionally queries local-agent capability/context endpoints.
4. Plan enters PM approval state.
5. On approval, assignments are activated.
6. Local agents generate drafts for human assignees.
7. Humans finalize subtasks.
8. Reviewer Agent monitors events continuously and runs final gate on completion.

## UI Architecture
- Developer view:
  - left: task list
  - center/right: selected-task detail panel (agents, progress, risks, errors, action items)
  - big-context mode for full project visibility
- PM view:
  - project portfolio card(s) with goals/milestones/timeline/GitHub
  - team progress and task-stage overview
  - critical alerts and risk board

## API Surface (MVP)
- `POST /api/v1/tasks`
- `GET /api/v1/tasks/{id}`
- `POST /api/v1/plans/generate`
- `POST /api/v1/plans/{id}/approve`
- `POST /api/v1/plans/{id}/reject`
- `POST /api/v1/local-agents/register`
- `GET /api/v1/dashboard/developer/{user_id}`
- `GET /api/v1/dashboard/pm/{project_id}`
- `GET /api/v1/reviewer/risks/{project_id}`

## Data and Storage
- Primary DB for normalized context and workflow state.
- Event log for approvals, plan updates, assignment changes, and reviewer findings.
- Local-agent artifact metadata store (manifest/capability references).

## Non-Functional Design Choices
- Event-driven updates for near-real-time risk detection.
- Deterministic validation layer around LLM outputs.
- Strict role-based authorization for PM/developer/admin actions.
- Full audit trail for compliance and explainability.

## Repository Layout
- `apps/web`
- `apps/api`
- `packages/shared-context`
- `packages/orchestrator-core`
- `packages/reviewer-core`
- `packages/integrations`
- `packages/shared`
- `tests/unit`
- `tests/integration`
- `tests/e2e`
