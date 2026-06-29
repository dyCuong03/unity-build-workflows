#!/usr/bin/env bash
# =============================================================================
# activate-license.sh — Unity license activation for Unity build toolkit
#
# Uses resolve_activation_strategy.sh to select the best activation method.
#
# Activation strategies (in priority order):
#   1. manual-ulf     — UNITY_LICENSE .ulf file content (base64 or raw XML)
#   2. serial         — UNITY_SERIAL + UNITY_EMAIL + UNITY_PASSWORD (Pro/Plus)
#   3. account        — UNITY_EMAIL + UNITY_PASSWORD (Personal/free)
#   4. preactivated   — Unity already activated on this runner
#   5. blocked        — No valid strategy; print guidance and exit 1
#
# UNITY_LICENSE is OPTIONAL. If not set, other strategies are attempted.
#
# Security:
#   - License content is NEVER printed to stdout/stderr
#   - Temp files created at restrictive 600 permissions
#   - Only secret presence (not values) is logged
#
# Returns:
#   0  — Activation succeeded or not needed (preactivated/none)
#   1  — Activation failed or blocked
# =============================================================================
set -Eeuo pipefail

UNITY_EDITOR="${UNITY_EDITOR:-/usr/bin/unity-editor}"
UNITY_LOG_FILE="${UNITY_LOG_FILE:-/tmp/unity-home/Editor.log}"
TEMP_LICENSE_FILE=""

# ---------------------------------------------------------------------------
# Logging — never log license content
# ---------------------------------------------------------------------------
log_info()  { echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] [INFO]  activate-license: $*" >&2; }
log_warn()  { echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] [WARN]  activate-license: $*" >&2; }
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
# Classify activation failure from Editor.log
# ---------------------------------------------------------------------------
classify_activation_failure() {
    local log_file="${1:-${UNITY_LOG_FILE}}"
    local exit_code="${2:-1}"

    if [[ ! -f "${log_file}" ]]; then
        echo "UNKNOWN_ACTIVATION_ERROR"
        return
    fi

    local log_content
    log_content="$(cat "${log_file}" 2>/dev/null || true)"

    if echo "${log_content}" | grep -qi "two.factor\|2fa\|multi.factor\|mfa"; then
        echo "MFA_OR_2FA_REQUIRED"
    elif echo "${log_content}" | grep -qi "invalid.*password\|wrong.*password\|auth.*fail\|login.*fail"; then
        echo "AUTH_FAILED"
    elif echo "${log_content}" | grep -qi "personal.*license.*online.*activation\|cannot activate personal"; then
        echo "PERSONAL_LICENSE_ONLINE_ACTIVATION_UNSUPPORTED"
    elif echo "${log_content}" | grep -qi "serial.*invalid\|invalid.*serial"; then
        echo "SERIAL_INVALID"
    elif echo "${log_content}" | grep -qi "activation.*limit\|seat.*limit\|maximum.*activation"; then
        echo "ACTIVATION_LIMIT_REACHED"
    elif echo "${log_content}" | grep -qi "service.*unavailable\|server.*error\|connect.*fail\|timeout"; then
        echo "UNITY_SERVICE_UNAVAILABLE"
    elif echo "${log_content}" | grep -qi "license.*invalid\|invalid.*license\|not.*valid.*license"; then
        echo "LICENSE_FILE_INVALID"
    else
        echo "UNKNOWN_ACTIVATION_ERROR"
    fi
}

# ---------------------------------------------------------------------------
# Preferred: GameCI-style combined Personal activation
# ---------------------------------------------------------------------------
# When a .ulf (UNITY_LICENSE) AND account credentials (UNITY_EMAIL +
# UNITY_PASSWORD) are BOTH provided, activate ONLINE with the .ulf in place.
# This mirrors game-ci/unity-builder and is the only reliable path for Unity
# Personal/free in ephemeral Docker:
#   - .ulf alone        → "TimeStamp validation failed" (machine-bound)
#   - email/pw alone     → "0 entitlements" (no seat without the .ulf)
#   - both together      → "Activation successful"
# UNITY_LICENSE is treated as RAW .ulf XML by default; base64 is auto-detected
# and decoded (set UNITY_LICENSE_ENCODING=raw to force raw, =base64 to force
# decode).
if [[ -n "${UNITY_LICENSE:-}" && -n "${UNITY_EMAIL:-}" && -n "${UNITY_PASSWORD:-}" ]]; then
    STRATEGY="personal-combined"
