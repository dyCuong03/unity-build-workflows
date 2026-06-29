#!/usr/bin/env bash
# =============================================================================
# resolve_unity_version.sh — Unity version single-source-of-truth resolver
#
# Resolves the Unity editor version using the following precedence:
#   1. Environment variable UNITY_VERSION_INPUT (non-empty) — explicit override
#   2. .unityVersion field in config/unity-build-defaults.json
#   3. Fail with a clear error message naming the config path
#
# Usage:
#   UNITY_VERSION_INPUT="6000.0.26f1" bash resolve_unity_version.sh
#   bash resolve_unity_version.sh   # reads from config/unity-build-defaults.json
#
# Output:
#   Prints the resolved version string to stdout (and nothing else).
#   All log/diagnostic messages go to stderr.
#
# Exit codes:
#   0 — Version resolved successfully; printed to stdout
#   1 — Could not resolve version
# =============================================================================
set -Eeuo pipefail

# ---------------------------------------------------------------------------
# Logging — all log output goes to stderr only
# ---------------------------------------------------------------------------
_log_prefix="resolve-unity-version"
log_info()  { echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] [INFO]  ${_log_prefix}: $*" >&2; }
log_warn()  { echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] [WARN]  ${_log_prefix}: $*" >&2; }
log_error() { echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] [ERROR] ${_log_prefix}: $*" >&2; }

# ---------------------------------------------------------------------------
# Locate the config file relative to this script's directory
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
CONFIG_FILE="${REPO_ROOT}/config/unity-build-defaults.json"

# ---------------------------------------------------------------------------
# Precedence 1: explicit env var input
# ---------------------------------------------------------------------------
if [[ -n "${UNITY_VERSION_INPUT:-}" ]]; then
    log_info "Resolved from UNITY_VERSION_INPUT env var: ${UNITY_VERSION_INPUT}"
    printf '%s\n' "${UNITY_VERSION_INPUT}"
    exit 0
fi

# ---------------------------------------------------------------------------
# Precedence 2: config file
# ---------------------------------------------------------------------------
log_info "UNITY_VERSION_INPUT not set; reading from ${CONFIG_FILE}"

if [[ ! -f "${CONFIG_FILE}" ]]; then
    log_error "Config file not found: ${CONFIG_FILE}"
    log_error "Either set UNITY_VERSION_INPUT or create ${CONFIG_FILE} with a 'unityVersion' field."
    exit 1
fi

# Try python3 first (always available in CI), fall back to jq
VERSION=""
if command -v python3 >/dev/null 2>&1; then
    VERSION="$(python3 -c "import json,sys; d=json.load(open('${CONFIG_FILE}')); print(d['unityVersion'])" 2>/dev/null || true)"
elif command -v jq >/dev/null 2>&1; then
    VERSION="$(jq -r '.unityVersion // empty' "${CONFIG_FILE}" 2>/dev/null || true)"
else
    log_error "Neither python3 nor jq found; cannot parse ${CONFIG_FILE}"
    exit 1
fi

if [[ -z "${VERSION}" ]]; then
    log_error "Could not read 'unityVersion' from ${CONFIG_FILE}"
    log_error "Ensure the file exists and contains a non-empty 'unityVersion' field."
    exit 1
fi

log_info "Resolved from ${CONFIG_FILE}: ${VERSION}"
printf '%s\n' "${VERSION}"
