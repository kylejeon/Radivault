# jpg-preview-defacing FR-DEFACE-5 — AFNI refacer sidecar.
#
# Multi-stage build (CAVEAT-2 round-3 fix). The upstream
# afni/afni_make_build:latest image is built on Ubuntu 18.04 bionic and
# runs as a non-root afni_user (UID 1000), which makes apt-get fail and
# blocks installing Python 3.11 / fastapi / tini. Round 3's recommended
# resolution: stage out the AFNI binaries from the bionic image and
# graft them onto a modern python:3.11-slim-bookworm runtime that
# already ships Python 3.11, has tini in the default repos, and runs
# under the same glibc-forward-compat that AFNI binaries built against
# glibc 2.27 honor on glibc 2.36.
#
# License posture (AC-20):
#   - AFNI:    NIH Public Domain
#   - dcm2niix: 2-clause BSD (vendored as the pypi `dcm2niix` wheel)
#   - Python deps: nibabel (MIT), numpy (BSD), Pillow (HPND/MIT-CMU),
#                  fastapi/uvicorn (MIT), python-multipart (MIT)
#   - tini:    MIT
# No FreeSurfer / FSL / Matlab — see AC-20.
#
# Network posture (FR-DEFACE-5, AC-21):
#   - The compose file pins this service to the deface-net bridge with
#     `internal: true`, so runtime egress is impossible. This Dockerfile
#     only fetches atlases at BUILD time (curl in the atlas-fetcher
#     stage); the runtime stage never opens an outbound socket.
#
# Architecture note:
#   AFNI's prebuilt binaries are linux/amd64 only. We pin both build and
#   runtime stages to --platform=linux/amd64. On arm64 Docker hosts
#   (Rancher Desktop / Apple Silicon) the container runs under
#   qemu/Rosetta emulation — functional but ~3-5× slower on big AFNI
#   warps. Production deploy on amd64 hosts is unaffected.

ARG AFNI_BUILD_TAG=latest

# ---------------------------------------------------------------------
# Stage 1 — afni-builder: pull AFNI install tree out of the bionic
# upstream image. We do NOT try to install anything new in this stage;
# the upstream image's non-root afni_user makes apt-get fail and we
# don't need apt — only the read-only /opt/afni/install/ tree.
# ---------------------------------------------------------------------
FROM --platform=linux/amd64 afni/afni_make_build:${AFNI_BUILD_TAG} AS afni-builder

# Sanity-check the binary contract our app relies on (FR-DEFACE-7). If
# the upstream image ever moves @afni_refacer_run, the build fails here
# instead of silently producing a broken sidecar.
RUN test -x /opt/afni/install/@afni_refacer_run \
    && test -x /opt/afni/install/3dAllineate \
    && test -x /opt/afni/install/3dcalc \
    && test -x /opt/afni/install/nifti_tool \
    && test -f /opt/afni/install/libmri.so \
    && test -f /opt/afni/install/libf2c.so

# ---------------------------------------------------------------------
# Stage 2 — atlas-fetcher: download AFNI's MNI152_2009_template_SSW
# (used by 3dAllineate as the alignment target — refacer.tcsh L70/L186)
# and the afni_refacer_shell_sym_1.0/2.0 datasets (the face-region
# replacement shells). The afni_make_build image does NOT bundle these;
# the canonical NIH CDN does. We pin Last-Modified dates from
# afni.nimh.nih.gov in the build log so a future drift is obvious.
# ---------------------------------------------------------------------
FROM --platform=linux/amd64 debian:bookworm-slim AS atlas-fetcher

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /atlas

# atlases_latest.tgz (~66 MB) carries MNI152_2009_template_SSW.nii.gz
# as a real file (not a git-annex symlink). We extract only that one
# file to keep image size minimal.
RUN curl -fsSL -o /tmp/atlases.tgz \
        "https://afni.nimh.nih.gov/pub/dist/tgz/atlases_latest.tgz" \
    && tar -xzf /tmp/atlases.tgz -C /atlas MNI152_2009_template_SSW.nii.gz \
    && rm /tmp/atlases.tgz