else
    # ── Check for pre-activated license (mounted from host) ────────────────
    # If license files are already present and no account credentials were
    # supplied to (re)activate online, trust the mounted license.
    UNITY_LICENSE_DIR="${HOME}/.local/share/unity3d/Unity"
    if ls "${UNITY_LICENSE_DIR}/"*.ulf 2>/dev/null | head -1 > /dev/null 2>&1; then
        log_info "Pre-activated license found at ${UNITY_LICENSE_DIR} — skipping activation"
        log_info "License files were likely mounted from the host runner"
        exit 0
    fi

    # ── Resolve activation strategy ────────────────────────────────────────
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

    # Strategy resolver can be in several locations depending on context
    STRATEGY_SCRIPT=""
    for candidate in \
        "${SCRIPT_DIR}/../../scripts/common/resolve_activation_strategy.sh" \
        "/usr/local/share/unity-build-workflows/scripts/common/resolve_activation_strategy.sh" \
        "${TOOLKIT_PATH:-}/scripts/common/resolve_activation_strategy.sh"; do
        if [[ -f "${candidate}" ]]; then
            STRATEGY_SCRIPT="$(realpath "${candidate}")"
            break
        fi
    done

    if [[ -n "${STRATEGY_SCRIPT}" ]]; then
        log_info "Using strategy resolver: ${STRATEGY_SCRIPT}"
        STRATEGY=$(bash "${STRATEGY_SCRIPT}" 2>&2)
    else
        # Inline fallback if resolver not found (backwards compat)
        log_warn "Strategy resolver not found — using inline detection"
        if [[ -n "${UNITY_LICENSE:-}" ]]; then
            STRATEGY="manual-ulf"
        elif [[ -n "${UNITY_SERIAL:-}" && -n "${UNITY_EMAIL:-}" && -n "${UNITY_PASSWORD:-}" ]]; then
            STRATEGY="serial"
        elif [[ -n "${UNITY_EMAIL:-}" && -n "${UNITY_PASSWORD:-}" ]]; then
            STRATEGY="account"
        elif [[ -z "${UNITY_LICENSE:-}" && -z "${UNITY_EMAIL:-}" ]]; then
            log_info "No license credentials found — continuing without activation"
            log_info "Unity may run with a limited personal license"
            exit 0
        else
            STRATEGY="blocked"
        fi
    fi
fi

log_info "Selected activation strategy: ${STRATEGY}"

