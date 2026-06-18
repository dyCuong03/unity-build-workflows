#!/usr/bin/env bash
# create_keychain.sh
# Creates an isolated temporary keychain for iOS code signing.
# Outputs KEYCHAIN_PATH, KEYCHAIN_NAME, KEYCHAIN_PASSWORD to GITHUB_ENV and GITHUB_OUTPUT.
# Usage: create_keychain.sh
set -euo pipefail

KEYCHAIN_NAME="${KEYCHAIN_NAME:-build-signing-${GITHUB_RUN_NUMBER:-0}-$$}"
KEYCHAIN_PATH="${RUNNER_TEMP:-/tmp}/${KEYCHAIN_NAME}.keychain-db"

# Generate random password — never echoed
KEYCHAIN_PASSWORD=$(LC_ALL=C tr -dc 'A-Za-z0-9!@#%^&*' < /dev/urandom | head -c 32 || true)
# head exits 141 (SIGPIPE) when enough chars are read — that's OK; re-read if empty
if [[ -z "${KEYCHAIN_PASSWORD}" ]]; then
  KEYCHAIN_PASSWORD=$(LC_ALL=C cat /dev/urandom | tr -dc 'A-Za-z0-9' | fold -w 32 | head -n 1)
fi

# Mask the password in GitHub Actions logs
[[ -n "${GITHUB_ACTIONS:-}" ]] && echo "::add-mask::${KEYCHAIN_PASSWORD}"

echo "[create_keychain] Creating isolated keychain: ${KEYCHAIN_PATH}"

# Create the keychain
security create-keychain -p "${KEYCHAIN_PASSWORD}" "${KEYCHAIN_PATH}"

# Restrictive permissions
chmod 600 "${KEYCHAIN_PATH}"

# Disable auto-lock for duration of build (6 h = 21600 s)
security set-keychain-settings -lut 21600 "${KEYCHAIN_PATH}"

# Add to user search list (prepend so it is found first by codesign)
CURRENT_LIST=$(security list-keychain -d user 2>/dev/null | tr -d '"' | tr '\n' ' ' || true)
# shellcheck disable=SC2086
security list-keychain -d user -s "${KEYCHAIN_PATH}" ${CURRENT_LIST}

echo "[create_keychain] Keychain created and added to search list"

# Export to GITHUB_ENV for subsequent steps
if [[ -n "${GITHUB_ENV:-}" ]]; then
  printf 'KEYCHAIN_PATH=%s\n'     "${KEYCHAIN_PATH}"     >> "${GITHUB_ENV}"
  printf 'KEYCHAIN_NAME=%s\n'     "${KEYCHAIN_NAME}"     >> "${GITHUB_ENV}"
  printf 'KEYCHAIN_PASSWORD=%s\n' "${KEYCHAIN_PASSWORD}" >> "${GITHUB_ENV}"
fi

# Export to GITHUB_OUTPUT
if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
  printf 'keychain-path=%s\n' "${KEYCHAIN_PATH}"  >> "${GITHUB_OUTPUT}"
  printf 'keychain-name=%s\n' "${KEYCHAIN_NAME}"  >> "${GITHUB_OUTPUT}"
fi
