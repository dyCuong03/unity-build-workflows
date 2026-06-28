# syntax=docker/dockerfile:1.6
# =============================================================================
# docker/variants/android.Dockerfile
# Unity Android build image for the Unity build toolkit.
#
# GameCI android image includes: Android SDK, NDK, OpenJDK 17.
#
# Build:
#   docker build -f docker/variants/android.Dockerfile \
#     -t OWNER/unity-android:6000.0.26f1 .
# =============================================================================

ARG UNITY_VERSION=6000.0.26f1
ARG BASE_IMAGE_TAG=${UNITY_VERSION}-android-3

FROM unityci/editor:${BASE_IMAGE_TAG} AS android-base

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

LABEL org.opencontainers.image.title="Unity Build Image (android)" \
      org.opencontainers.image.description="Unity Android build image with SDK/NDK/JDK" \
      org.opencontainers.image.vendor="${VENDOR}" \
      org.opencontainers.image.version="${UNITY_VERSION}" \
      org.opencontainers.image.revision="${SOURCE_COMMIT}" \
      org.opencontainers.image.created="${BUILD_TIMESTAMP}" \
      org.unity.build.unity-version="${UNITY_VERSION}" \
      org.unity.build.changeset="${UNITY_CHANGESET}" \
      org.unity.build.variant="android" \
      org.unity.build.modules="android,android-sdk-ndk-tools" \
      org.unity.build.tooling-version="${TOOLING_VERSION}" \
      org.unity.build.contract-version="${CONTRACT_VERSION}"

# ---------------------------------------------------------------------------
# Extra system deps (beyond what GameCI android image provides)
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
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# ---------------------------------------------------------------------------
# Android SDK / NDK environment variables
# GameCI images place SDK at /opt/android-sdk-linux
# ---------------------------------------------------------------------------
ENV ANDROID_HOME=/opt/android-sdk-linux \
    ANDROID_SDK_ROOT=/opt/android-sdk-linux \
    ANDROID_NDK_HOME=/opt/android-sdk-linux/ndk-bundle

# Gradle home under /tmp so it's always writable regardless of runtime UID
ENV GRADLE_USER_HOME=/tmp/gradle-cache

RUN mkdir -p /tmp/gradle-cache && chmod 1777 /tmp/gradle-cache

# Pre-create Gradle wrapper / cache dirs to avoid permission errors on first run
RUN mkdir -p /tmp/gradle-cache/wrapper /tmp/gradle-cache/caches && \
    chmod -R 775 /tmp/gradle-cache

# ---------------------------------------------------------------------------
# Non-root user support (mirrors base Dockerfile)
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
COPY scripts/common/resolve_activation_strategy.sh /usr/local/share/unity-build-workflows/scripts/common/resolve_activation_strategy.sh

RUN chmod 755 \
        /usr/local/bin/entrypoint.sh \
        /usr/local/bin/healthcheck.sh \
        /usr/local/bin/activate-license.sh \
        /usr/local/bin/return-license.sh \
        /usr/local/share/unity-build-workflows/scripts/common/resolve_activation_strategy.sh

# ---------------------------------------------------------------------------
# Runtime environment defaults
# ---------------------------------------------------------------------------
ENV UNITY_VERSION="${UNITY_VERSION}" \
    UNITY_EDITOR=/usr/bin/unity-editor \
    BUILD_TARGET="Android" \
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
