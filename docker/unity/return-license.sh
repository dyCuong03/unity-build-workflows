#!/usr/bin/env bash
# =============================================================================
# return-license.sh — Return Unity license and clean up temp credential files
#
# Called from entrypoint.sh cleanup trap; must ALWAYS succeed.
# A failed license return must not fail the overall build.
#
# Cleans up:
#   - /tmp/unity-license-*.ulf  (temp license files written by activate-license.sh)
#   - /tmp/.unity3d             (Unity's internal license cache)
#   - /tmp/unity-home/.local/share/unity3d/Unity/  (per-home license store)
# =============================================================================
set -o pipefail  # intentionally NOT set -e so we always exit 0

UNITY_EDITOR="${UNITY_EDITOR:-/usr/bin/unity-editor}"
UNITY_LOG_FILE="${UNITY_LOG_FILE:-/tmp/unity-home/Editor.log}"
RETURN_LOG="/tmp/unity-home/return-license.log"

log_info()  { echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] [INFO]  return-license: $*" >&2; }
log_warn()  { echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] [WARN]  return-license: $*" >&2; }

# ---------------------------------------------------------------------------
# Only attempt a Unity return if a serial-based activation was used.
# File-content (ULF) and personal licenses do not need an explicit return.
# ---------------------------------------------------------------------------
if [[ -n "${UNITY_SERIAL:-}" && -n "${UNITY_EMAIL:-}" && -n "${UNITY_PASSWORD:-}" ]]; then
    log_info "Attempting to return serial license (UNITY_SERIAL detected)"

    if "${UNITY_EDITOR}" \
            -batchmode \
            -nographics \
            -username   "${UNITY_EMAIL}" \
            -password   "${UNITY_PASSWORD}" \
            -returnlicense \
            -logFile    "${RETURN_LOG}" \
            -quit 2>&1; then
        log_info "License returned successfully"
    else
        log_warn "Unity license return failed (exit code: $?) – continuing without return"
        log_warn "Return log: ${RETURN_LOG}"
    fi
else
    log_info "No serial credentials (UNITY_SERIAL/UNITY_EMAIL/UNITY_PASSWORD) – skipping license return"
fi

# ---------------------------------------------------------------------------
# Remove temp license files regardless of return outcome
# ---------------------------------------------------------------------------
find /tmp -maxdepth 1 -name "unity-license-*.ulf" -type f -exec rm -f {} + 2>/dev/null || true
find /tmp -maxdepth 1 -name ".unity3d"            -type f -exec rm -f {} + 2>/dev/null || true

# Clean per-home Unity license store (if HOME is set)
if [[ -n "${HOME:-}" ]]; then
    unity_license_dir="${HOME}/.local/share/unity3d/Unity"
    if [[ -d "${unity_license_dir}" ]]; then
        find "${unity_license_dir}" -name "*.ulf" -type f -exec rm -f {} + 2>/dev/null || true
        find "${unity_license_dir}" -name "*.alf" -type f -exec rm -f {} + 2>/dev/null || true
        log_info "Cleaned Unity license store: ${unity_license_dir}"
    fi
fi

log_info "License cleanup complete"
# Always succeed – a license return failure must not abort the build pipeline
exit 0
