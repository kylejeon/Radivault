# RadiVault Portal

Next.js 14 App Router project that hosts two surfaces on a single deployable:

- **Buyer Portal** (`/`, `/search`, `/orders`, `/orders/[id]`, `/orders/[id]/downloads`,
  `/signin`, `/docs`) — English, cool-blue theme.
- **Hospital Dashboard** (`/hospital`, `/hospital/signin`) — Korean, teal theme.

Backed entirely by BFF (Route Handlers) — upstream API keys and hospital
admin tokens never reach the browser.

## Commands

```bash
npm install
cp .env.example .env.local  # fill in values
npm run dev                 # http://localhost:3000
npm run build               # production build
npm run test                # Vitest smoke tests
npm run typecheck           # tsc --noEmit
```

## Environment

| Variable | Purpose |
|---|---|
| `CENTRAL_INGEST_URL` | base URL for central-ingest (`/v1/hospital/me/*`) |
| `SEARCH_URL` | base URL for metadata-index (`/v1/search/*`) |
| `FULFILLMENT_URL` | base URL for order-fulfillment (`/v1/orders/*`) |
| `SESSION_PASSWORD` | 48+ char random string used by iron-session |
| `DEMOOP_TOKEN` | optional — if set, enables Demo Operator Mode |
| `RV_HOSPITAL_ADMIN_TOKENS` | JSON map for D-5 hospital login |
| `HOSPITAL_UPSTREAM_BEARER` | gateway auth_token proxied to upstream for hospital tiles |

## Design notes

- Tokens: `src/app/globals.css` + `tailwind.config.ts`.
- Surface theming via `surface-buyer` / `surface-hospital` classes.
- Error taxonomy: `src/lib/errors.ts` — see design-spec §7.
- Session: `src/lib/session.ts` — iron-session v8, HttpOnly/SameSite=Lax.

See `docs/specs/dev-spec-buyer-portal-demo.md` and
`docs/specs/design-spec-buyer-portal-demo.md` for the full contracts.
