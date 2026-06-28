#!/usr/bin/env bash
# =============================================================================
# resolve_activation_strategy.sh — Unity license activation strategy resolver
#
# Detects available secrets and selects the best activation strategy.
#
# Strategy priority (auto mode):
#   1. manual-ulf    — UNITY_LICENSE contains a valid .ulf file
#   2. serial        — UNITY_SERIAL + UNITY_EMAIL + UNITY_PASSWORD
#   3. account       — UNITY_EMAIL + UNITY_PASSWORD (no serial)
#   4. preactivated  — Unity already activated on this machine
#   5. blocked       — No valid strategy available
#
# Environment variables read (never printed):
#   UNITY_LICENSE    — .ulf file content (raw XML or base64)
#   UNITY_SERIAL     — Pro/Plus/Enterprise serial key
#   UNITY_EMAIL      — Unity account email
#   UNITY_PASSWORD   — Unity account password
#
# Optional env:
#   UNITY_ACTIVATION_STRATEGY — Force a specific strategy (default: auto)
#   UNITY_EDITOR              — Path to Unity editor binary
#
# Outputs (written to GITHUB_OUTPUT if available, else stdout):
#   activation-strategy       — Selected strategy name
#   unity-license-present     — true/false
#   unity-license-valid-ulf   — yes/no/unchecked
#   unity-serial-present      — true/false
#   unity-email-present       — true/false
#   unity-password-present    — true/false
#   activation-blocked-reason — Reason if blocked (empty otherwise)
#
# Exit codes:
#   0 — Strategy resolved successfully (check activation-strategy output)
#   1 — Script error (not a licensing issue)
#
# Security:
#   - NEVER prints secret values
#   - Only prints presence (present/missing) and validity (yes/no)
# =============================================================================
set -Eeuo pipefail

# ---------------------------------------------------------------------------
# Logging — never log secret content
# ---------------------------------------------------------------------------
_log_prefix="resolve-activation-strategy"
log_info()  { echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] [INFO]  ${_log_prefix}: $*" >&2; }
log_warn()  { echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] [WARN]  ${_log_prefix}: $*" >&2; }
log_error() { echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] [ERROR] ${_log_prefix}: $*" >&2; }

# ---------------------------------------------------------------------------
# Output helper — writes to GITHUB_OUTPUT or stdout
# ---------------------------------------------------------------------------
set_output() {
    local key="$1" value="$2"
    if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
        echo "${key}=${value}" >> "${GITHUB_OUTPUT}"
    fi
    # Always print to stderr for log visibility
    log_info "Output: ${key}=${value}"
}

# ---------------------------------------------------------------------------
# Detect secret presence (never read values beyond checking non-empty)
# ---------------------------------------------------------------------------
HAS_LICENSE="false"
HAS_SERIAL="false"
HAS_EMAIL="false"
HAS_PASSWORD="false"

[[ -n "${UNITY_LICENSE:-}" ]]  && HAS_LICENSE="true"
[[ -n "${UNITY_SERIAL:-}" ]]   && HAS_SERIAL="true"
[[ -n "${UNITY_EMAIL:-}" ]]    && HAS_EMAIL="true"
[[ -n "${UNITY_PASSWORD:-}" ]] && HAS_PASSWORD="true"

log_info "Secret detection:"
log_info "  UNITY_LICENSE:  ${HAS_LICENSE}"
log_info "  UNITY_SERIAL:   ${HAS_SERIAL}"
log_info "  UNITY_EMAIL:    ${HAS_EMAIL}"
log_info "  UNITY_PASSWORD: ${HAS_PASSWORD}"

set_output "unity-license-present"  "${HAS_LICENSE}"
set_output "unity-serial-present"   "${HAS_SERIAL}"
set_output "unity-email-present"    "${HAS_EMAIL}"
set_output "unity-password-present" "${HAS_PASSWORD}"

# ---------------------------------------------------------------------------
# Validate UNITY_LICENSE if present
# ---------------------------------------------------------------------------
LICENSE_VALID="unchecked"