# afni_atlases.tgz (~80 MB) carries afni_refacer_shell_sym_{1,2}.0.nii.gz
# as real files (the inner atlases/ subdir is git-annex symlinks, but
# the refacer shells themselves are flat files at the tarball root).
RUN curl -fsSL -o /tmp/afni_atlases.tgz \
        "https://afni.nimh.nih.gov/pub/dist/data/afni_atlases.tgz" \
    && tar -xzf /tmp/afni_atlases.tgz -C /tmp \
        afni_atlases/afni_refacer_shell_sym_1.0.nii.gz \
        afni_atlases/afni_refacer_shell_sym_2.0.nii.gz \
    && mv /tmp/afni_atlases/afni_refacer_shell_sym_1.0.nii.gz /atlas/ \
    && mv /tmp/afni_atlases/afni_refacer_shell_sym_2.0.nii.gz /atlas/ \
    && rm -rf /tmp/afni_atlases /tmp/afni_atlases.tgz

# ---------------------------------------------------------------------
# Stage 3 — runtime: modern Debian + Python 3.11. AFNI binaries get
# COPY'd in. Python deps installed via pip. Drops to afni_user (UID 1000)
# at the end (HIPAA defense-in-depth + matches round-3 sidecar
# expectations).
# ---------------------------------------------------------------------
FROM --platform=linux/amd64 python:3.11-slim-bookworm AS runtime

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

