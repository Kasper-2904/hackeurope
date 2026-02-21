# Team Rules (Shared)

This file is the shared operating guide for our team of 4.

## Team
- Kasper
- Martin
- Farhan
- Marin

## Core Rules
- One task has one human owner.
- Keep tasks small and explicit in `TASKS.md`.
- Never push unfinished or unreviewed work to `main`.
- If behavior changes, update `PROJECT_SPEC.md`, `ARCHITECTURE.md`, and `TASKS.md` in the same PR.

## Simple Work Loop
1. Pick task from `TASKS.md`.
2. Implement with your agent.
3. Add/update unit tests (see `TESTING.md`).
4. Open PR with a short summary:
   - what changed
   - tests added/updated
   - risks/open questions

## Agent Usage Rules
- Keep agent scope limited to the task.
- Do not silently change architecture contracts.
- If an agent cannot complete a required step, document it in the PR.

## Definition of Done
- Acceptance criteria for task are met.
- Unit tests are added/updated.
- Relevant docs are updated.
- CI is green.

## Docker Ports (Team Standard)
- Backend: `8000`
- Frontend: `5173`
- Dummy agents: `8001`, `8002`, `8003` (continue with `8004+` as needed)
