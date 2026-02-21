# M3-T4 Test Agent Prompt - Billing & Settings Coverage

## Mission
Add or improve tests for the M3-T4 Billing & Settings implementation, following `TESTING.md` requirements:
- Happy path
- Error/validation path
- Authorization path (when relevant)

Scope for this run: **M3-T4-ST7 and M3-T4-ST8**.

## Expected implementation context
M3-T4 introduces:
- Backend billing summary endpoint (team-owner scoped).
- Hardened subscribe endpoint behavior.
- Frontend billing/settings page with:
  - workspace selection,
  - subscribe CTA,
  - usage dashboard rendering,
  - loading/empty/error states.

## Backend test targets
Primary location: `backend/tests/api/`

Add tests for:
1. Billing summary endpoint (`GET /billing/summary/{team_id}`):
- success for team owner with usage data;
- success with no usage records (empty state payload);
- unauthorized/forbidden access to another owner team (expect 404/403 per implementation contract);
- stable response shape for UI.

2. Subscribe endpoint (`POST /billing/subscribe`):
- owner happy path returns checkout URL payload;
- unknown team / non-owner path returns correct error;
- service failure path returns deterministic error response.

Implementation hints:
- Reuse dependency override pattern from `backend/tests/api/test_pm_dashboard.py`.
- Mock/patch Stripe service calls; do not call external APIs.

## Frontend test targets
Primary location: `frontend/src/pages/` and/or `frontend/src/lib/` tests.

Add tests for Billing UI:
1. Renders team selector + subscribe CTA + usage widgets on success.
2. Subscribe click triggers API call and redirect behavior (mock `window.location.assign` or equivalent).
3. Shows API error message for failed subscribe.
4. Handles summary empty state (no usage).
5. Handles loading and fetch error states for summary query.

Implementation hints:
- Follow existing page test style (`TaskDetailPage.test.tsx`, `ProjectDetailPage.test.tsx`).
- Mock API module methods and auth context as needed.

## Constraints
- Keep tests deterministic and isolated.
- No network calls.
- Avoid brittle assertions tied to implementation internals.

## Required task updates
- Mark these subtasks `Done` in `TASKS.md` when fully complete:
  - `M3-T4-ST7`
  - `M3-T4-ST8`
- Add one concise note listing test files added/updated and commands run.

## Execution commands
- Backend tests: `cd backend && .venv/bin/pytest`
- Frontend quality/tests: `cd frontend && npm run lint && npm run build && npm run test`

## Output format
Return:
1. Added/updated tests by file.
2. Coverage matrix: happy/error/auth paths.
3. Commands run + pass/fail.
4. Remaining gaps (if any).