# ---------------------------------------------------------------------------
# Execute activation strategy
# ---------------------------------------------------------------------------
case "${STRATEGY}" in

    # ── Strategy 0: Combined Personal (GameCI-style) ────────────────────────
    personal-combined)
        log_info "Activating via UNITY_LICENSE (.ulf) + UNITY_EMAIL/UNITY_PASSWORD (combined)"

        # Ensure a .ulf is present in the license dir for the licensing client.
        # If the dir is a read-only host mount that already holds one, reuse it;
        # otherwise materialise UNITY_LICENSE (raw by default, base64 honoured).
        ULF_DIR="${HOME}/.local/share/unity3d/Unity"
        if ls "${ULF_DIR}/"*.ulf >/dev/null 2>&1; then
            log_info "Reusing .ulf already present in license dir"
        elif mkdir -p "${ULF_DIR}" 2>/dev/null; then
            ULF_DEST="${ULF_DIR}/Unity_lic.ulf"
            case "${UNITY_LICENSE_ENCODING:-auto}" in
                base64) echo "${UNITY_LICENSE}" | base64 -d > "${ULF_DEST}" 2>/dev/null || true ;;
                raw)    printf '%s' "${UNITY_LICENSE}" > "${ULF_DEST}" 2>/dev/null || true ;;
                *)      if echo "${UNITY_LICENSE}" | base64 -d >/dev/null 2>&1; then
                            echo "${UNITY_LICENSE}" | base64 -d > "${ULF_DEST}" 2>/dev/null || true
                        else
                            printf '%s' "${UNITY_LICENSE}" > "${ULF_DEST}" 2>/dev/null || true
                        fi ;;
            esac
            [[ -f "${ULF_DEST}" ]] && chmod 600 "${ULF_DEST}" 2>/dev/null || true
            log_info "Placed .ulf in license dir (content redacted)"
        else
            log_warn "License dir not writable; relying on online activation only"
        fi

        if "${UNITY_EDITOR}" \
                -batchmode \
                -nographics \
                -username "${UNITY_EMAIL}" \
                -password "${UNITY_PASSWORD}" \
                -logFile "${UNITY_LOG_FILE}" \
                -quit 2>&1; then
            log_info "License activation succeeded (personal-combined)"
            exit 0
        else
            unity_exit=$?
            FAILURE_CLASS=$(classify_activation_failure "${UNITY_LOG_FILE}" "${unity_exit}")
            log_error "License activation failed (personal-combined): ${FAILURE_CLASS}"
            log_error "Unity exit code: ${unity_exit}"
            preserve_log_on_failure
            # Last-resort fallbacks (do not give up while another path exists)
            if [[ -n "${UNITY_SERIAL:-}" ]]; then
                log_info "Falling back to serial activation"
                STRATEGY="serial"
            else
                log_info "Falling back to manual-ulf activation"
                STRATEGY="manual-ulf"
            fi
        fi
        ;;&  # Fall through to re-match the updated STRATEGY

    # ── Strategy 1: Manual ULF ──────────────────────────────────────────────
    manual-ulf)
        log_info "Activating via UNITY_LICENSE (manualLicenseFile strategy)"

        TEMP_LICENSE_FILE="$(mktemp /tmp/unity-license-XXXXXXXX.ulf)"
        chmod 600 "${TEMP_LICENSE_FILE}"

        # Write the license content — support both raw XML and base64-encoded
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
            log_info "License activation succeeded (manual-ulf)"
            exit 0
        else
            unity_exit=$?
            FAILURE_CLASS=$(classify_activation_failure "${UNITY_LOG_FILE}" "${unity_exit}")
            log_error "License activation failed (manual-ulf): ${FAILURE_CLASS}"
            log_error "Unity exit code: ${unity_exit}"
            preserve_log_on_failure

            # If ULF is invalid, try fallback strategies
            if [[ "${FAILURE_CLASS}" == "LICENSE_FILE_INVALID" ]]; then
                log_warn "UNITY_LICENSE file appears invalid — attempting fallback strategies"

                # Try serial if available
                if [[ -n "${UNITY_SERIAL:-}" && -n "${UNITY_EMAIL:-}" && -n "${UNITY_PASSWORD:-}" ]]; then
                    log_info "Falling back to serial activation"
                    STRATEGY="serial"
                    # Fall through to serial case below
                elif [[ -n "${UNITY_EMAIL:-}" && -n "${UNITY_PASSWORD:-}" ]]; then
                    log_info "Falling back to account activation"
                    STRATEGY="account"
                    # Fall through to account case below
                else
                    exit 1
                fi
            else
                exit 1
            fi
        fi
        ;;&  # Fall through to check if STRATEGY was updated

    # ── Strategy 2: Serial activation (Pro/Plus/Enterprise) ─────────────────
    serial)
        log_info "Activating via UNITY_SERIAL + credentials (serial strategy)"

        if "${UNITY_EDITOR}" \
                -batchmode \
                -nographics \
                -username "${UNITY_EMAIL}" \
                -password "${UNITY_PASSWORD}" \
                -serial "${UNITY_SERIAL}" \
                -logFile "${UNITY_LOG_FILE}" \
                -quit 2>&1; then
            log_info "License activation succeeded (serial)"
            exit 0
        else
            unity_exit=$?
            FAILURE_CLASS=$(classify_activation_failure "${UNITY_LOG_FILE}" "${unity_exit}")
            log_error "License activation failed (serial): ${FAILURE_CLASS}"
            log_error "Unity exit code: ${unity_exit}"
            preserve_log_on_failure
            exit 1
        fi
        ;;

    # ── Strategy 3: Account activation (Personal/free) ──────────────────────
    account)
        log_info "Activating via UNITY_EMAIL + UNITY_PASSWORD (account strategy)"
        log_info "This is the primary method for Unity Personal/free licenses"

        if "${UNITY_EDITOR}" \
                -batchmode \
                -nographics \
                -username "${UNITY_EMAIL}" \
                -password "${UNITY_PASSWORD}" \
                -logFile "${UNITY_LOG_FILE}" \
                -quit 2>&1; then
            log_info "License activation succeeded (account)"
            exit 0
        else
            unity_exit=$?
            FAILURE_CLASS=$(classify_activation_failure "${UNITY_LOG_FILE}" "${unity_exit}")
            log_error "License activation failed (account): ${FAILURE_CLASS}"
            log_error "Unity exit code: ${unity_exit}"

            case "${FAILURE_CLASS}" in
                MFA_OR_2FA_REQUIRED)
                    log_error "BLOCKED: Unity account requires MFA/2FA which cannot be provided in CI."
                    log_error "Options: disable 2FA on the CI account, use UNITY_LICENSE (.ulf), or use a preactivated self-hosted runner."
                    ;;
                PERSONAL_LICENSE_ONLINE_ACTIVATION_UNSUPPORTED)
                    log_error "BLOCKED: Unity Personal/free online activation is not supported in this Unity version."
                    log_error "Options: use UNITY_LICENSE (.ulf from Unity Hub), or use a preactivated self-hosted runner."
                    ;;
                AUTH_FAILED)
                    log_error "BLOCKED: Authentication failed. Check UNITY_EMAIL and UNITY_PASSWORD secrets."
                    ;;
                *)
                    log_error "BLOCKED: Unity account activation failed with: ${FAILURE_CLASS}"
                    ;;
            esac

            preserve_log_on_failure
            exit 1
        fi
        ;;

    # ── Strategy 4: Preactivated runner ─────────────────────────────────────
    preactivated)
        log_info "Unity is already activated on this runner — skipping activation"
        exit 0
        ;;

    # ── Strategy 5: No activation (explicit) ────────────────────────────────
    none)
        log_info "Activation explicitly disabled (strategy: none)"
        log_info "Unity may run with a limited personal license or fail if activation is required"
        exit 0
        ;;

    # ── Blocked ─────────────────────────────────────────────────────────────
    blocked)
        log_error "BLOCKED: No valid Unity activation strategy available"
        log_error ""
        log_error "Setup options for Unity Personal/free:"
        log_error "  1. Set UNITY_EMAIL + UNITY_PASSWORD secrets (account activation)"
        log_error "  2. Set UNITY_LICENSE secret with .ulf content (manual license)"
        log_error "     Get .ulf: Unity Hub → Preferences → Licenses → Add"
        log_error "     Windows: C:\\ProgramData\\Unity\\Unity_lic.ulf"
        log_error "     macOS:   /Library/Application Support/Unity/Unity_lic.ulf"
        log_error "     Linux:   ~/.local/share/unity3d/Unity/Unity_lic.ulf"
        log_error "  3. Use a preactivated self-hosted runner"
        log_error ""
        log_error "Setup options for Unity Pro/Plus/Enterprise:"
        log_error "  Set UNITY_SERIAL + UNITY_EMAIL + UNITY_PASSWORD secrets"
        log_error ""
        log_error "See: https://game.ci/docs/github/activation"
        exit 1
        ;;

    *)
        log_error "Unknown activation strategy: ${STRATEGY}"
        exit 1
        ;;
esac
