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
