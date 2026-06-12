#!/usr/bin/env bash
# =============================================================================
# activate-license.sh — Unity license activation for BuzzelStudio containers
#
# Activation strategy (in priority order):
#   1. UNITY_LICENSE env var     – ULF file content (base64 or raw XML)
#   2. UNITY_EMAIL + UNITY_PASSWORD – interactive serial activation
#
# Security:
#   - License content is NEVER printed to stdout/stderr
#   - Temp file created at restrictive 600 permissions
#   - Temp file path is not logged
#
# Returns:
#   0  – activation succeeded
#   1  – activation failed (details in Editor.log)
# =============================================================================
set -Eeuo pipefail

UNITY_EDITOR="${UNITY_EDITOR:-/usr/bin/unity-editor}"
UNITY_LOG_FILE="${UNITY_LOG_FILE:-/tmp/unity-home/Editor.log}"
TEMP_LICENSE_FILE=""

# ---------------------------------------------------------------------------
# Logging — never log license content
# ---------------------------------------------------------------------------
log_info()  { echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] [INFO]  activate-license: $*" >&2; }
log_error() { echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] [ERROR] activate-license: $*" >&2; }

cleanup_temp_license() {
    if [[ -n "${TEMP_LICENSE_FILE}" && -f "${TEMP_LICENSE_FILE}" ]]; then
        rm -f "${TEMP_LICENSE_FILE}" 2>/dev/null || true
    fi
}
trap cleanup_temp_license EXIT

# ---------------------------------------------------------------------------
# Helper: preserve Editor.log on failure
# ---------------------------------------------------------------------------
preserve_log_on_failure() {
    local dest="${1:-/tmp/unity-home/activation-failure-Editor.log}"
    if [[ -f "${UNITY_LOG_FILE}" ]]; then
        cp -f "${UNITY_LOG_FILE}" "${dest}" 2>/dev/null || true
        log_error "Editor.log preserved at: ${dest}"
    fi
}

# ---------------------------------------------------------------------------
# Strategy 1: UNITY_LICENSE (ULF file content)
# ---------------------------------------------------------------------------
if [[ -n "${UNITY_LICENSE:-}" ]]; then
    log_info "Activating via UNITY_LICENSE (file-content strategy)"

    TEMP_LICENSE_FILE="$(mktemp /tmp/unity-license-XXXXXXXX.ulf)"
    chmod 600 "${TEMP_LICENSE_FILE}"

    # Write the license content – support both raw XML and base64-encoded
    if echo "${UNITY_LICENSE}" | base64 -d > /dev/null 2>&1; then
        echo "${UNITY_LICENSE}" | base64 -d > "${TEMP_LICENSE_FILE}"
    else
        printf '%s' "${UNITY_LICENSE}" > "${TEMP_LICENSE_FILE}"
    fi

    log_info "Invoking Unity -manualLicenseFile (details redacted)"

    if "${UNITY_EDITOR}" \
            -batchmode \
            -nographics \
            -manualLicenseFile "${TEMP_LICENSE_FILE}" \
            -logFile "${UNITY_LOG_FILE}" \
            -quit 2>&1; then
        log_info "License activation succeeded (UNITY_LICENSE)"
        exit 0
    else
        unity_exit=$?
        log_error "License activation failed (UNITY_LICENSE), Unity exit code: ${unity_exit}"
        preserve_log_on_failure
        exit 1
    fi
fi

# ---------------------------------------------------------------------------
# Strategy 2: UNITY_EMAIL + UNITY_PASSWORD (serial / interactive)
# ---------------------------------------------------------------------------
if [[ -n "${UNITY_EMAIL:-}" && -n "${UNITY_PASSWORD:-}" ]]; then
    log_info "Activating via UNITY_EMAIL / UNITY_PASSWORD strategy"

    # Build the activation arguments without logging credentials
    activation_args=(
        -batchmode
        -nographics
        -username "${UNITY_EMAIL}"
        -password "${UNITY_PASSWORD}"
        -logFile  "${UNITY_LOG_FILE}"
        -quit
    )

    if [[ -n "${UNITY_SERIAL:-}" ]]; then
        log_info "Serial key detected (UNITY_SERIAL) – using serial activation"
        activation_args+=(-serial "${UNITY_SERIAL}")
    else
        log_info "No serial key provided – attempting personal/plus license activation"
    fi

    if "${UNITY_EDITOR}" "${activation_args[@]}" 2>&1; then
        log_info "License activation succeeded (email/password)"
        exit 0
    else
        unity_exit=$?
        log_error "License activation failed (email/password), Unity exit code: ${unity_exit}"
        preserve_log_on_failure
        exit 1
    fi
fi

# ---------------------------------------------------------------------------
# No credentials found
# ---------------------------------------------------------------------------
log_info "No license credentials found (UNITY_LICENSE, UNITY_EMAIL, UNITY_PASSWORD are all unset)"
log_info "Continuing without activation — Unity may run with a limited personal license"
exit 0
