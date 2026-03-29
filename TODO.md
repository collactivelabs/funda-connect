# FundaConnect TODO

Reviewed: 2026-03-29

This file tracks outstanding work identified by comparing the original technical documentation with the current implementation.

## Recommended Order

- [x] Establish a safer foundation first: tests, frontend scripts, and CI.
- [x] Harden authentication flows next.
- [x] Build the full admin verification workflow.
- [ ] Complete the remaining payments/reporting/scope decisions.
- [ ] Finish security and documentation cleanup.

## 1. Foundation And Tooling

- [x] Add real backend tests beyond `backend/tests/conftest.py`.
- [x] Add frontend scripts for `lint`, `typecheck`, and `test` in `frontend/package.json`.
- [x] Align `Makefile` frontend targets with actual package scripts.
- [x] Add CI for linting, type-checking, and tests on push.
- [ ] Clean up existing backend Ruff violations so backend lint can be enforced in CI.

## 2. Authentication And Sessions

- [x] Add email verification flow.
- [x] Add forgot-password and reset-password flow.
- [x] Add Google OAuth login.
- [x] Replace simple stateless refresh handling with rotation and reuse detection.
- [x] Add session listing and session revocation support.

## 3. Teacher Verification Workflow

- [x] Add admin review of individual verification documents, not only whole-teacher status changes.
- [x] Surface reviewer notes per document.
- [x] Add secure/private document viewing flow for admins and teachers.
- [x] Improve verification queue details in the admin dashboard.
- [ ] Decide whether to implement automated SACE/NRSO checks or remove them from active scope.

## 4. Payments, Payouts, And Reporting

- [x] Add payment history endpoint and UI.
- [x] Implement refund handling based on cancellation policy.
- [x] Add dispute/escrow workflow where needed.
- [x] Add invoice or receipt generation if still in scope.
- [ ] Decide whether recurring lessons should stay as the current prepaid-series model or move to true subscription-style charging.
- [ ] Decide whether Ozow support is still planned; implement it or remove the remaining references.

## 5. Bookings, Learners, And Lesson Operations

- [x] Add rescheduling flow for bookings.
- [x] Add learner progress tracking.
- [x] Add learner report export.
- [x] Persist and surface lesson notes and covered topics on completed lessons.
- [x] Add a first-class attendance/no-show workflow for live lessons.
- [x] Add blocked dates to teacher scheduling.
- [ ] Decide whether calendar sync is still needed for scheduling.

## 6. Notifications

- [x] Add notification center endpoints and UI.
- [x] Add notification preferences management.
- [x] Add in-app notifications for key booking, verification, payout, and refund events.
- [ ] Add SMS delivery if still required.
- [ ] Add push delivery if still required.
- [ ] Add notification delivery tracking where useful.

## 7. Search And Reference Data

- [x] Add reference-data endpoints for grade levels and curricula.
- [x] Add a topics endpoint if topics remain part of the API contract.
- [ ] Decide whether teacher search should move to Meilisearch or stay database-backed.
- [x] Align the public search/filter contract with what the API actually supports.

## 8. Security And Compliance

- [x] Add security headers beyond the current CORS setup.
- [x] Add rate limiting for auth, booking, upload, and admin endpoints.
- [x] Add audit logging for sensitive/admin actions.
- [x] Add consent tracking for registration and marketing preference changes.
- [x] Add data export and account deletion/anonymisation flows.
- [x] Harden file uploads with stricter content validation and safe filename normalisation.
- [x] Add malware/virus scanning support for uploads when configured.

## 9. Deployment, Infrastructure, And Docs

- [ ] Update technical docs to reflect the actual project stage instead of `Pre-Development` / `Draft`.
- [ ] Align docs with the current implementation details and route surface.
- [ ] Add production deployment/infra definitions if they are still intended to live in this repo.
- [ ] Add monitoring/observability setup if still in scope.
- [ ] Decide whether the planned mobile app remains active scope or is a later-phase item.

## Notes

- Recent booking, PayFast, admin, onboarding, and dashboard fixes were already completed and committed before this TODO file was created.
- Auth hardening, session management, and admin document-level verification review were added after the initial backlog draft.
- This list should be treated as a living backlog, not as a promise that every original doc item still belongs in scope.
