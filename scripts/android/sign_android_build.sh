#!/usr/bin/env bash
# sign_android_build.sh
# Sign an Android APK or AAB using jarsigner / apksigner.
# Usage: sign_android_build.sh <build-dir> <environment>
set -euo pipefail

BUILD_DIR="${1:?Usage: sign_android_build.sh <build-dir> <environment>}"
ENVIRONMENT="${2:-production}"
KEYSTORE_PATH="${KEYSTORE_PATH:-/tmp/android-keystore.jks}"

echo "[sign_android] Signing Android build in: $BUILD_DIR"
echo "[sign_android] Environment: $ENVIRONMENT"

# Mask secrets in logs
if [[ -n "${ANDROID_KEYSTORE_PASS:-}" ]]; then
  echo "::add-mask::${ANDROID_KEYSTORE_PASS}"
fi
if [[ -n "${ANDROID_KEY_PASS:-}" ]]; then
  echo "::add-mask::${ANDROID_KEY_PASS}"
fi

if [[ ! -f "$KEYSTORE_PATH" ]]; then
  echo "ERROR: Keystore not found at $KEYSTORE_PATH" >&2
  exit 1
fi

KEY_ALIAS="${ANDROID_KEY_ALIAS:?ANDROID_KEY_ALIAS is required}"
KEYSTORE_PASS="${ANDROID_KEYSTORE_PASS:?ANDROID_KEYSTORE_PASS is required}"
KEY_PASS="${ANDROID_KEY_PASS:?ANDROID_KEY_PASS is required}"

# Find build outputs
AAB_FILES=$(find "$BUILD_DIR" -name "*.aab" 2>/dev/null || true)
APK_FILES=$(find "$BUILD_DIR" -name "*.apk" -not -name "*-aligned.apk" 2>/dev/null || true)

if [[ -z "$AAB_FILES" && -z "$APK_FILES" ]]; then
  echo "ERROR: No .aab or .apk files found in $BUILD_DIR" >&2
  exit 1
fi

# Sign AAB files with jarsigner
if [[ -n "$AAB_FILES" ]]; then
  while IFS= read -r aab; do
    echo "[sign_android] Signing AAB: $aab"
    jarsigner \
      -verbose \
      -sigalg SHA256withRSA \
      -digestalg SHA-256 \
      -keystore "$KEYSTORE_PATH" \
      -storepass "$KEYSTORE_PASS" \
      -keypass "$KEY_PASS" \
      "$aab" \
      "$KEY_ALIAS"
    echo "[sign_android] AAB signed: $aab"
  done <<< "$AAB_FILES"
fi

# Sign APK files with apksigner (if available) or jarsigner
if [[ -n "$APK_FILES" ]]; then
  while IFS= read -r apk; do
    echo "[sign_android] Signing APK: $apk"
    ALIGNED_APK="${apk%.apk}-aligned.apk"

    # Align first
    if command -v zipalign &>/dev/null; then
      zipalign -v 4 "$apk" "$ALIGNED_APK"
      rm -f "$apk"
    else
      echo "[sign_android] WARNING: zipalign not found — skipping alignment" >&2
      ALIGNED_APK="$apk"
    fi

    # Sign
    if command -v apksigner &>/dev/null; then
      apksigner sign \
        --ks "$KEYSTORE_PATH" \
        --ks-pass "pass:$KEYSTORE_PASS" \
        --key-pass "pass:$KEY_PASS" \
        --ks-key-alias "$KEY_ALIAS" \
        --out "${apk%.apk}-signed.apk" \
        "$ALIGNED_APK"
      rm -f "$ALIGNED_APK"
      echo "[sign_android] APK signed with apksigner"
    else
      jarsigner \
        -verbose \
        -sigalg SHA256withRSA \
        -digestalg SHA-256 \
        -keystore "$KEYSTORE_PATH" \
        -storepass "$KEYSTORE_PASS" \
        -keypass "$KEY_PASS" \
        "$ALIGNED_APK" \
        "$KEY_ALIAS"
      echo "[sign_android] APK signed with jarsigner"
    fi
  done <<< "$APK_FILES"
fi

echo "[sign_android] Signing complete"
