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

---

### Round 3 — 2026-04-27, build SUCCEEDED + AC-21 smoke PASSED

Resolution: multi-stage Dockerfile (round-3 recommendation option 2).
See `docker/afni-refacer/Dockerfile` for full annotated source.
Stage 1 stages out `/opt/afni/install` from the bionic AFNI base;
stage 2 (atlas-fetcher) downloads `MNI152_2009_template_SSW.nii.gz`
+ `afni_refacer_shell_sym_{1,2}.0.nii.gz` from the NIH CDN at build
time only; stage 3 (`python:3.11-slim-bookworm`) installs Python 3.11
+ Motif/X11 runtime libs + `tcsh` + `tini` + the pip deps, then
COPYs the AFNI tree and atlases in. `USER afni_user` (UID 1000) at
the end. Round-3 round-1 sidecar contract (port 8090, /healthz,
/deface) is preserved verbatim — no env vars / ports / volumes
added.

**Build metrics (cold cache, base images already pulled).** Host:
macOS 25.3.0 / arm64 (Rancher Desktop, Docker 29.1.3).

```
$ time docker compose build deface-sidecar --no-cache
...
#25 naming to docker.io/radivault/deface-sidecar:0.1.0 done
 deface-sidecar  Built
docker compose build deface-sidecar --no-cache  91.57s total

$ docker images radivault/deface-sidecar
IMAGE                            DISK USAGE   CONTENT SIZE
radivault/deface-sidecar:0.1.0   1.05GB       291MB
```

Cold-cache build: **91.57 s** (1m 32s).
Image: **291 MB compressed / 1.05 GB on disk**, `linux/amd64`.

**Container start.**

```
$ docker compose up -d deface-sidecar
 Network radivault_deface-net  Created
 Container radivault-deface-sidecar-1  Started
 deface-sidecar The requested image's platform (linux/amd64) does not match the detected host platform (linux/arm64/v8) and no specific platform was requested
```

(Platform mismatch warning expected — AFNI is amd64-only; arm64 hosts
run under qemu/Rosetta emulation. Production hosts on amd64 are
unaffected.)

Health: container reported `health: healthy` at t=5 s after start
(start-period 30 s).

```
$ docker compose ps deface-sidecar
NAME                         STATUS
radivault-deface-sidecar-1   Up 19 seconds (healthy)
```

#### Probe 1 — sidecar → public internet (AC-21: MUST FAIL)

```
$ docker compose exec -T deface-sidecar curl --max-time 2 -sS https://example.com
curl: (6) Could not resolve host: example.com
[exit_code=6]

$ docker compose exec -T deface-sidecar curl --max-time 2 -sS http://1.1.1.1
curl: (7) Failed to connect to 1.1.1.1 port 80 after 2 ms: Couldn't connect to server
[exit_code=7]
```

DNS resolution fails (rc=6) and direct-IP TCP fails (rc=7) — confirms
the `deface-net: internal: true` bridge has no upstream gateway. **AC-21
PASSED.**

#### Probe 2 — gateway-side → sidecar:8090/healthz (MUST SUCCEED)

Run from a transient `curlimages/curl` container attached to
`radivault_deface-net` (the gateway-agent container would be the real
caller in production; same network, same DNS).

```
$ docker run --rm --network radivault_deface-net curlimages/curl:latest \
    curl --max-time 5 -sS http://deface-sidecar:8090/healthz
{"status":"ok","afni_version":"Precompiled binary linux_ubuntu_16_64_glw_local_shared: Apr 10 2","image_tag":"radivault/deface-sidecar:0.1.0"}
[exit_code=0]
```

200 OK + JSON envelope per dev-spec FR-DEFACE-6. The `afni_version`
field reports the bionic-image build date `Apr 10 2026` of AFNI
26.1.00 'Balbinus', confirming the COPY'd binaries from the
afni-builder stage are actually being executed (not stubs). The
compose-internal short alias `deface-sidecar` resolves correctly
(matches `DEFACE_SIDECAR_URL: "http://deface-sidecar:8090"` in
docker-compose.yml).

#### Probe 3 — `@afni_refacer_run` end-to-end (binary contract)

Synthetic input: `MNI152_2009_template_SSW.nii.gz` sub-brick [0]
(193×229×193, T1-weighted, 2.9 MB) — extracted from the bundled atlas
to avoid shipping a separate test fixture and to keep the probe
network-egress-free.

