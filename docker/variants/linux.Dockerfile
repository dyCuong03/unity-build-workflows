# syntax=docker/dockerfile:1.6
# =============================================================================
# docker/variants/linux.Dockerfile
# Unity Linux build image for BuzzelStudio.
# Supports StandaloneLinux64 and LinuxServer targets.
#
# GameCI linux-il2cpp image includes: IL2CPP toolchain, GCC, libstdc++.
#
# Build:
#   docker build -f docker/variants/linux.Dockerfile \
#     -t buzzelstudio/unity-linux:6000.0.26f1 .
# =============================================================================

ARG UNITY_VERSION=6000.0.26f1
ARG BASE_IMAGE_TAG=${UNITY_VERSION}-linux-il2cpp-3

FROM unityci/editor:${BASE_IMAGE_TAG} AS linux-base

# ---------------------------------------------------------------------------
# OCI labels
# ---------------------------------------------------------------------------
ARG UNITY_VERSION
ARG UNITY_CHANGESET=a5cf46f7893b
ARG TOOLING_VERSION=1.0.0
ARG BUILD_TIMESTAMP
ARG SOURCE_COMMIT

LABEL org.opencontainers.image.title="BuzzelStudio Unity Linux" \
      org.opencontainers.image.description="Unity Linux IL2CPP build image – StandaloneLinux64 + LinuxServer" \
      org.opencontainers.image.vendor="BuzzelStudio" \
      org.opencontainers.image.version="${UNITY_VERSION}" \
      org.opencontainers.image.revision="${SOURCE_COMMIT}" \
      org.opencontainers.image.created="${BUILD_TIMESTAMP}" \
      com.buzzelstudio.unity.version="${UNITY_VERSION}" \
      com.buzzelstudio.unity.changeset="${UNITY_CHANGESET}" \
      com.buzzelstudio.unity.variant="linux-il2cpp" \
      com.buzzelstudio.unity.modules="linux-il2cpp,linux-server" \
      com.buzzelstudio.tooling.version="${TOOLING_VERSION}"

# ---------------------------------------------------------------------------
# System deps
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
        # IL2CPP compilation dependencies
        build-essential \
        clang \
        libc6-dev \
        libstdc++-12-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

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
    BUILD_TARGET="StandaloneLinux64" \
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
