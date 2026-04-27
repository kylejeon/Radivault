# deface-sidecar Networking

> jpg-preview-defacing AC-21 / dev-spec §5 NFR Security / §12.5 Isolation

## Network topology

The `deface-sidecar` container is intentionally cut off from the public
internet. The only peer that can reach it is `gateway-agent`, which posts
DICOM tars to `POST /deface` and reads multipart responses back.

The compose file declares two networks:

| Network      | Driver   | `internal` | Members                              |
|--------------|----------|------------|--------------------------------------|
| `default`    | bridge   | `false`    | gateway-agent, mock-central, orthanc, orthanc-b |
| `deface-net` | bridge   | **`true`** | gateway-agent, deface-sidecar        |

`internal: true` tells Docker to skip installing the iptables MASQUERADE
rule that normally NATs container egress to the host's default route. The
result: any DNS / TCP / ICMP attempt from the sidecar that resolves to a
public address fails immediately at the kernel level — there is no
upstream gateway in the bridge.

The `gateway-agent` container is attached to **both** networks. The
gateway uses the `default` network for mock-central + Orthanc, and uses
`deface-net` only to call the sidecar. The sidecar itself is attached
**only** to `deface-net`, so its routing table contains no default
gateway.

```
                            (public internet)
                                    ▲
                                    │  egress / NAT
                  ┌─────────────────┴──────────────────┐
                  │           Docker host              │
                  │                                    │
   ┌──────────────┴───── network: default ─────────────┴─────┐
   │                                                          │
   │   gateway-agent ───── orthanc / orthanc-b / mock-central │
   │        │                                                 │
   └────────┼─────────────────────────────────────────────────┘
            │
   ┌────────┴────────────── network: deface-net ─────────────┐
   │   (internal: true — no NAT rule, no upstream)           │
   │                                                         │
   │   gateway-agent ─────────────► deface-sidecar           │
   │                                                         │
   └─────────────────────────────────────────────────────────┘
```

## Verification (smoke test)

After `docker compose up -d`, a one-shot probe MUST fail from inside the
sidecar:

```bash
# Expected: rc != 0 + "Could not resolve host" or "connect: Network is unreachable"
docker compose exec deface-sidecar \
  curl --max-time 2 https://example.com
```

A second probe MUST succeed from gateway-agent:

```bash
# Expected: rc == 0, JSON {"status":"ok"}
docker compose exec gateway-agent \
  curl --max-time 2 http://deface-sidecar:8090/healthz
```

If the public-internet probe succeeds, the sidecar has been mis-attached
to a routable network — review `docker-compose.yml` (top-level `networks:`
block + per-service `networks:` lists) before any production handoff.

## Why not `network_mode: none`?

`network_mode: none` would isolate the sidecar even from the gateway,
breaking the only intended ingress path (`POST /deface`). The
`internal: true` bridge keeps the gateway↔sidecar path while still
satisfying AC-21 because Docker omits the MASQUERADE rule that NATs
egress traffic.

## Smoke verification

> **Round 2 attempt — 2026-04-27, blocked at `docker compose build`.**
> AC-21 (network isolation) verification cannot be run until the
> sidecar image builds. The compose-level network topology (default
> + `deface-net` with `internal: true`) is in place and verified by
> `docker compose config` — only the runtime probe is blocked.

### Build attempt log

Host: macOS 25.3.0 / arm64 (Rancher Desktop, Docker 29.1.4-rd)
Time: 2026-04-27

```
$ docker pull afni/afni_make_build:latest
... Status: Downloaded newer image for afni/afni_make_build:latest    (rc=0)

$ docker compose build deface-sidecar
#7 [2/6] RUN apt-get update && apt-get install -y --no-install-recommends \
        dcm2niix python3.11 python3.11-venv python3-pip ca-certificates tini
#7 0.770 E: List directory /var/lib/apt/lists/partial is missing.
            - Acquire (13: Permission denied)
exit code: 100                                                        (rc=1)
```

**Root cause #1 — non-root base.** The upstream
`afni/afni_make_build:latest` image has a default `USER afni_user`
(UID 1000), so `apt-get update` cannot write `/var/lib/apt/lists`.
A `USER root` directive before the install layer is needed.

**Root cause #2 — Ubuntu 18.04 bionic.** Even with `USER root`, the
base image is `NAME="Ubuntu" VERSION="18.04.3 LTS (Bionic Beaver)"`
which only ships Python 3.6 in default repos. `fastapi >= 0.110` (the
sidecar's primary dep, per the existing Dockerfile) requires Python
3.8+, and the deadsnakes PPA — the canonical "newer Python on older
Ubuntu" workaround — has dropped bionic support, so
`add-apt-repository ppa:deadsnakes/ppa` followed by
`apt-get install python3.11` does not resolve. `tini` is also not in
the default bionic repos.

**Root cause #3 — amd64-only base on arm64 host.** The image is
single-platform `linux/amd64`; on a Rancher Desktop arm64 host it
runs under Rosetta/QEMU emulation which is functional but slow
(noticeable on 600 s+ AFNI runs). Production CI/CD on amd64 is
unaffected.

### Path forward (open items handed to the next round)

1. **Switch the base image** to a newer AFNI tag (e.g. one based on
   Ubuntu 22.04 jammy which ships Python 3.10 by default), OR
2. **Multi-stage build** — install Python 3.11 + the sidecar venv in
   an Ubuntu 22.04 stage, then COPY the AFNI binaries from the
   bionic stage into it. AC-20 (no FreeSurfer/FSL/Matlab) stays
   honoured because we'd only copy `/usr/local/abin/` (AFNI's
   install root), OR
3. **Pin fastapi to a Python 3.6-compatible version** — e.g.
   `fastapi==0.65.x` was the last 3.6-compat release. This downgrades
   the sidecar's HTTP framework but keeps the bionic base. Risk: the
   sidecar's app.py uses modern-ish typing (`from __future__ import
   annotations`) which is fine, but a dependency audit is required.

Recommendation: option **2** (multi-stage). Keeps the AFNI binaries
verbatim from the NIH-blessed image while decoupling our sidecar's
Python toolchain from the base OS. Estimated effort: half a day.

### Compose-config verification (still passing)

The `docker-compose.yml` topology was independently verified with
`docker compose config` — both networks are declared and the sidecar
is bound only to `deface-net`. AC-21 is **structurally** satisfied;
the runtime probe is what's pending.

```
$ docker compose config --services
deface-sidecar
mock-central
orthanc
gateway-agent
orthanc-b
```

Once the build blocker is resolved, the runtime probes from the
"Verification (smoke test)" section above MUST be re-run and the
output appended below this paragraph with timestamps and exit codes
before the D-13 demo.