validate_unity_license() {
    if [[ "${HAS_LICENSE}" != "true" ]]; then
        LICENSE_VALID="unchecked"
        return
    fi

    log_info "Validating UNITY_LICENSE format..."

    # Decode to temp file
    local temp_ulf
    temp_ulf="$(mktemp /tmp/unity-license-check-XXXXXXXX.ulf)"
    chmod 600 "${temp_ulf}"

    # Try base64 decode first, fall back to raw
    if echo "${UNITY_LICENSE}" | base64 -d > /dev/null 2>&1; then
        echo "${UNITY_LICENSE}" | base64 -d > "${temp_ulf}"
    else
        printf '%s' "${UNITY_LICENSE}" > "${temp_ulf}"
    fi

    # Check non-empty
    if [[ ! -s "${temp_ulf}" ]]; then
        log_warn "UNITY_LICENSE decoded to empty file"
        LICENSE_VALID="no"
        rm -f "${temp_ulf}" 2>/dev/null || true
        return
    fi

    # Reject known invalid formats
    local content_head
    content_head="$(head -c 2048 "${temp_ulf}" 2>/dev/null || true)"

    # Reject Unity entitlement XML (not a .ulf)
    if echo "${content_head}" | grep -qi "UnityEntitlementLicense"; then
        log_warn "UNITY_LICENSE contains UnityEntitlementLicense XML (not a .ulf)"
        LICENSE_VALID="no"
        rm -f "${temp_ulf}" 2>/dev/null || true
        return
    fi

    # Reject generic XML root elements that aren't license files
    if echo "${content_head}" | grep -qE "^<\?xml|^<root>" && \
       ! echo "${content_head}" | grep -qi "license"; then
        log_warn "UNITY_LICENSE contains XML but does not appear to be a license file"
        LICENSE_VALID="no"
        rm -f "${temp_ulf}" 2>/dev/null || true
        return
    fi

    # Accept: non-empty, not entitlement XML
    LICENSE_VALID="yes"
    log_info "UNITY_LICENSE appears to be a valid .ulf candidate"

    rm -f "${temp_ulf}" 2>/dev/null || true
}

validate_unity_license
set_output "unity-license-valid-ulf" "${LICENSE_VALID}"

# ---------------------------------------------------------------------------
# Check for preactivated Unity installation
# ---------------------------------------------------------------------------
check_preactivated() {
    local unity_editor="${UNITY_EDITOR:-}"

    # Try common paths if not set
    if [[ -z "${unity_editor}" ]]; then
        for candidate in \
            "/usr/bin/unity-editor" \
            "/Applications/Unity/Unity.app/Contents/MacOS/Unity" \
            "/opt/unity/Editor/Unity" \
            "C:/Program Files/Unity/Hub/Editor/*/Editor/Unity.exe"; do
            if [[ -x "${candidate}" ]] 2>/dev/null; then
                unity_editor="${candidate}"
                break
            fi
        done
    fi

    if [[ -z "${unity_editor}" || ! -x "${unity_editor}" ]] 2>/dev/null; then
        log_info "No Unity editor found for preactivation check"
        return 1
    fi

    log_info "Checking if Unity is already activated on this runner..."

    # Try a lightweight batchmode command — if it exits 0 without license error,
    # Unity is activated
    local check_log
    check_log="$(mktemp /tmp/unity-activation-check-XXXXXXXX.log)"

    if "${unity_editor}" \
        -batchmode \
        -nographics \
        -quit \
        -logFile "${check_log}" 2>/dev/null; then
        log_info "Unity appears to be already activated on this runner"
        rm -f "${check_log}" 2>/dev/null || true
        return 0
    fi

    # Check log for specific license error
    if grep -qi "No valid Unity license found\|Activation.*Error\|license.*invalid" "${check_log}" 2>/dev/null; then
        log_info "Unity is NOT activated on this runner"
        rm -f "${check_log}" 2>/dev/null || true
        return 1
    fi

    # Unity exited non-zero but maybe not due to licensing
    log_info "Unity exited non-zero — assuming not activated"
    rm -f "${check_log}" 2>/dev/null || true
    return 1
}

# ---------------------------------------------------------------------------
# Strategy resolution
# ---------------------------------------------------------------------------
FORCED_STRATEGY="${UNITY_ACTIVATION_STRATEGY:-auto}"
SELECTED_STRATEGY=""
BLOCKED_REASON=""

