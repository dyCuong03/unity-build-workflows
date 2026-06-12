# syntax=docker/dockerfile:1.6
# =============================================================================
# docker/unity/Dockerfile
# Base Unity CI image for BuzzelStudio build workflows.
#
# Build:
#   docker build -f docker/unity/Dockerfile -t buzzelstudio/unity-base:6000.0.26f1 .
#
# All Unity commands are invoked exclusively through entrypoint.sh.
# Do NOT bake secrets, licenses, or credentials into this image.
# =============================================================================

ARG UNITY_VERSION=6000.0.26f1
ARG UNITY_CHANGESET=a5cf46f7893b
ARG BASE_IMAGE_TAG=${UNITY_VERSION}-base-3

FROM unityci/editor:${BASE_IMAGE_TAG} AS base

# ---------------------------------------------------------------------------
# OCI / image metadata labels
# ---------------------------------------------------------------------------
ARG UNITY_VERSION
ARG UNITY_CHANGESET
ARG TOOLING_VERSION=1.0.0
ARG BUILD_TIMESTAMP
ARG SOURCE_COMMIT
ARG CONTRACT_VERSION=1

LABEL org.opencontainers.image.title="BuzzelStudio Unity Build Base" \
      org.opencontainers.image.description="Organization Unity CI base image – no platform modules" \
      org.opencontainers.image.vendor="BuzzelStudio" \
      org.opencontainers.image.version="${UNITY_VERSION}" \
      org.opencontainers.image.revision="${SOURCE_COMMIT}" \
      org.opencontainers.image.created="${BUILD_TIMESTAMP}" \
      com.buzzelstudio.unity.version="${UNITY_VERSION}" \
      com.buzzelstudio.unity.changeset="${UNITY_CHANGESET}" \
      com.buzzelstudio.unity.variant="base" \
      com.buzzelstudio.unity.modules="" \
      com.buzzelstudio.tooling.version="${TOOLING_VERSION}" \
      com.buzzelstudio.contract.version="${CONTRACT_VERSION}"

# ---------------------------------------------------------------------------
# System dependencies layer
# Keep this layer separate so dep updates don't invalidate the Unity layer.
# ---------------------------------------------------------------------------
RUN apt-get update -qq && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        python3 \
        python3-pip \
        jq \
        curl \
        ca-certificates \
        git \
        rsync \
        unzip \
        zip \
        gettext-base \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# ---------------------------------------------------------------------------
# Non-root user support
# The image supports arbitrary UID/GID via --user at runtime.
# We create a named "unity" user as a convenience default.
# HOME is set to /tmp/unity-home so it is always writable regardless of UID.
# ---------------------------------------------------------------------------
ARG UNITY_UID=1000
ARG UNITY_GID=1000

RUN groupadd --gid "${UNITY_GID}" unity 2>/dev/null || true && \
    useradd --uid "${UNITY_UID}" --gid "${UNITY_GID}" \
            --shell /bin/bash \
            --no-create-home \
            unity 2>/dev/null || true

# Writable home at /tmp/unity-home; actual bind-mount workspace at /workspace.
ENV HOME=/tmp/unity-home
RUN mkdir -p /tmp/unity-home && \
    chmod 1777 /tmp/unity-home

# ---------------------------------------------------------------------------
# Workspace directory – will be bind-mounted at runtime
# ---------------------------------------------------------------------------
RUN mkdir -p /workspace
WORKDIR /workspace

# ---------------------------------------------------------------------------
# Copy organisation tooling scripts
# ---------------------------------------------------------------------------
COPY docker/unity/entrypoint.sh       /usr/local/bin/entrypoint.sh
COPY docker/unity/healthcheck.sh      /usr/local/bin/healthcheck.sh
COPY docker/unity/activate-license.sh /usr/local/bin/activate-license.sh
COPY docker/unity/return-license.sh   /usr/local/bin/return-license.sh

RUN chmod 755 \
        /usr/local/bin/entrypoint.sh \
        /usr/local/bin/healthcheck.sh \
        /usr/local/bin/activate-license.sh \
        /usr/local/bin/return-license.sh

# ---------------------------------------------------------------------------
# Runtime environment defaults
# Downstream images / callers override these via --env or --env-file.
# ---------------------------------------------------------------------------
ENV UNITY_VERSION="${UNITY_VERSION}" \
    UNITY_EDITOR=/usr/bin/unity-editor \
    BUILD_TARGET="" \
    BUILD_CONFIG="" \
    BUILD_ENVIRONMENT="development" \
    BUILD_OUTPUT_PATH=/workspace/Builds \
    TEST_RESULTS_PATH=/workspace/TestResults \
    LOG_DIR=/workspace/Logs \
    UNITY_LOG_FILE=/tmp/unity-home/Editor.log \
    TOOLING_VERSION="${TOOLING_VERSION}"

# ---------------------------------------------------------------------------
# Health check – runs before the container is considered "healthy"
# ---------------------------------------------------------------------------
HEALTHCHECK --interval=30s --timeout=15s --start-period=10s --retries=3 \
    CMD ["/usr/local/bin/healthcheck.sh"]

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["inspect"]
