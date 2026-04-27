# `secrets/` — runtime credential drop-zone

This directory holds operator-provided credential files referenced by the
gateway config via the `${file:...}` substitution pattern (see
`src/radivault_gateway/config/loader.py:_SECRET_RE`).

## Multi-PACS upload tokens (FR-MPS-7 / K-MPS-8)

For multi-PACS sync, each hospital has its own central upload bearer.
Operators have two equivalent ways to wire them:

- **Environment variables** — `${env:HOSP_001_TOKEN}` /
  `${env:HOSP_002_TOKEN}` resolved at gateway start. Used by
  `configs/gateway.docker.yaml` for container deployments.

- **File-mounted secrets** — `${file:secrets/HOSP_001_TOKEN}` /
  `${file:secrets/HOSP_002_TOKEN}`. Each file holds the literal token
  with no surrounding whitespace; the loader strips trailing newline.

Recommended permissions on host bind-mount:

```sh
chmod 0600 secrets/HOSP_*_TOKEN
chown root:root secrets/HOSP_*_TOKEN
```

## Why these files are .gitignored

The `.gitignore` excludes `secrets/*` except this README + `.gitkeep`.
Never commit a real token. Demo configs (`configs/demo_gateway.yaml`)
ship with literal tokens for local convenience — those are demo-only and
will be rotated before pilot.

## Issuing a fresh token

```sh
docker exec radivault-central-1 ingest-admin token issue \
  --hospital-id HOSP-002 \
  --note "demo gateway 2026-04"
```

Save the printed token to `secrets/HOSP_002_TOKEN`.