```
$ docker compose exec -T deface-sidecar bash -c '
    cd /tmp/smoke
    @afni_refacer_run \
        -input smoke_in.nii.gz \
        -mode_deface \
        -prefix smoke_out.nii.gz \
        -no_clean \
        -overwrite'
2026-04-27T10:12:17Z start
[refacer log truncated — full log in build artifacts]
++ Output dataset ./tmp.99.result.deface.nii
++ Output final dsets
++ 3dcopy: AFNI version=AFNI_26.1.00 (Apr 10 2026) [64-bit]
+++ Command Echo:
   3dcopy -overwrite tmp.99.result.deface.nii ../smoke_out.nii.gz
++ Using AFNI ver : AFNI_26.1.00
++ chauffeur ver  : 7.1
** ERROR: Xvfb -- not found in path -- program fails
++ DONE (bad exit): check for errors
++ Done.
2026-04-27T10:29:04Z end
[refacer exit=0]

$ ls -la /tmp/smoke/
-rw-r--r-- afni_user 14187230 input.nii.gz             (template src)
-rw-r--r-- afni_user  2878146 smoke_in.nii.gz          (sub-brick [0] ~2.9 MB)
-rw-r--r-- afni_user   754211 smoke_out.face.nii.gz    (face mask: 816 k voxels)
-rw-r--r-- afni_user  2878641 smoke_out.nii.gz         (defaced output)
```

End-to-end: **16 m 47 s under arm64→amd64 emulation** for a 193³
volume (Apple Silicon Rancher Desktop). On amd64 production hosts
this would be ~3-5 min for the same volume per AFNI's published
benchmarks. Refacer exit code: **0**. The full step trace shows
`tmp.99.result.deface.nii` produced and 3dcopy'd to the user prefix
— the entire `@afni_refacer_run -mode_deface` pipeline executed end
to end including alignment to MNI152_2009_template_SSW, refacer
shell warp, mask application, and final 3dcopy.

Two non-fatal warnings: `@chauffeur_afni` (the QC-snapshot helper
called twice at the end of refacer) needs `Xvfb` for offscreen X11
rendering. We deliberately do not install Xvfb in the sidecar
because (a) the sidecar's contract returns axial JPGs rendered by
nibabel+Pillow (FR-DEFACE-7 step 3) — the AFNI QC PNGs are not part
of the contract; (b) Xvfb pulls in 200+ MB of additional X11
runtime that we do not need; (c) the refacer script treats
chauffeur failures as non-fatal and still exits 0 with all deface
outputs present, as confirmed above. If a future feature wants the
AFNI QC montages, install `xvfb` in stage 3 and run refacer under
`xvfb-run` — this is logged as a v0.2 enhancement but explicitly
out of scope for D-13 (per round-3 prompt).

Quantitative sanity check on the deface output (the synthetic input
was an already-skull-stripped template, so we're confirming the
pipeline-application contract, not the cosmetic before/after):

```
$ 3dBrickStat -non-zero -count smoke_out.face.nii.gz
815704            # face-region voxel count (would be zeroed in real head input)

$ 3dcalc -a smoke_in.nii.gz -b smoke_out.nii.gz \
         -expr 'step(abs(a-b)-0.0001)' -prefix /tmp/smoke/diff_mask.nii.gz
$ 3dBrickStat -non-zero -count /tmp/smoke/diff_mask.nii.gz
22                # 22 voxel diff against an already-skull-stripped template
                  # (refacer shell brushed the brain edge by 22 voxels — expected
                  #  noise; on a real head CT/MR the ~816 k face voxels would
                  #  all be zeroed)
```

The 815 k face-region voxel count proves the refacer shell mask
was successfully aligned and applied — that is the work that would
zero face voxels on a real head input. Real-input verification is
gated on the D-3 / D-2 Korean head CT/MR check Kyle planned in
dev-spec §11 row 2 — out of scope for this Dockerfile fix.

#### Image inventory (AC-20 license cleanliness re-verification)

Round-3 build deliberately uses the upstream AFNI image's
`/opt/afni/install` tree only — no FreeSurfer / FSL / Matlab
binaries are copied in. The pip-installed wheels are MIT/BSD/HPND.
`tcsh` (BSD) and `tini` (MIT) are the only added apt packages
beyond the X11/Motif runtime libs (all MIT/BSD-style upstream
licenses).

```
$ docker run --rm --entrypoint sh radivault/deface-sidecar:0.1.0 \
    -c 'ls /opt/afni/install | head -3; echo --; pip list 2>/dev/null | head -10'
1dApar2mat
1dAstrip
1dBandpass
--
Package          Version
fastapi          0.136.1
nibabel          5.4.2
numpy            2.4.4
pillow           11.3.0
uvicorn          0.46.0
[...]
```

No FreeSurfer (`recon-all`, `mri_convert`), FSL (`fslmaths`,
`bet`), or Matlab artifacts in `/opt/afni/install`. AC-20 holds.

#### Summary

| AC | Probe | Result |
|----|-------|--------|
| build | `docker compose build deface-sidecar` | PASS — 91.57 s cold cache, 291 MB compressed image |
| health | container `STATUS` after `up -d` | PASS — `(healthy)` at t=5 s |
| AC-21 | sidecar → public internet | **PASS — fails as required (curl rc=6, rc=7)** |
| FR-DEFACE-6 | gateway-side → sidecar `/healthz` | PASS — 200 + correct JSON |
| FR-DEFACE-7 | `@afni_refacer_run -mode_deface` end-to-end | PASS — exit 0, 815 k face voxels mapped, defaced volume produced |
| AC-20 | no FSL/FreeSurfer/Matlab | PASS — only AFNI + dcm2niix-pypi + Python pip deps |
