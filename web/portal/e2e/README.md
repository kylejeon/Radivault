# Portal e2e (Playwright) — feature-slug `portal-e2e`

Safety net for the CEO-meeting demo. Three scenarios, all hermetic (no live upstream).

- **Prereq**: Next.js dev server on port 3000 (`npm run dev`). Playwright config sets `reuseExistingServer: true` — if Kyle already has one running it is reused; otherwise Playwright boots one.
- **One-time**: `npm install` then `npm run e2e:install` (downloads Chromium ~160MB).
- **Run**: `npm run e2e` (CLI list reporter) or `npm run e2e:ui` (interactive).
- **Mock strategy**: Every spec calls `blockRealUpstream(page)` first (returns 599 on any `/api/**`), then layers specific mocks via `page.route`. Session cookies are forged with `iron-session sealData` using the same `SESSION_PASSWORD` the dev server reads — see `e2e/fixtures/session.ts`.
- **Live-vs-mock switch**: not added in v0.1 — add a `PORTAL_E2E_LIVE=1` env flag later if you ever want an end-to-end smoke against the real docker stack.
