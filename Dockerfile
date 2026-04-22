############################
# Stage 1 — builder
############################
FROM python:3.11-bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# Install build deps and create a clean virtualenv with pinned wheels.
RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential \
 && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY src ./src
COPY README.md ./

RUN python -m venv /opt/radivault-venv \
 && /opt/radivault-venv/bin/pip install --upgrade pip \
 && /opt/radivault-venv/bin/pip install .[mock]

############################
# Stage 2 — runtime
############################
FROM python:3.11-slim-bookworm AS runtime

ARG APP_UID=10001
ARG APP_GID=10001

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/radivault-venv/bin:${PATH}" \
    RADIVAULT_CONFIG=/etc/radivault/gateway.yml

RUN groupadd --system --gid ${APP_GID} radivault \
 && useradd --system --uid ${APP_UID} --gid ${APP_GID} --home-dir /var/lib/radivault \
    --shell /usr/sbin/nologin radivault \
 && mkdir -p /var/lib/radivault/staging /var/log/radivault /etc/radivault \
 && chown -R radivault:radivault /var/lib/radivault /var/log/radivault /etc/radivault

COPY --from=builder /opt/radivault-venv /opt/radivault-venv

USER radivault:radivault
WORKDIR /var/lib/radivault

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -m radivault_gateway version >/dev/null || exit 1

ENTRYPOINT ["radivault-gateway"]
CMD ["start"]
