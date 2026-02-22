# Team Context

## Team: Demo Team
**Project:** E-Commerce Platform
**Sprint:** Sprint 4 (Feb 17 - Feb 28)

## Current Sprint Focus
- Finalize product catalog component (Charlie — 60% complete, agent draft in review)
- Security audit of payment module (pending PM approval of plan)
- CI/CD pipeline setup (assigned to DevOps Pro Agent, Bob overseeing)

## Latest Reviewer Notes

### Review #1 — Product Catalog Component (Feb 20)
- **Agent:** Claude Frontend Expert
- **Finding:** ProductCard component lacks keyboard navigation for accessibility (WCAG 2.1 AA requirement).
- **Action:** Charlie to add `tabIndex`, `onKeyDown` handlers, and ARIA labels before finalizing.
- **Status:** Fix in progress.

### Review #2 — Authentication API (Feb 18)
- **Agent:** Claude Security Reviewer
- **Finding:** Token refresh endpoint doesn't invalidate the old refresh token, allowing token reuse attacks.
- **Action:** Bob implemented token rotation — old token is blacklisted on refresh.
- **Status:** Resolved. Merged in PR #41.

### Review #3 — Product Filter Endpoint (Feb 19)
- **Agent:** Claude Security Reviewer
- **Finding:** Query parameters passed directly to database without sanitization. SQL injection risk.
- **Action:** Pydantic validation added to all filter parameters. Parameterized queries enforced.
- **Status:** Fix pending review.

## Retrospective Findings (Sprint 3)
- Agent drafts save ~40% of implementation time on well-defined tasks
- Vague task descriptions lead to poor agent output — always include acceptance criteria
- Reviewer Agent caught 3 security issues that manual review missed
- Merge conflicts increased when two agents work on overlapping files — OA now checks for file overlap before assigning

## Communication Log
- **Feb 20:** Alice (PM) approved Product Catalog plan, assigned Charlie as owner
- **Feb 19:** Bob flagged performance concern with product search on large datasets (>10k products)
- **Feb 18:** Team agreed to use cursor-based pagination over offset-based for all list endpoints
- **Feb 17:** Sprint 4 kickoff — focus on completing catalog + security audit before staging deploy

## Working Agreements
- All agent drafts must be reviewed by a human before merge
- Security-flagged risks must be resolved within 48 hours
- Code review turnaround target: < 24 hours
- Daily async standup in Slack #dev-ecommerce channel
