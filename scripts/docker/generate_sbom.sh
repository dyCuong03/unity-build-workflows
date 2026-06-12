#!/usr/bin/env bash
# generate_sbom.sh
# Generate a Software Bill of Materials (SBOM) for a Unity Docker image.
#
# Uses `syft` to produce an SPDX or CycloneDX SBOM document.
# Falls back to `docker sbom` (Docker Desktop built-in) if syft is not installed.
#
# Usage:
#   bash scripts/docker/generate_sbom.sh <image-reference> [format] [output-dir]
#
# Arguments:
#   image-reference   Full Docker image reference (required)
#   format            Output format: spdx-json | cyclonedx-json | table (default: spdx-json)
#   output-dir        Directory to write the SBOM file (default: ./sbom-reports)
#
# Examples:
#   bash scripts/docker/generate_sbom.sh ghcr.io/myorg/unity-build:2022.3.21f1-android
#   bash scripts/docker/generate_sbom.sh ghcr.io/myorg/unity-build:2022.3.21f1-android cyclonedx-json ./reports
#
# Exit codes:
#   0  SBOM generated successfully
#   1  Error — see output for details

set -euo pipefail

# ── Arguments ──────────────────────────────────────────────────────────────
IMAGE_REF="${1:-}"
FORMAT="${2:-spdx-json}"
OUTPUT_DIR="${3:-./sbom-reports}"

# ── Validation ─────────────────────────────────────────────────────────────
if [[ -z "${IMAGE_REF}" ]]; then
  echo "ERROR: image reference is required." >&2
  echo "Usage: $0 <image-reference> [format] [output-dir]" >&2
  exit 1
fi

case "${FORMAT}" in
  spdx-json|cyclonedx-json|table)
    ;;
  *)
    echo "ERROR: unsupported format '${FORMAT}'. Use: spdx-json | cyclonedx-json | table" >&2
    exit 1
    ;;
esac

# ── Output path ────────────────────────────────────────────────────────────
mkdir -p "${OUTPUT_DIR}"

# Sanitize image ref for use as filename
SAFE_REF=$(echo "${IMAGE_REF}" | tr '/:@' '---')
TIMESTAMP=$(date -u +"%Y%m%dT%H%M%SZ")
OUTPUT_FILE="${OUTPUT_DIR}/sbom-${SAFE_REF}-${TIMESTAMP}.${FORMAT//-json/.json}"

echo "[generate_sbom] Image     : ${IMAGE_REF}"
echo "[generate_sbom] Format    : ${FORMAT}"
echo "[generate_sbom] Output    : ${OUTPUT_FILE}"

# ── SBOM generation ────────────────────────────────────────────────────────

if command -v syft &>/dev/null; then
  echo "[generate_sbom] Using syft …"

  # Map our format names to syft output format names
  case "${FORMAT}" in
    spdx-json)     SYFT_FORMAT="spdx-json" ;;
    cyclonedx-json) SYFT_FORMAT="cyclonedx-json" ;;
    table)          SYFT_FORMAT="table" ;;
  esac

  syft "${IMAGE_REF}" \
    --output "${SYFT_FORMAT}=${OUTPUT_FILE}" \
    --quiet

elif command -v docker &>/dev/null && docker sbom --help &>/dev/null 2>&1; then
  echo "[generate_sbom] syft not found — falling back to docker sbom …"
  echo "WARNING: docker sbom produces SPDX format only; format argument ignored." >&2

  docker sbom "${IMAGE_REF}" \
    --format spdx \
    --output "${OUTPUT_FILE}"

elif command -v grype &>/dev/null; then
  echo "WARNING: syft not found. grype can scan but not generate a full SBOM." >&2
  echo "Install syft: https://github.com/anchore/syft#installation" >&2
  exit 1

else
  echo "ERROR: No SBOM tool found. Install syft:" >&2
  echo "  curl -sSfL https://raw.githubusercontent.com/anchore/syft/main/install.sh | sh -s -- -b /usr/local/bin" >&2
  exit 1
fi

echo "[generate_sbom] SBOM written to: ${OUTPUT_FILE}"

# ── Metadata summary ───────────────────────────────────────────────────────
if [[ "${FORMAT}" == "spdx-json" || "${FORMAT}" == "cyclonedx-json" ]] && command -v jq &>/dev/null; then
  PACKAGE_COUNT=$(jq 'if .packages then (.packages | length)
                      elif .components then (.components | length)
                      else 0 end' "${OUTPUT_FILE}" 2>/dev/null || echo "unknown")
  echo "[generate_sbom] Packages catalogued: ${PACKAGE_COUNT}"
fi

echo "[generate_sbom] Done."
