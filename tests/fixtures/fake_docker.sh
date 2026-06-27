#!/usr/bin/env bash
# fake_docker.sh — Fake Docker executable for end-to-end pipeline testing.
#
# Drop this on PATH as 'docker' to intercept all docker calls from
# run_unity_container.py and workflow scripts without requiring a real
# Docker daemon or Unity image.
#
# Behaviour is controlled by FAKE_DOCKER_MODE environment variable:
#   success         (default) exit 0, write fake build artifact
#   pull_failure    exit 1 on 'docker pull' with registry error message
#   oom_killed      exit 137 (SIGKILL / OOM) with OOM message in output
#   exit_nonzero    exit 1 after Unity build simulation (compile error)
#   timeout         sleep indefinitely (caller must kill with timeout)
#   image_not_found exit 125 with "Unable to find image" error message
#
# Reads:
#   FAKE_DOCKER_MODE        — behaviour selector (default: success)
#   FAKE_DOCKER_OUTPUT_DIR  — directory to write fake artifact into (default: /tmp/fake_docker_out)
#   FAKE_DOCKER_LOG_FILE    — path to write fake container log (default: /tmp/fake_docker.log)
#
# All docker subcommands (run, pull, inspect, images, rmi, etc.) are handled.
# Only 'run' and 'pull' have mode-specific behaviour — other subcommands
# always exit 0 with minimal output.

MODE="${FAKE_DOCKER_MODE:-success}"
OUTPUT_DIR="${FAKE_DOCKER_OUTPUT_DIR:-/tmp/fake_docker_out}"
LOG_FILE="${FAKE_DOCKER_LOG_FILE:-/tmp/fake_docker.log}"

SUBCOMMAND="${1:-run}"

# ---------------------------------------------------------------------------
# Minimal implementations of non-run subcommands
# ---------------------------------------------------------------------------

case "$SUBCOMMAND" in
  inspect)
    # docker inspect returns a JSON array; must include required OCI labels
    echo '[{"Id":"fake123","RepoTags":["fake/unity:test"],"Config":{"Labels":{"org.opencontainers.image.version":"2022.3.21f1","org.unity.build.unity-version":"2022.3.21f1","org.unity.build.variant":"android","org.unity.build.contract-version":"1"}}}]'
    exit 0
    ;;
  images)
    printf "REPOSITORY\tTAG\tIMAGE ID\tCREATED\tSIZE\n"
    printf "fake/unity\ttest\tfake12345678\t1 hour ago\t5.00GB\n"
    exit 0
    ;;
  pull)
    case "$MODE" in
      pull_failure)
        echo "Error response from daemon: Get \"https://ghcr.io/v2/\": dial tcp: lookup ghcr.io: no such host" >&2
        echo "Error: failed to pull image" >&2
        exit 1
        ;;
      image_not_found)
        echo "Unable to find image 'fake/unity:nonexistent' locally" >&2
        echo "Error response from daemon: manifest for fake/unity:nonexistent not found: manifest unknown" >&2
        exit 125
        ;;
      *)
        echo "Pulling from fake registry..."
        echo "Status: Image is up to date for fake/unity:test"
        exit 0
        ;;
    esac
    ;;
  rmi|tag|push|network|volume|container)
    exit 0
    ;;
  run)
    # Fall through to run-specific behaviour below
    ;;
  *)
    # Unknown subcommand — exit 0 silently
    exit 0
    ;;
esac

# ---------------------------------------------------------------------------
# docker run simulation
# ---------------------------------------------------------------------------

# Write a fake container log regardless of outcome
mkdir -p "$(dirname "$LOG_FILE")"
cat > "$LOG_FILE" <<EOF
=== FAKE DOCKER CONTAINER LOG ===
Mode: $MODE
Arguments: $*
Image: $(echo "$@" | grep -oP 'ghcr\.io/\S+' | head -1 || echo "fake/unity:test")
Container ID: fake_container_$(date +%s)
[Unity] Initializing engine...
[Unity] Loading project...
EOF

case "$MODE" in
  # ── success: write a fake build artifact and exit 0 ──────────────────────
  success)
    echo "[Unity] Build started." >> "$LOG_FILE"
    echo "[Unity] Compiling scripts..." >> "$LOG_FILE"
    echo "[Unity] Build succeeded." >> "$LOG_FILE"
    mkdir -p "$OUTPUT_DIR"
    echo "FAKE_BUILD_ARTIFACT_$(date +%s)" > "$OUTPUT_DIR/game.apk"
    echo "Fake docker run succeeded. Artifact: $OUTPUT_DIR/game.apk"
    exit 0
    ;;

  # ── pull_failure: image pull fails before container even starts ───────────
  pull_failure)
    echo "Unable to find image 'fake/unity:test' locally" >&2
    echo "Error response from daemon: Get \"https://ghcr.io/v2/\": dial tcp: lookup ghcr.io: no such host" >&2
    exit 1
    ;;

  # ── oom_killed: container killed by OOM killer (exit 137 = SIGKILL) ───────
  oom_killed)
    cat >> "$LOG_FILE" <<EOF
[Unity] Loading large asset bundle...
[Unity] Loading large asset bundle...
Killed
EOF
    echo "Container killed by OOM killer (exit 137)" >&2
    echo "[Fake docker] OOM kill simulated." >&2
    exit 137
    ;;

  # ── exit_nonzero: Unity build fails inside the container ─────────────────
  exit_nonzero)
    cat >> "$LOG_FILE" <<EOF
Assets/Scripts/GameManager.cs(42,10): error CS0103: The name 'NonExistent' does not exist
Error building Player because scripts had compiler errors
[Unity] Build FAILED.
EOF
    echo "[Fake docker] Build failed (compile error)." >&2
    exit 1
    ;;

  # ── timeout: container runs indefinitely (test must kill it) ─────────────
  timeout)
    echo "[Fake docker] Simulating hung container (sleep indefinitely)." >> "$LOG_FILE"
    sleep 99999
    ;;

  # ── image_not_found: image not in local cache and pull disabled ───────────
  image_not_found)
    echo "Unable to find image 'fake/unity:nonexistent' locally" >&2
    echo "docker: Error response from daemon: manifest for fake/unity:nonexistent not found." >&2
    exit 125
    ;;

  # ── unknown mode ──────────────────────────────────────────────────────────
  *)
    echo "[Fake docker] Unknown FAKE_DOCKER_MODE: $MODE" >&2
    exit 1
    ;;
esac
