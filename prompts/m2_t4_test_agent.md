You are a test agent validating `M2-T4 PM Dashboard UI`.

Scope:
- Implement tests for `M2-T4-ST7` and `M2-T4-ST8` in `docs/plans/M2-T4_IMPLEMENTATION_PLAN.md`.

Mandatory execution rules:
- Work on branch `marin-m2-t4-pm-dashboard-ui`.
- Follow `TESTING.md` and `AGENTS.md`.
- Keep tests deterministic and mock external systems.

Test requirements:
- Add backend tests for project agent allowlist APIs:
  - list/add/remove happy path
  - duplicate or invalid operations
  - authorization and ownership checks
- Add backend tests for PM plan approval/rejection paths used by dashboard actions.
- Add frontend tests for PM dashboard:
  - loading/error/success rendering
  - allowlist management interactions
  - approve/reject flow and rejection-reason validation

Quality requirements:
- Ensure backend and frontend test commands are runnable and documented.
- Record exact commands used and failing scenarios (if any).

Deliverable:
- Test files plus a short coverage summary and known remaining test gaps.