resolve_strategy() {
    log_info "Resolving activation strategy (mode: ${FORCED_STRATEGY})"

    # ── Forced strategy ──────────────────────────────────────────────────────
    if [[ "${FORCED_STRATEGY}" != "auto" ]]; then
        case "${FORCED_STRATEGY}" in
            manual-ulf|manual-license)
                if [[ "${HAS_LICENSE}" != "true" ]]; then
                    SELECTED_STRATEGY="blocked"
                    BLOCKED_REASON="Forced strategy 'manual-ulf' but UNITY_LICENSE is not set"
                    return
                fi
                if [[ "${LICENSE_VALID}" == "no" ]]; then
                    SELECTED_STRATEGY="blocked"
                    BLOCKED_REASON="Forced strategy 'manual-ulf' but UNITY_LICENSE is not a valid .ulf"
                    return
                fi
                SELECTED_STRATEGY="manual-ulf"
                ;;
            serial)
                if [[ "${HAS_SERIAL}" != "true" || "${HAS_EMAIL}" != "true" || "${HAS_PASSWORD}" != "true" ]]; then
                    SELECTED_STRATEGY="blocked"
                    BLOCKED_REASON="Forced strategy 'serial' but UNITY_SERIAL/UNITY_EMAIL/UNITY_PASSWORD not all set"
                    return
                fi
                SELECTED_STRATEGY="serial"
                ;;
            account)
                if [[ "${HAS_EMAIL}" != "true" || "${HAS_PASSWORD}" != "true" ]]; then
                    SELECTED_STRATEGY="blocked"
                    BLOCKED_REASON="Forced strategy 'account' but UNITY_EMAIL/UNITY_PASSWORD not set"
                    return
                fi
                SELECTED_STRATEGY="account"
                ;;
            preactivated)
                SELECTED_STRATEGY="preactivated"
                ;;
            none)
                SELECTED_STRATEGY="none"
                log_info "Activation explicitly disabled (strategy: none)"
                ;;
            *)
                SELECTED_STRATEGY="blocked"
                BLOCKED_REASON="Unknown forced strategy: ${FORCED_STRATEGY}"
                ;;
        esac
        return
    fi

    # ── Auto resolution (priority order) ─────────────────────────────────────

    # 1. UNITY_LICENSE with valid .ulf
    if [[ "${HAS_LICENSE}" == "true" && "${LICENSE_VALID}" == "yes" ]]; then
        SELECTED_STRATEGY="manual-ulf"
        log_info "Strategy 1: UNITY_LICENSE is present and valid → manual-ulf"
        return
    fi

    # 1b. UNITY_LICENSE present but invalid — warn and continue
    if [[ "${HAS_LICENSE}" == "true" && "${LICENSE_VALID}" == "no" ]]; then
        log_warn "UNITY_LICENSE is present but invalid format — skipping manual-ulf"
        log_warn "Falling back to next available strategy"
    fi

    # 2. Serial activation (Pro/Plus/Enterprise)
    if [[ "${HAS_SERIAL}" == "true" && "${HAS_EMAIL}" == "true" && "${HAS_PASSWORD}" == "true" ]]; then
        SELECTED_STRATEGY="serial"
        log_info "Strategy 2: UNITY_SERIAL + credentials → serial"
        return
    fi

    # 3. Account activation (Personal/free or any account)
    if [[ "${HAS_EMAIL}" == "true" && "${HAS_PASSWORD}" == "true" ]]; then
        SELECTED_STRATEGY="account"
        log_info "Strategy 3: UNITY_EMAIL + UNITY_PASSWORD → account"
        return
    fi

    # 4. Preactivated runner
    if check_preactivated 2>/dev/null; then
        SELECTED_STRATEGY="preactivated"
        log_info "Strategy 4: Unity already activated → preactivated"
        return
    fi

    # 5. Blocked
    SELECTED_STRATEGY="blocked"
    if [[ "${HAS_LICENSE}" == "true" && "${LICENSE_VALID}" == "no" ]]; then
        BLOCKED_REASON="UNITY_LICENSE is set but invalid (not a .ulf). No other activation secrets available."
    elif [[ "${HAS_EMAIL}" == "true" && "${HAS_PASSWORD}" != "true" ]]; then
        BLOCKED_REASON="UNITY_EMAIL is set but UNITY_PASSWORD is missing"
    elif [[ "${HAS_PASSWORD}" == "true" && "${HAS_EMAIL}" != "true" ]]; then
        BLOCKED_REASON="UNITY_PASSWORD is set but UNITY_EMAIL is missing"
    else
        BLOCKED_REASON="No Unity activation secrets found (UNITY_LICENSE, UNITY_SERIAL, UNITY_EMAIL, UNITY_PASSWORD all missing)"
    fi
}

resolve_strategy

set_output "activation-strategy"       "${SELECTED_STRATEGY}"
set_output "activation-blocked-reason" "${BLOCKED_REASON}"

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo "" >&2
log_info "════════════════════════════════════════════════════════════"
log_info "Unity activation strategy resolution:"
log_info "  UNITY_LICENSE:           ${HAS_LICENSE}"
log_info "  UNITY_LICENSE_VALID_ULF: ${LICENSE_VALID}"
log_info "  UNITY_SERIAL:            ${HAS_SERIAL}"
log_info "  UNITY_EMAIL:             ${HAS_EMAIL}"
log_info "  UNITY_PASSWORD:          ${HAS_PASSWORD}"
log_info "  Selected strategy:       ${SELECTED_STRATEGY}"
if [[ -n "${BLOCKED_REASON}" ]]; then
    log_info "  Blocked reason:          ${BLOCKED_REASON}"
fi
log_info "════════════════════════════════════════════════════════════"
echo "" >&2

# Print strategy to stdout (for callers that capture output)
echo "${SELECTED_STRATEGY}"

exit 0
