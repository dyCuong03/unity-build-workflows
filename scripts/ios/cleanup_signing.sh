#!/usr/bin/env bash
# cleanup_signing.sh
# Always-run cleanup: removes keychain, provisioning profiles, ASC API key, temp signing files.
# Run with if: always() to ensure execution even on build failure.
# Expected env vars (all optional — cleanup skips gracefully if unset):
#   KEYCHAIN_PATH    — path to the temp keychain
#   KEYCHAIN_NAME    — keychain name (fallback if KEYCHAIN_PATH unavailable)
#   PROFILE_PATH     — path to installed provisioning profile
#   ASC_API_KEY_DIR  — directory holding the ASC API key .p8 file
set -euo pipefail

ERRORS=0

log_warn() { echo "[cleanup_signing] WARNING: $*" >&2; }
log_info() { echo "[cleanup_signing] $*"; }

# ── 1. Keychain ────────────────────────────────────────────────────────────────
if [[ -n "${KEYCHAIN_PATH:-}" && -f "${KEYCHAIN_PATH}" ]]; then
  log_info "Removing keychain: ${KEYCHAIN_PATH}"
  security delete-keychain "${KEYCHAIN_PATH}" 2>/dev/null \
    || log_warn "delete-keychain failed (may already be removed)"
  rm -f "${KEYCHAIN_PATH}" || true
  log_info "Keychain removed"
elif [[ -n "${KEYCHAIN_NAME:-}" ]]; then
  security delete-keychain "${KEYCHAIN_NAME}.keychain-db" 2>/dev/null || true
fi

# ── 2. Provisioning profile ───────────────────────────────────────────────────
if [[ -n "${PROFILE_PATH:-}" && -f "${PROFILE_PATH}" ]]; then
  log_info "Removing provisioning profile: ${PROFILE_PATH}"
  rm -f "${PROFILE_PATH}" || { log_warn "Failed to remove profile"; ERRORS=$((ERRORS+1)); }
  log_info "Profile removed"
fi

# ── 3. ASC API key directory ─────────────────────────────────────────────────
if [[ -n "${ASC_API_KEY_DIR:-}" && -d "${ASC_API_KEY_DIR}" ]]; then
  log_info "Removing ASC API key directory: ${ASC_API_KEY_DIR}"
  rm -rf "${ASC_API_KEY_DIR}" \
    || { log_warn "Failed to remove ASC API key dir"; ERRORS=$((ERRORS+1)); }
  log_info "ASC API key directory removed"
fi

# ── 4. Stray temp files ───────────────────────────────────────────────────────
RUNNER_TEMP="${RUNNER_TEMP:-/tmp}"
for pattern in \
  "${RUNNER_TEMP}/distribution-cert-*.p12" \
  "${RUNNER_TEMP}/profile-*.mobileprovision" \
  "${RUNNER_TEMP}/ExportOptions-*.plist" \
  "${RUNNER_TEMP}/asc-key-*.p8" \
  "${RUNNER_TEMP}/asc-keys-*"
do
  # Use find to safely expand; glob may not match
  while IFS= read -r -d '' f; do
    log_info "Removing stray temp: ${f}"
    rm -rf "${f}" || true
  done < <(find "${RUNNER_TEMP}" -maxdepth 2 -name "$(basename "${pattern}")" -print0 2>/dev/null || true)
done

if [[ "${ERRORS}" -gt 0 ]]; then
  log_warn "${ERRORS} cleanup error(s) — verify secrets were not left on runner"
  exit 1
fi

log_info "Cleanup complete"