# Runtime libs needed by AFNI binaries called from @afni_refacer_run.
#
# Most binaries (3dAllineate, 3dQwarp, 3dWarp, 3dresample, 3dcalc,
# 3dmask_tool, 3dAFNItoNIFTI, nifti_tool, 3dinfo) are headless and only
# need libc/libm/libgomp/libexpat/libz.
#
# BUT @afni_refacer_run -> @FindAfniDsetPath -> `afni -get_processed_env`,
# which always dlopen()s the full Motif/GLU GUI stack on startup, even
# in the no-display code path. So we must install:
#   libxm4    — Motif (transitively pulls libxt/libxext/libxft/libxmu/
#               libpng/libjpeg62-turbo/libfontconfig/libfreetype)
#   libglu1-mesa — GLU (used by AFNI's volume rendering init code)
# This is GUI-stack-on-headless overhead but unavoidable while we're
# pinned to the upstream `afni` binary's startup contract.
#
# Plus:
#   tcsh — @afni_refacer_run is `#!/usr/bin/env tcsh`
#   tini — PID 1 init that reaps AFNI's fork-heavy subprocess tree
#   curl — HEALTHCHECK
#   libgomp1 — OpenMP, needed by 3dQwarp / 3dAllineate
#   libexpat1 — used by AFNI's NIfTI/XML parsing
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tcsh \
        tini \
        curl \
        ca-certificates \
        libexpat1 \
        libgomp1 \
        libxm4 \
        libxpm4 \
        libxt6 \
        libxext6 \
        libxft2 \
        libxmu6 \
        libglu1-mesa \
        libgl1 \
        libfontconfig1 \
        libfreetype6 \
        libpng16-16 \
        libjpeg62-turbo \
    && rm -rf /var/lib/apt/lists/* \
    # AFNI's `afni` GUI binary (called by @FindAfniDsetPath via
    # `afni -get_processed_env`) was linked against libjpeg.so.8 on
    # bionic. bookworm ships libjpeg.so.62 (libjpeg-turbo 2.1.5).
    # The ABI is forward-compatible for the symbols `afni` actually
    # references at startup (only IJG public API). Symlink as a compat
    # shim — verified by the build-time probe two layers below.
    && ln -sf /usr/lib/x86_64-linux-gnu/libjpeg.so.62 \
              /usr/lib/x86_64-linux-gnu/libjpeg.so.8

# Python deps — pinned majors so a base-image refresh doesn't surprise
# us. Versions chosen to match round-1's resolved ranges (verified via
# round-3 lockfile probe before AFNI base-image switch).
RUN pip install --no-cache-dir \
        "fastapi>=0.110,<1.0" \
        "uvicorn[standard]>=0.27,<1.0" \
        "python-multipart>=0.0.9,<1.0" \
        "numpy>=1.26,<3.0" \
        "nibabel>=5.2,<6.0" \
        "pillow>=10.2,<12.0" \
        "dcm2niix>=1.0.20240202"

# Symlink the pip-installed dcm2niix wheel binary onto PATH. The pypi
# package places the real binary at .../site-packages/dcm2niix/dcm2niix
# and a wrapper at /usr/local/bin/dcm2niix; we want the real binary on
# PATH for AFNI's tcsh subprocesses (which don't go through the wrapper
# reliably). Verify it's executable.
RUN ln -sf /usr/local/lib/python3.11/site-packages/dcm2niix/dcm2niix \
        /usr/local/bin/dcm2niix-bin \
    && /usr/local/bin/dcm2niix-bin -h >/dev/null

# AFNI install tree — ~200 MB. We put it at /opt/afni so internal paths
# match the upstream layout (libmri.so / libf2c.so live alongside the
# binaries and AFNI dlopen()s them via $ORIGIN).
COPY --from=afni-builder /opt/afni/install /opt/afni/install

# Refacer atlas + MNI alignment template — copied to a directory that
# AFNI's @FindAfniDsetPath will discover via AFNI_PLUGINPATH /
# AFNI_GLOBAL_SESSION. We use AFNI_GLOBAL_SESSION because that's the
# documented "system-wide dataset search path" (refacer.tcsh L186 calls
# @FindAfniDsetPath which honors it).
COPY --from=atlas-fetcher /atlas /opt/afni/atlases

# AFNI binaries on PATH; libmri.so/libf2c.so on LD_LIBRARY_PATH; atlases
# on AFNI_GLOBAL_SESSION so refacer's `@FindAfniDsetPath -append_file`
# resolves them. AFNI_PLUGINPATH is also set so afni_proc finds them.
ENV PATH="/opt/afni/install:${PATH}" \
    LD_LIBRARY_PATH="/opt/afni/install" \
    AFNI_GLOBAL_SESSION="/opt/afni/atlases" \
    AFNI_PLUGINPATH="/opt/afni/install"

# Sanity probe at build time — prove the AFNI binaries actually run on
# bookworm's glibc and find the atlas. If this fails, we surface to QA
# rather than ship a sidecar that 500s on first request.
RUN /opt/afni/install/3dinfo -help >/dev/null 2>&1 \
    && /opt/afni/install/@FindAfniDsetPath -full_path -append_file \
        afni_refacer_shell_sym_1.0.nii.gz | grep -q nii.gz \
    && /opt/afni/install/@FindAfniDsetPath -full_path -append_file \
        MNI152_2009_template_SSW.nii.gz | grep -q nii.gz

# Non-root user (HIPAA defense-in-depth + AC-21 alignment). UID 1000
# matches the upstream afni_user so any volume-mounted artifacts retain
# consistent ownership across base-image refreshes.
RUN useradd --create-home --uid 1000 --shell /bin/bash afni_user \
    && mkdir -p /opt/sidecar \
    && chown -R afni_user:afni_user /opt/sidecar /home/afni_user \
    && chmod 755 /opt/afni/install /opt/afni/atlases

WORKDIR /opt/sidecar
COPY --chown=afni_user:afni_user app.py /opt/sidecar/app.py

USER afni_user

# Healthcheck — sidecar must respond 200 to /healthz before gateway
# routes deface jobs to it (FR-DEFACE-8: unhealthy => quarantine path).
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8090/healthz || exit 1

EXPOSE 8090

# tini reaps AFNI's subprocess zombies; uvicorn does the rest.
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8090", "--workers", "1"]
