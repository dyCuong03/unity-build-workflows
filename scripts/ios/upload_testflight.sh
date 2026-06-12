#!/usr/bin/env bash
# upload_testflight.sh
# Upload an IPA to TestFlight using altool or notarytool.
# Usage: upload_testflight.sh <ipa-dir> <app-id>
set -euo pipefail

IPA_DIR="${1:?Usage: upload_testflight.sh <ipa-dir> <app-id>}"
APP_APPLE_ID="${2:?Missing App Apple ID}"

APPLE_TEAM_ID="${APPLE_TEAM_ID:-}"
APP_SPECIFIC_PASSWORD="${TESTFLIGHT_APP_SPECIFIC_PASSWORD:?TESTFLIGHT_APP_SPECIFIC_PASSWORD is required}"
APPLE_ID="${APPLE_ID:-}"

# Mask the app-specific password in logs
echo "::add-mask::${APP_SPECIFIC_PASSWORD}"

echo "[upload_testflight] IPA directory: $IPA_DIR"
echo "[upload_testflight] App Apple ID: $APP_APPLE_ID"

# Find IPA
IPA_FILE=$(find "$IPA_DIR" -name "*.ipa" | head -1 || true)
if [[ -z "$IPA_FILE" ]]; then
  echo "ERROR: No .ipa found in $IPA_DIR" >&2
  exit 1
fi
echo "[upload_testflight] Uploading: $IPA_FILE"

# Try xcrun altool (Xcode 13+)
if xcrun altool --version &>/dev/null; then
  echo "[upload_testflight] Using xcrun altool"
  xcrun altool \
    --upload-app \
    --type ios \
    --file "$IPA_FILE" \
    --apiKey "$APP_APPLE_ID" \
    --apiIssuer "${APPLE_TEAM_ID:-}" \
    --verbose 2>&1 | grep -v "password" || true

  # Fallback: username/password auth
  if [[ "${PIPESTATUS[0]}" -ne 0 && -n "$APPLE_ID" ]]; then
    echo "[upload_testflight] Retrying with Apple ID + app-specific password"
    xcrun altool \
      --upload-app \
      --type ios \
      --file "$IPA_FILE" \
      --username "$APPLE_ID" \
      --password "$APP_SPECIFIC_PASSWORD" \
      --verbose
  fi
else
  # Fallback: use Transporter CLI if available
  if command -v xcrun &>/dev/null && xcrun --find Transporter &>/dev/null 2>&1; then
    echo "[upload_testflight] Using Transporter CLI"
    xcrun Transporter \
      -m upload \
      -f "$IPA_FILE" \
      -u "$APPLE_ID" \
      -p "$APP_SPECIFIC_PASSWORD"
  else
    echo "ERROR: Neither altool nor Transporter found. Install Xcode or Transporter." >&2
    exit 1
  fi
fi

echo "[upload_testflight] Upload to TestFlight complete"
