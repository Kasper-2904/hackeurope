# M3-T4 Review Agent Prompt - Billing & Settings Risk Review

## Mission
Perform a PR-style review of M3-T4 changes with focus on correctness, regressions, and missing tests.

Scope for this run: **M3-T4-ST9**.

## Review context
M3-T4 goal: workspace billing/settings UI with Stripe checkout trigger and Paid.ai cost visibility.

Expected touched areas:
- Backend billing endpoints/schemas (`backend/src/api/billing.py`, billing schemas)
- Billing aggregation queries over usage records
- Frontend billing page + API client + route/nav wiring
- Backend and frontend tests for billing flows
- `TASKS.md` status updates for completed M3-T4 subtasks

## Review checklist
1. Contract correctness
- Endpoint paths and payloads are consistent between backend and frontend.
- Error response behavior is deterministic and user-actionable.

2. Authorization/security
- Team ownership checks are enforced on all billing summary and subscribe actions.
- No accidental cross-team data exposure in usage/cost responses.

3. Data correctness
- Usage/cost aggregation logic is accurate and stable for empty/noisy data.
- Sorting/limits for recent usage are reasonable.

4. UI behavior
- Billing page handles loading, empty, success, and error states.
- Subscribe flow cannot be triggered without valid team selection.
- Redirect behavior uses returned checkout URL correctly.

5. Regression risk
- Existing routes/pages (projects, PM dashboard, marketplace) remain unaffected.
- Existing tests continue to pass.

6. Test adequacy
- Backend tests cover happy + auth + failure paths.
- Frontend tests cover interaction and state transitions.

## Output format (mandatory)
1. Findings first, ordered by severity:
- `High` / `Medium` / `Low`
- include file reference and line when possible
- explain user impact and recommended fix
2. Open questions/assumptions
3. Brief change summary
4. Quality gate status:
- `cd backend && .venv/bin/pytest`
- `cd frontend && npm run lint && npm run build && npm run test`

If no findings, state that explicitly and still list residual risks/testing gaps.
