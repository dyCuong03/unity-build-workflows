#!/usr/bin/env bash
# install_profile.sh
# Installs a base64-encoded provisioning profile into ~/Library/MobileDevice/Provisioning Profiles/.
# Required env vars:
#   IOS_PROVISIONING_PROFILE_BASE64 — base64-encoded .mobileprovision
set -euo pipefail

PROFILE_BASE64="${IOS_PROVISIONING_PROFILE_BASE64:?IOS_PROVISIONING_PROFILE_BASE64 is required}"

PROFILES_DIR="${HOME}/Library/MobileDevice/Provisioning Profiles"
mkdir -p "${PROFILES_DIR}"

TEMP_PROFILE="${RUNNER_TEMP:-/tmp}/profile-$$.mobileprovision"
if ! echo "${PROFILE_BASE64}" | base64 --decode > "${TEMP_PROFILE}" 2>/dev/null; then
  echo "::error::Failed to base64-decode IOS_PROVISIONING_PROFILE_BASE64" >&2
  exit 1
fi
chmod 600 "${TEMP_PROFILE}"

# Extract UUID from the embedded binary plist
PROFILE_UUID=$(security cms -D -i "${TEMP_PROFILE}" 2>/dev/null \
  | python3 -c "import sys, plistlib; d=plistlib.loads(sys.stdin.buffer.read()); print(d['UUID'])" 2>/dev/null || echo "")

if [[ -z "${PROFILE_UUID}" ]]; then
  echo "::error::Failed to extract UUID from provisioning profile — check IOS_PROVISIONING_PROFILE_BASE64" >&2
  rm -f "${TEMP_PROFILE}"
  exit 1
fi

PROFILE_DEST="${PROFILES_DIR}/${PROFILE_UUID}.mobileprovision"
mv "${TEMP_PROFILE}" "${PROFILE_DEST}"
chmod 600 "${PROFILE_DEST}"

echo "[install_profile] Installed profile UUID: ${PROFILE_UUID}"
echo "[install_profile] Location: ${PROFILE_DEST}"

if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
  printf 'profile-uuid=%s\n' "${PROFILE_UUID}" >> "${GITHUB_OUTPUT}"
  printf 'profile-path=%s\n' "${PROFILE_DEST}" >> "${GITHUB_OUTPUT}"
fi
if [[ -n "${GITHUB_ENV:-}" ]]; then
  printf 'PROFILE_UUID=%s\n' "${PROFILE_UUID}" >> "${GITHUB_ENV}"
  printf 'PROFILE_PATH=%s\n' "${PROFILE_DEST}" >> "${GITHUB_ENV}"
fi
