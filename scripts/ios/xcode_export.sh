#!/usr/bin/env bash
# xcode_export.sh
# Runs xcodebuild -exportArchive to produce an .ipa from a .xcarchive.
# Required env vars:
#   ARCHIVE_PATH         — path to .xcarchive (from xcode_archive.sh)
#   EXPORT_OPTIONS_PATH  — path to ExportOptions.plist (from generate_export_options.sh)
# Optional env vars:
#   EXPORT_PATH          — output directory (default: Builds/iOS/Export)
#   LOG_PATH             — log file path (default: Logs/iOS/xcode-export.log)
set -euo pipefail

ARCHIVE_PATH="${ARCHIVE_PATH:-Builds/iOS/Archive/Game.xcarchive}"
EXPORT_OPTIONS_PATH="${EXPORT_OPTIONS_PATH:?EXPORT_OPTIONS_PATH is required}"
EXPORT_PATH="${EXPORT_PATH:-Builds/iOS/Export}"
LOG_PATH="${LOG_PATH:-Logs/iOS/xcode-export.log}"

mkdir -p "${EXPORT_PATH}"
mkdir -p "$(dirname "${LOG_PATH}")"

if [[ ! -d "${ARCHIVE_PATH}" ]]; then
  echo "::error::Archive not found: ${ARCHIVE_PATH}" >&2
  exit 1
fi
if [[ ! -f "${EXPORT_OPTIONS_PATH}" ]]; then
  echo "::error::ExportOptions.plist not found: ${EXPORT_OPTIONS_PATH}" >&2
  exit 1
fi

echo "[xcode_export] Archive:        ${ARCHIVE_PATH}"
echo "[xcode_export] Export options: ${EXPORT_OPTIONS_PATH}"
echo "[xcode_export] Export path:    ${EXPORT_PATH}"

set +e
xcodebuild \
  -exportArchive \
  -archivePath "${ARCHIVE_PATH}" \
  -exportOptionsPlist "${EXPORT_OPTIONS_PATH}" \
  -exportPath "${EXPORT_PATH}" \
  -allowProvisioningUpdates 2>&1 | tee "${LOG_PATH}"
EXPORT_EXIT=${PIPESTATUS[0]}
set -e

if [[ "${EXPORT_EXIT}" -ne 0 ]]; then
  echo "::error::xcodebuild exportArchive failed (exit ${EXPORT_EXIT}). See: ${LOG_PATH}" >&2
  exit "${EXPORT_EXIT}"
fi

# Locate IPA and rename to canonical name
IPA_PATH=$(find "${EXPORT_PATH}" -maxdepth 1 -name "*.ipa" | head -1 || true)
if [[ -z "${IPA_PATH}" ]]; then
  echo "::error::No .ipa found in export directory: ${EXPORT_PATH}" >&2
  exit 1
fi

CANONICAL_IPA="${EXPORT_PATH}/Game.ipa"
if [[ "${IPA_PATH}" != "${CANONICAL_IPA}" ]]; then
  mv "${IPA_PATH}" "${CANONICAL_IPA}"
  IPA_PATH="${CANONICAL_IPA}"
  echo "[xcode_export] Renamed to: ${CANONICAL_IPA}"
fi

echo "[xcode_export] IPA exported: ${IPA_PATH}"

if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
  printf 'ipa-path=%s\n'       "${IPA_PATH}"   >> "${GITHUB_OUTPUT}"
  printf 'export-path=%s\n'    "${EXPORT_PATH}" >> "${GITHUB_OUTPUT}"
  printf 'export-log-path=%s\n' "${LOG_PATH}"   >> "${GITHUB_OUTPUT}"
fi
