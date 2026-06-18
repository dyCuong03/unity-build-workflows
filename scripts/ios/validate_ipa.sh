#!/usr/bin/env bash
# validate_ipa.sh
# Validates an .ipa file structure, codesign, and Info.plist.
# Usage: validate_ipa.sh <ipa-path>  OR  set IPA_PATH env var
set -euo pipefail

IPA_PATH="${1:-${IPA_PATH:-}}"
: "${IPA_PATH:?Usage: validate_ipa.sh <ipa-path>}"

if [[ ! -f "${IPA_PATH}" ]]; then
  echo "::error::IPA not found: ${IPA_PATH}" >&2
  exit 1
fi

echo "[validate_ipa] Validating: ${IPA_PATH}"

# Must be a valid ZIP
if ! unzip -t "${IPA_PATH}" > /dev/null 2>&1; then
  echo "::error::IPA is not a valid zip archive" >&2
  exit 1
fi

INSPECT_DIR="${RUNNER_TEMP:-/tmp}/ipa-inspect-$$"
mkdir -p "${INSPECT_DIR}"
# shellcheck disable=SC2064
trap "rm -rf '${INSPECT_DIR}'" EXIT

unzip -q "${IPA_PATH}" -d "${INSPECT_DIR}"

APP_PATH=$(find "${INSPECT_DIR}/Payload" -maxdepth 1 -name "*.app" 2>/dev/null | head -1 || true)
if [[ -z "${APP_PATH}" ]]; then
  echo "::error::No .app bundle found inside IPA Payload/" >&2
  exit 1
fi

echo "[validate_ipa] App bundle: $(basename "${APP_PATH}")"

# Verify code signature
if ! codesign --verify --verbose=2 "${APP_PATH}" 2>&1; then
  echo "::error::codesign verification failed for: ${APP_PATH}" >&2
  exit 1
fi

# Check Info.plist
INFO_PLIST="${APP_PATH}/Info.plist"
if [[ ! -f "${INFO_PLIST}" ]]; then
  echo "::error::Info.plist not found in .app bundle" >&2
  exit 1
fi

BUNDLE_ID=$(defaults read "${INFO_PLIST}" CFBundleIdentifier 2>/dev/null || echo "unknown")
BUNDLE_VERSION=$(defaults read "${INFO_PLIST}" CFBundleShortVersionString 2>/dev/null || echo "unknown")
BUILD_NUMBER=$(defaults read "${INFO_PLIST}" CFBundleVersion 2>/dev/null || echo "unknown")

echo "[validate_ipa] Bundle ID:       ${BUNDLE_ID}"
echo "[validate_ipa] Version:         ${BUNDLE_VERSION}"
echo "[validate_ipa] Build number:    ${BUILD_NUMBER}"
echo "[validate_ipa] Validation passed"

if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
  printf 'bundle-id=%s\n'       "${BUNDLE_ID}"       >> "${GITHUB_OUTPUT}"
  printf 'bundle-version=%s\n'  "${BUNDLE_VERSION}"  >> "${GITHUB_OUTPUT}"
  printf 'build-number=%s\n'    "${BUILD_NUMBER}"     >> "${GITHUB_OUTPUT}"
fi
