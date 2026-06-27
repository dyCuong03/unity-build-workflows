#!/usr/bin/env bash
# release_metadata.sh
# Generates SHA-256 checksums and build metadata JSON for iOS release artifacts.
# Required env vars:
#   BUILD_VERSION — version string
# Optional:
#   IPA_PATH      — path to the exported .ipa (default: Builds/iOS/Export/Unity.ipa)
#   ARCHIVE_PATH  — path to .xcarchive (default: Builds/iOS/Archive/Unity.xcarchive)
#   ENVIRONMENT   — build environment (default: production)
#   REPORT_PATH   — directory for reports (default: BuildReports/iOS)
set -euo pipefail

IPA_PATH="${IPA_PATH:-Builds/iOS/Export/Unity.ipa}"
ARCHIVE_PATH="${ARCHIVE_PATH:-Builds/iOS/Archive/Unity.xcarchive}"
ENVIRONMENT="${ENVIRONMENT:-production}"
BUILD_VERSION="${BUILD_VERSION:?BUILD_VERSION is required}"
REPORT_PATH="${REPORT_PATH:-BuildReports/iOS}"
COMMIT_SHA="${GITHUB_SHA:-unknown}"
RUN_NUMBER="${GITHUB_RUN_NUMBER:-0}"
RUNNER_NAME_VAL="${RUNNER_NAME:-unknown}"

mkdir -p "${REPORT_PATH}"

echo "[release_metadata] Generating checksums and metadata for v${BUILD_VERSION}..."

IPA_CHECKSUM=""
IPA_SIZE_BYTES=0
if [[ -f "${IPA_PATH}" ]]; then
  IPA_CHECKSUM=$(shasum -a 256 "${IPA_PATH}" | awk '{print $1}')
  IPA_SIZE_BYTES=$(stat -f%z "${IPA_PATH}" 2>/dev/null || stat -c%s "${IPA_PATH}" 2>/dev/null || echo "0")
  # Write standalone checksum file — filename derived from IPA basename (standard format: <hash>  <filename>)
  IPA_BASENAME="$(basename "${IPA_PATH}")"
  printf '%s  %s\n' "${IPA_CHECKSUM}" "${IPA_BASENAME}" > "${REPORT_PATH}/${IPA_BASENAME}.sha256"
  echo "[release_metadata] IPA SHA-256: ${IPA_CHECKSUM} (${IPA_SIZE_BYTES} bytes)"
else
  echo "[release_metadata] WARNING: IPA not found at ${IPA_PATH}" >&2
fi

DSYM_CHECKSUM=""
if [[ -d "${ARCHIVE_PATH}" ]]; then
  DSYM_PATH=$(find "${ARCHIVE_PATH}" -name "*.dSYM" -maxdepth 5 2>/dev/null | head -1 || true)
  if [[ -d "${DSYM_PATH}" ]]; then
    DSYM_CHECKSUM=$(find "${DSYM_PATH}" -type f -exec shasum -a 256 {} \; 2>/dev/null | sort | shasum -a 256 | awk '{print $1}')
    echo "[release_metadata] dSYM tree SHA-256: ${DSYM_CHECKSUM}"
  fi
fi

python3 - << PYEOF
import json
data = {
    "version": "${BUILD_VERSION}",
    "environment": "${ENVIRONMENT}",
    "build_number": "${RUN_NUMBER}",
    "commit": "${COMMIT_SHA}",
    "runner": "${RUNNER_NAME_VAL}",
    "platform": "iOS",
    "artifacts": {
        "ipa": {
            "path": "${IPA_PATH}",
            "sha256": "${IPA_CHECKSUM}",
            "size_bytes": int("${IPA_SIZE_BYTES}" or "0")
        },
        "xcarchive": {
            "path": "${ARCHIVE_PATH}",
            "dsym_sha256": "${DSYM_CHECKSUM}"
        }
    }
}
with open("${REPORT_PATH}/build-metadata.json", "w") as f:
    json.dump(data, f, indent=2)
print("[release_metadata] Metadata written: ${REPORT_PATH}/build-metadata.json")
PYEOF
