# syntax=docker/dockerfile:1.6
# =============================================================================
# docker/unity/Dockerfile
# Base Unity CI image for the Unity build toolkit.
#
# Build:
#   docker build -f docker/unity/Dockerfile -t OWNER/unity-base:6000.0.26f1 .
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
# VENDOR: configurable image vendor label. Override with --build-arg VENDOR="My Org".
ARG VENDOR="Unity Build Toolkit"

LABEL org.opencontainers.image.title="Unity Build Image (base)" \
      org.opencontainers.image.description="Unity CI base image – no platform modules" \
      org.opencontainers.image.vendor="${VENDOR}" \
      org.opencontainers.image.version="${UNITY_VERSION}" \
      org.opencontainers.image.revision="${SOURCE_COMMIT}" \
      org.opencontainers.image.created="${BUILD_TIMESTAMP}" \
      org.unity.build.unity-version="${UNITY_VERSION}" \
      org.unity.build.changeset="${UNITY_CHANGESET}" \
      org.unity.build.variant="base" \
      org.unity.build.modules="" \
      org.unity.build.tooling-version="${TOOLING_VERSION}" \
      org.unity.build.contract-version="${CONTRACT_VERSION}"

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
COPY scripts/common/resolve_activation_strategy.sh /usr/local/share/unity-build-workflows/scripts/common/resolve_activation_strategy.sh

RUN chmod 755 \
        /usr/local/bin/entrypoint.sh \
        /usr/local/bin/healthcheck.sh \
        /usr/local/bin/activate-license.sh \
        /usr/local/bin/return-license.sh \
        /usr/local/share/unity-build-workflows/scripts/common/resolve_activation_strategy.sh

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
