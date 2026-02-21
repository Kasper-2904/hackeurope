# M3-T4 Feature Agent Prompt - Billing & Settings UI

## Mission
Implement M3-T4 functional behavior for Billing & Settings UI, aligned with `PROJECT_SPEC.md`, `ARCHITECTURE.md`, `AGENTS.md`, and `TESTING.md`.

Scope for this run: **M3-T4-ST1 through M3-T4-ST6** only.

## Current repo reality (must use)
- Frontend billing route is a placeholder in `frontend/src/App.tsx`:
  - `/billing` currently renders `<div>Billing - Marin M3-T4</div>`.
- Existing backend billing routes in `backend/src/api/billing.py`:
  - `POST /api/v1/billing/subscribe`
  - `POST /api/v1/billing/onboard-seller`
- Stripe checkout service exists in `backend/src/services/stripe_service.py`.
- Paid.ai helper exists in `backend/src/services/paid_service.py`.
- Usage storage model exists in `backend/src/storage/models.py` as `UsageRecord`.
- Teams API already exists (`GET /api/v1/teams`) in `backend/src/api/teams.py`.

## Subtasks
1. **M3-T4-ST1 (Backend summary API)**
- Add a new authenticated endpoint under billing router to return workspace billing summary for a team owned by current user.
- Suggested path: `GET /api/v1/billing/summary/{team_id}`.
- Include in response:
  - Team id and subscription snapshot (best effort from existing data).
  - Total usage cost.
  - Cost grouped by marketplace agent.
  - Recent usage records (newest first, bounded list).
- Enforce team ownership (`Team.owner_id == current_user.id`). Return `404` when inaccessible.

2. **M3-T4-ST2 (Subscribe flow hardening)**
- Keep `POST /billing/subscribe` but improve contract quality:
  - Validate team ownership path (already present).
  - Return predictable typed payload (e.g., `checkout_url`, optional `team_id`).
  - Keep error handling explicit and stable for UI consumption.

3. **M3-T4-ST3 (Frontend billing client/types)**
- Add frontend API helpers in a dedicated module (e.g., `frontend/src/lib/billingApi.ts`).
- Add TypeScript types in `frontend/src/lib/types.ts` for billing summary + subscribe response.
- Reuse `toApiErrorMessage` from `frontend/src/lib/apiClient.ts`.

4. **M3-T4-ST4 (Billing page shell + nav)**
- Replace placeholder route with concrete page component (e.g., `frontend/src/pages/BillingPage.tsx`).
- Add Billing nav entry in `frontend/src/components/layout/AppShell.tsx`.
- Match existing app visual language and component usage (`Card`, `Button`, `Table`, etc).

5. **M3-T4-ST5 (Subscribe CTA flow)**
- Implement flow:
  - list teams owned by user;
  - select workspace/team;
  - click Subscribe;
  - handle loading and API errors;
  - redirect browser to Stripe checkout URL on success.
- Keep authorization assumptions consistent with existing auth header behavior.

6. **M3-T4-ST6 (Usage visibility widgets)**
- Render summary cards/tables for:
  - total cost,
  - per-agent usage/cost breakdown,
  - recent usage rows.
- Include empty-state behavior when no usage data exists.

## File targets (likely)
- Backend:
  - `backend/src/api/billing.py`
  - `backend/src/api/schemas_marketplace.py` (or split billing schemas if cleaner)
  - `backend/src/storage/models.py` (only if absolutely needed)
- Frontend:
  - `frontend/src/App.tsx`
  - `frontend/src/components/layout/AppShell.tsx`
  - `frontend/src/pages/BillingPage.tsx` (new)
  - `frontend/src/lib/billingApi.ts` (new)
  - `frontend/src/lib/types.ts`

## Constraints
- Do not silently change architecture contracts outside this scope.
- Keep role and ownership checks strict.
- Do not break existing PM dashboard/project flows.
- Keep changes focused to M3-T4 only.

## Testing expectations (implementer-owned smoke)
- Add/update tests only if directly required by your code touches; deeper coverage is handled by test-agent.
- At minimum run local smoke checks for touched areas if feasible.

## Required task/doc updates
- Update `TASKS.md` status lines only for subtasks you fully complete.
- If you complete ST1..ST6, update their statuses from `Todo` to `Done` and add concise notes in M3-T4 block.

## Output format
Provide:
1. Changed files list.
2. API contract summary (request/response for new endpoints).
3. UI behavior summary.
4. Tests run.
5. Open risks or follow-ups for test-agent/review-agent.
