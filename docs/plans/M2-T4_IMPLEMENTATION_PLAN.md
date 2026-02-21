# M2-T4 Implementation Plan: PM Dashboard UI

## Scope
- Task: `M2-T4 PM Dashboard UI`
- Owner: Marin
- Source of truth: `TASKS.md`, `PROJECT_SPEC.md`, `ARCHITECTURE.md`, `TESTING.md`, `AGENTS.md`
- Goal:
  - PM can manage project agent allowlist.
  - PM can review and approve OA plans.

## Subtasks
1. `M2-T4-ST1` PM information architecture and routing
- Define PM-facing routes and page boundaries for project overview, plan approvals, and agent allowlist.
- Replace M2-T4 placeholders in existing routes with concrete page components.
- Keep routing aligned with authenticated shell behavior from M1-T4.

2. `M2-T4-ST2` Backend support for project agent allowlist
- Add persistent model for project-level agent allowlist (project + agent mapping).
- Add API endpoints to list, add, and remove allowed agents for a project.
- Enforce project ownership/authorization and prevent duplicate allowlist entries.

3. `M2-T4-ST3` PM dashboard API readiness
- Extend PM dashboard payload where needed to expose allowlist and plan-approval context.
- Keep existing API contracts stable where possible; document any necessary contract changes.
- Ensure dashboard data supports goals, milestones, timeline, team progress, risks, and pending approvals.

4. `M2-T4-ST4` Frontend API layer for PM workflows
- Implement typed API functions for PM dashboard fetch, allowlist management, and plan approve/reject actions.
- Normalize backend errors for UI display using existing API error patterns.
- Keep API functions scoped to M2-T4 features only.

5. `M2-T4-ST5` PM dashboard UI implementation
- Build PM dashboard views for:
  - Project goals/progress/timeline summary
  - Team member workload/progress snapshot
  - OA plans pending PM decision with approve/reject actions
  - Project agent allowlist management controls
- Include loading, empty, and error states.

6. `M2-T4-ST6` PM approval gate interactions
- Add approve/reject UI flows with explicit confirmation and rejection reason input.
- Update local/query state after actions to reflect latest plan statuses.
- Surface auditable feedback in UI (e.g., approved/rejected state and timestamps if available).

7. `M2-T4-ST7` Backend unit/API tests
- Cover allowlist endpoints:
  - happy path list/add/remove
  - validation/duplicate-path failures
  - authorization/project ownership checks
- Cover PM plan approval/rejection endpoint behavior and error paths relevant to dashboard actions.

8. `M2-T4-ST8` Frontend unit/component tests
- Cover PM dashboard rendering with success, loading, and error states.
- Cover allowlist interaction flows (add/remove + optimistic/update behavior).
- Cover plan approval/rejection UI interactions, including rejection-reason validation.

9. `M2-T4-ST9` Quality gates and handoff
- Backend: run `cd backend && pytest`.
- Frontend: run `cd frontend && npm run lint && npm run build && npm run test`.
- Document exact commands run, failing checks (if any), and residual risks/open questions.

## Agent Assignment
- Feature Agent: `M2-T4-ST1` to `M2-T4-ST6`
- Test Agent: `M2-T4-ST7` to `M2-T4-ST8`
- Review Agent: Validate all subtasks with focus on approval-gate correctness, allowlist governance, and regressions.

## Completion Checklist
- All M2-T4 subtasks above are completed in this branch.
- `TASKS.md` is only updated for M2-T4 status/notes when acceptance criteria are fully met.
- Tests are added/updated per `TESTING.md` standards.
- PR summary includes: changes, tests, risks/open questions.
