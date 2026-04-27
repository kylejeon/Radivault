# jpg-preview-defacing FR-DEFACE-5 — AFNI refacer sidecar.
#
# Base: AFNI's official build image (NIH Public Domain). Tagged via
# AFNI_BUILD_TAG so we pin a specific date in CI but allow a floating
# tag for local dev. The image only contains AFNI, dcm2niix (BSD),
# Python 3.11 + a thin HTTP server. NO FreeSurfer / FSL / Matlab — see
# AC-20 (license cleanliness).
#
# License posture (AC-20):
#   - AFNI:    NIH Public Domain
#   - dcm2niix: 2-clause BSD
#   - Python deps: nibabel (MIT), numpy (BSD), Pillow (HPND/MIT-CMU),
#                  fastapi/uvicorn (MIT), python-multipart (MIT)
#
# Network posture (FR-DEFACE-5, AC-21):
#   - The compose file pins this service to network_mode: internal so
#     it cannot reach the public internet at runtime. The only ingress
#     is the gateway-agent over the internal compose network.

ARG AFNI_BUILD_TAG=latest
FROM afni/afni_make_build:${AFNI_BUILD_TAG} AS base

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

# dcm2niix + Python toolchain. AFNI's image already has python; we
# install pip + venv to keep our deps isolated from AFNI's site-packages.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        dcm2niix \
        python3.11 \
        python3.11-venv \
        python3-pip \
        ca-certificates \
        tini \
    && rm -rf /var/lib/apt/lists/*

# Isolated venv at /opt/sidecar — runtime PATH puts it ahead of AFNI's
# python so our app's imports never collide.
RUN python3.11 -m venv /opt/sidecar/venv
ENV PATH="/opt/sidecar/venv/bin:${PATH}"

# Pip deps — pinned majors so a base-image refresh doesn't surprise us.
RUN pip install --no-cache-dir \
        "fastapi>=0.110,<1.0" \
        "uvicorn[standard]>=0.27,<1.0" \
        "python-multipart>=0.0.9,<1.0" \
        "numpy>=1.26,<3.0" \
        "nibabel>=5.2,<6.0" \
        "pillow>=10.2,<12.0"

WORKDIR /opt/sidecar
COPY app.py /opt/sidecar/app.py

# Healthcheck — sidecar must respond 200 to /healthz before gateway
# routes deface jobs to it (FR-DEFACE-8: unhealthy => quarantine path).
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8090/healthz || exit 1

EXPOSE 8090

# tini reaps AFNI's subprocess zombies; uvicorn does the rest.
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8090", "--workers", "1"]
