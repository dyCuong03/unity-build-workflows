# syntax=docker/dockerfile:1.6
# =============================================================================
# docker/variants/webgl.Dockerfile
# Unity WebGL build image for the Unity build toolkit.
#
# GameCI webgl image includes: Emscripten toolchain.
#
# Build:
#   docker build -f docker/variants/webgl.Dockerfile \
#     -t OWNER/unity-webgl:6000.0.26f1 .
# =============================================================================

ARG UNITY_VERSION=6000.0.26f1
ARG BASE_IMAGE_TAG=${UNITY_VERSION}-webgl-3

FROM unityci/editor:${BASE_IMAGE_TAG} AS webgl-base

# ---------------------------------------------------------------------------
# OCI labels
# ---------------------------------------------------------------------------
ARG UNITY_VERSION
ARG UNITY_CHANGESET=a5cf46f7893b
ARG TOOLING_VERSION=1.0.0
ARG BUILD_TIMESTAMP
ARG SOURCE_COMMIT
ARG CONTRACT_VERSION=1
# VENDOR: configurable image vendor label. Override with --build-arg VENDOR="My Org".
ARG VENDOR="Unity Build Toolkit"

LABEL org.opencontainers.image.title="Unity Build Image (webgl)" \
      org.opencontainers.image.description="Unity WebGL build image with Emscripten" \
      org.opencontainers.image.vendor="${VENDOR}" \
      org.opencontainers.image.version="${UNITY_VERSION}" \
      org.opencontainers.image.revision="${SOURCE_COMMIT}" \
      org.opencontainers.image.created="${BUILD_TIMESTAMP}" \
      org.unity.build.unity-version="${UNITY_VERSION}" \
      org.unity.build.changeset="${UNITY_CHANGESET}" \
      org.unity.build.variant="webgl" \
      org.unity.build.modules="webgl" \
      org.unity.build.tooling-version="${TOOLING_VERSION}" \
      org.unity.build.contract-version="${CONTRACT_VERSION}"

# ---------------------------------------------------------------------------
# System deps and WebGL tooling
# ---------------------------------------------------------------------------
RUN apt-get update -qq && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        python3 \
        python3-pip \
        jq \
        curl \
        ca-certificates \
        rsync \
        unzip \
        zip \
        gettext-base \
        brotli \
        gzip \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# ---------------------------------------------------------------------------
# WebGL / Emscripten – GameCI already installs emsdk at /emsdk
# Expose EMSDK env vars so Unity can locate the toolchain
# ---------------------------------------------------------------------------
ENV EMSDK=/emsdk \
    EM_CONFIG=/emsdk/.emscripten \
    EMSDK_QUIET=1

# Emscripten writes temp/cache files; put them in /tmp for writability
ENV EM_CACHE=/tmp/emscripten-cache
RUN mkdir -p /tmp/emscripten-cache && chmod 1777 /tmp/emscripten-cache

# ---------------------------------------------------------------------------
# Non-root user support
# ---------------------------------------------------------------------------
ARG UNITY_UID=1000
ARG UNITY_GID=1000

RUN groupadd --gid "${UNITY_GID}" unity 2>/dev/null || true && \
    useradd --uid "${UNITY_UID}" --gid "${UNITY_GID}" \
            --shell /bin/bash \
            --no-create-home \
            unity 2>/dev/null || true

ENV HOME=/tmp/unity-home
RUN mkdir -p /tmp/unity-home && chmod 1777 /tmp/unity-home

RUN mkdir -p /workspace
WORKDIR /workspace

# ---------------------------------------------------------------------------
# Tooling scripts
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
# Runtime defaults
# ---------------------------------------------------------------------------
ENV UNITY_VERSION="${UNITY_VERSION}" \
    UNITY_EDITOR=/usr/bin/unity-editor \
    BUILD_TARGET="WebGL" \
    BUILD_ENVIRONMENT="development" \
    BUILD_OUTPUT_PATH=/workspace/Builds \
    TEST_RESULTS_PATH=/workspace/TestResults \
    LOG_DIR=/workspace/Logs \
    UNITY_LOG_FILE=/tmp/unity-home/Editor.log \
    TOOLING_VERSION="${TOOLING_VERSION}"

HEALTHCHECK --interval=30s --timeout=15s --start-period=10s --retries=3 \
    CMD ["/usr/local/bin/healthcheck.sh"]

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["inspect"]
