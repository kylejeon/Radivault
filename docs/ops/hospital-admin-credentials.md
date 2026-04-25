# Hospital admin credentials (demo)

> **Scope**: D-day demo only. These are *not* pilot credentials.
>
> **Source of truth**: `web/portal/.env.local` (`RV_HOSPITAL_ADMIN_TOKENS`).
> The plaintext below is what you type into `/hospital/signin`; the env
> file stores the SHA-256 hash.

| hospital_id | admin password (plaintext)  | SHA-256 prefix |
|-------------|-----------------------------|----------------|
| HOSP-001    | `radivault-demo-2026`       | `sha256:55e1aa…3065b` |
| HOSP-002    | `tunteun-demo-2026`         | `sha256:b9e246…7a67`  |

## Adding a new hospital

```bash
# 1. Generate hash
PASSWORD='your-new-password-here'
node -e "console.log('sha256:' + require('crypto').createHash('sha256').update('$PASSWORD').digest('hex'))"

# 2. Append to RV_HOSPITAL_ADMIN_TOKENS in web/portal/.env.local
#    (the value is a JSON object, key=hospital_id, value=sha256:<hex>).

# 3. Issue an upstream bearer for the new hospital
docker exec radivault-central-1 \
  ingest-admin token issue --hospital-id HOSP-XXX

# 4. Add to .env.local as HOSP_XXX_BEARER (per-hospital lookup, HIGH-2).

# 5. Update this file.
```

## Rotation

There is no rotation procedure for v0.1. To rotate, regenerate the hash
+ bearer + restart the portal container. Tokens have no expiry.

## Why plaintext lives in a doc

The portal repo is private. Demo passwords are operational artefacts on
par with the bearer tokens that already live in `.env.local`. Pilot
deployments will use SSO (FR-HO-2 / Q10) and this file becomes obsolete.
