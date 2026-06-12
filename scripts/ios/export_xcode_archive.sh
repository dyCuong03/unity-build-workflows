#!/usr/bin/env bash
# export_xcode_archive.sh
# Build and archive an Xcode project, then export to IPA.
# Usage: export_xcode_archive.sh <xcode-project-dir> <output-dir> <environment>
set -euo pipefail

XCODE_DIR="${1:?Usage: export_xcode_archive.sh <xcode-project-dir> <output-dir> <environment>}"
OUTPUT_DIR="${2:?Missing output directory}"
ENVIRONMENT="${3:-production}"
EXPORT_OPTIONS_PLIST="${EXPORT_OPTIONS_PLIST:-/tmp/ExportOptions.plist}"
TEAM_ID="${APPLE_TEAM_ID:-}"

echo "[export_xcode] Xcode project dir: $XCODE_DIR"
echo "[export_xcode] Output dir: $OUTPUT_DIR"
echo "[export_xcode] Environment: $ENVIRONMENT"

mkdir -p "$OUTPUT_DIR"
ARCHIVE_PATH="/tmp/unity-ios-build.xcarchive"

# Find the .xcodeproj or .xcworkspace
WORKSPACE=$(find "$XCODE_DIR" -name "*.xcworkspace" -maxdepth 2 | head -1 || true)
PROJECT=$(find "$XCODE_DIR" -name "*.xcodeproj" -maxdepth 2 | head -1 || true)

if [[ -n "$WORKSPACE" ]]; then
  echo "[export_xcode] Using workspace: $WORKSPACE"
  BUILD_FLAGS=(-workspace "$WORKSPACE" -scheme Unity-iPhone)
elif [[ -n "$PROJECT" ]]; then
  echo "[export_xcode] Using project: $PROJECT"
  BUILD_FLAGS=(-project "$PROJECT" -scheme Unity-iPhone)
else
  echo "ERROR: No .xcworkspace or .xcodeproj found in $XCODE_DIR" >&2
  exit 1
fi

# Determine configuration
XCCONFIG="Release"
if [[ "$ENVIRONMENT" == "development" ]]; then
  XCCONFIG="Debug"
fi

# Archive
echo "[export_xcode] Archiving (configuration: $XCCONFIG)..."
xcodebuild \
  "${BUILD_FLAGS[@]}" \
  -configuration "$XCCONFIG" \
  -destination "generic/platform=iOS" \
  -archivePath "$ARCHIVE_PATH" \
  ${TEAM_ID:+-allowProvisioningUpdates} \
  ${TEAM_ID:+DEVELOPMENT_TEAM="$TEAM_ID"} \
  clean archive \
  CODE_SIGN_STYLE=Manual \
  | xcpretty 2>/dev/null || true

if [[ ! -d "$ARCHIVE_PATH" ]]; then
  echo "ERROR: Archive not created at $ARCHIVE_PATH" >&2
  exit 1
fi
echo "[export_xcode] Archive created: $ARCHIVE_PATH"

# Export IPA
echo "[export_xcode] Exporting IPA..."
if [[ ! -f "$EXPORT_OPTIONS_PLIST" ]]; then
  echo "WARNING: ExportOptions.plist not found — creating minimal fallback" >&2
  cat > /tmp/ExportOptions.plist << 'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>method</key>
    <string>development</string>
</dict>
</plist>
PLIST
  EXPORT_OPTIONS_PLIST="/tmp/ExportOptions.plist"
fi

xcodebuild \
  -exportArchive \
  -archivePath "$ARCHIVE_PATH" \
  -exportOptionsPlist "$EXPORT_OPTIONS_PLIST" \
  -exportPath "$OUTPUT_DIR" \
  | xcpretty 2>/dev/null || true

# Verify IPA was created
IPA_FILE=$(find "$OUTPUT_DIR" -name "*.ipa" | head -1 || true)
if [[ -z "$IPA_FILE" ]]; then
  echo "ERROR: No .ipa file found in $OUTPUT_DIR after export" >&2
  exit 1
fi

echo "[export_xcode] IPA exported: $IPA_FILE"
IPA_SIZE=$(du -sh "$IPA_FILE" | cut -f1)
echo "[export_xcode] IPA size: $IPA_SIZE"
