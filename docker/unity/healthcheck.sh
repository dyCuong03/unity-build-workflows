#!/usr/bin/env bash
# =============================================================================
# healthcheck.sh — Docker HEALTHCHECK for Unity build toolkit containers
#
# Exits 0 (healthy) or 1 (unhealthy).
# Runs as the HEALTHCHECK CMD inside the container.
# =============================================================================
set -Eeuo pipefail

UNITY_EDITOR="${UNITY_EDITOR:-/usr/bin/unity-editor}"
REQUIRED_DISK_MB="${HEALTHCHECK_MIN_DISK_MB:-512}"

fail() { echo "[HEALTHCHECK] FAIL: $*" >&2; exit 1; }
ok()   { echo "[HEALTHCHECK] OK: $*"; }

# ---------------------------------------------------------------------------
# 1. Unity executable exists and is executable
# ---------------------------------------------------------------------------
if [[ ! -x "${UNITY_EDITOR}" ]]; then
    fail "Unity editor not found or not executable at: ${UNITY_EDITOR}"
fi
ok "Unity editor found: ${UNITY_EDITOR}"

# ---------------------------------------------------------------------------
# 2. Unity reports a version string (quick sanity that the binary is intact)
# ---------------------------------------------------------------------------
if ! unity_version_output=$("${UNITY_EDITOR}" -version 2>/dev/null); then
    # Some GameCI builds return non-zero on -version; tolerate that
    true
fi
if [[ -z "${unity_version_output:-}" ]]; then
    # Fall back: check the env var set by the Dockerfile
    unity_version_output="${UNITY_VERSION:-unknown}"
fi
ok "Unity version: ${unity_version_output}"

# ---------------------------------------------------------------------------
# 3. Writable directories
# ---------------------------------------------------------------------------
for dir in /tmp/unity-home /workspace; do
    if [[ ! -d "${dir}" ]]; then
        fail "Required directory missing: ${dir}"
    fi
    if ! touch "${dir}/.healthcheck_probe" 2>/dev/null; then
        fail "Directory not writable: ${dir}"
    fi
    rm -f "${dir}/.healthcheck_probe"
    ok "Directory writable: ${dir}"
done

# ---------------------------------------------------------------------------
# 4. Minimum free disk space on /workspace
# ---------------------------------------------------------------------------
available_mb=$(df -BM /workspace 2>/dev/null | awk 'NR==2 {gsub("M",""); print $4}')
if [[ -z "${available_mb}" ]]; then
    fail "Could not determine disk space for /workspace"
fi
if [[ "${available_mb}" -lt "${REQUIRED_DISK_MB}" ]]; then
    fail "Insufficient disk space: ${available_mb}MB available, need ${REQUIRED_DISK_MB}MB on /workspace"
fi
ok "Disk space: ${available_mb}MB available on /workspace"

# ---------------------------------------------------------------------------
# 5. Tooling scripts are present
# ---------------------------------------------------------------------------
for script in /usr/local/bin/entrypoint.sh \
              /usr/local/bin/activate-license.sh \
              /usr/local/bin/return-license.sh; do
    if [[ ! -x "${script}" ]]; then
        fail "Required script missing or not executable: ${script}"
    fi
done
ok "All tooling scripts present"

echo "[HEALTHCHECK] Container is healthy"
exit 0
