#!/usr/bin/env bash
# scan_image.sh
# Scan a Docker image for known vulnerabilities using trivy or grype.
#
# Exits non-zero if vulnerabilities at or above the severity threshold are found.
# Writes a JSON report to the output directory.
#
# Usage:
#   bash scripts/docker/scan_image.sh <image-reference> [severity-threshold] [output-dir]
#
# Arguments:
#   image-reference    Full Docker image reference (required)
#   severity-threshold Minimum severity to fail on: CRITICAL | HIGH | MEDIUM | LOW
#                      (default: HIGH — fails on CRITICAL or HIGH)
#   output-dir         Directory to write the scan report (default: ./scan-reports)
#
# Examples:
#   bash scripts/docker/scan_image.sh ghcr.io/myorg/unity-build:2022.3.21f1-android
#   bash scripts/docker/scan_image.sh ghcr.io/myorg/unity-build:2022.3.21f1-android CRITICAL
#   bash scripts/docker/scan_image.sh ghcr.io/myorg/unity-build:2022.3.21f1-android HIGH ./reports
#
# Exit codes:
#   0   No vulnerabilities at or above threshold found
#   1   Setup or scan error
#   5   Vulnerabilities at or above threshold found (actionable — fix or accept)

set -euo pipefail

# ── Arguments ──────────────────────────────────────────────────────────────
IMAGE_REF="${1:-}"
SEVERITY_THRESHOLD="${2:-HIGH}"
OUTPUT_DIR="${3:-./scan-reports}"

# ── Validation ─────────────────────────────────────────────────────────────
if [[ -z "${IMAGE_REF}" ]]; then
  echo "ERROR: image reference is required." >&2
  echo "Usage: $0 <image-reference> [severity-threshold] [output-dir]" >&2
  exit 1
fi

case "${SEVERITY_THRESHOLD}" in
  CRITICAL|HIGH|MEDIUM|LOW)
    ;;
  *)
    echo "ERROR: invalid severity threshold '${SEVERITY_THRESHOLD}'. Use: CRITICAL | HIGH | MEDIUM | LOW" >&2
    exit 1
    ;;
esac

# ── Output path ────────────────────────────────────────────────────────────
mkdir -p "${OUTPUT_DIR}"

SAFE_REF=$(echo "${IMAGE_REF}" | tr '/:@' '---')
TIMESTAMP=$(date -u +"%Y%m%dT%H%M%SZ")
REPORT_FILE="${OUTPUT_DIR}/vuln-${SAFE_REF}-${TIMESTAMP}.json"

echo "[scan_image] Image     : ${IMAGE_REF}"
echo "[scan_image] Threshold : ${SEVERITY_THRESHOLD} and above"
echo "[scan_image] Report    : ${REPORT_FILE}"

# ── Scan ───────────────────────────────────────────────────────────────────
VULN_FOUND=0

if command -v trivy &>/dev/null; then
  echo "[scan_image] Using trivy …"

  # Build the severity filter: trivy accepts comma-separated list of
  # severities to flag. We include everything >= threshold.
  case "${SEVERITY_THRESHOLD}" in
    CRITICAL) TRIVY_SEVERITIES="CRITICAL" ;;
    HIGH)     TRIVY_SEVERITIES="CRITICAL,HIGH" ;;
    MEDIUM)   TRIVY_SEVERITIES="CRITICAL,HIGH,MEDIUM" ;;
    LOW)      TRIVY_SEVERITIES="CRITICAL,HIGH,MEDIUM,LOW" ;;
  esac

  # Run trivy; capture exit code without triggering set -e
  trivy image \
    --severity "${TRIVY_SEVERITIES}" \
    --format json \
    --output "${REPORT_FILE}" \
    --exit-code 5 \
    "${IMAGE_REF}" || VULN_FOUND=$?

  # Also print a human-readable table to stdout
  trivy image \
    --severity "${TRIVY_SEVERITIES}" \
    --format table \
    "${IMAGE_REF}" || true

elif command -v grype &>/dev/null; then
  echo "[scan_image] trivy not found — using grype …"

  # grype severity filter
  case "${SEVERITY_THRESHOLD}" in
    CRITICAL) GRYPE_FAIL_ON="critical" ;;
    HIGH)     GRYPE_FAIL_ON="high" ;;
    MEDIUM)   GRYPE_FAIL_ON="medium" ;;
    LOW)      GRYPE_FAIL_ON="low" ;;
  esac

  grype "${IMAGE_REF}" \
    --fail-on "${GRYPE_FAIL_ON}" \
    --output json \
    --file "${REPORT_FILE}" || VULN_FOUND=$?

  # Human-readable table
  grype "${IMAGE_REF}" \
    --fail-on "${GRYPE_FAIL_ON}" \
    --output table || true

else
  echo "ERROR: No vulnerability scanner found." >&2
  echo "Install trivy: https://aquasecurity.github.io/trivy/latest/getting-started/installation/" >&2
  echo "Install grype: https://github.com/anchore/grype#installation" >&2
  exit 1
fi

# ── Result summary ─────────────────────────────────────────────────────────
if [[ "${VULN_FOUND}" -eq 5 || "${VULN_FOUND}" -eq 1 ]]; then
  echo "" >&2
  echo "============================================================" >&2
  echo "  VULNERABILITY SCAN FAILED" >&2
  echo "  Image   : ${IMAGE_REF}" >&2
  echo "  Threshold: ${SEVERITY_THRESHOLD}" >&2
  echo "  Report  : ${REPORT_FILE}" >&2
  echo "============================================================" >&2
  echo "" >&2
  echo "Action required:" >&2
  echo "  1. Review the report: ${REPORT_FILE}" >&2
  echo "  2. Update base image or vulnerable packages in the Dockerfile." >&2
  echo "  3. If a finding is a false positive, add it to the trivy/grype ignore file." >&2
  exit 5
fi

if [[ "${VULN_FOUND}" -ne 0 ]]; then
  echo "ERROR: Scanner exited with unexpected code ${VULN_FOUND}." >&2
  exit 1
fi

echo "[scan_image] No vulnerabilities at or above ${SEVERITY_THRESHOLD} severity found."
echo "[scan_image] Full report: ${REPORT_FILE}"
echo "[scan_image] Done."
