#!/usr/bin/env bash
# generate_export_options.sh
# Generates ExportOptions.plist for xcodebuild -exportArchive.
# No secrets are embedded in the plist.
# Required env vars:
#   EXPORT_METHOD       — app-store | ad-hoc | enterprise | development
#   BUNDLE_IDENTIFIER   — com.company.game
#   DEVELOPMENT_TEAM    — Apple Team ID (10 alphanumeric chars)
# Optional env vars:
#   PROFILE_UUID        — UUID of installed provisioning profile
#   EXPORT_OPTIONS_PATH — output path (default: $RUNNER_TEMP/ExportOptions-$$.plist)
set -euo pipefail

EXPORT_METHOD="${EXPORT_METHOD:?EXPORT_METHOD is required}"
BUNDLE_IDENTIFIER="${BUNDLE_IDENTIFIER:?BUNDLE_IDENTIFIER is required}"
DEVELOPMENT_TEAM="${DEVELOPMENT_TEAM:?DEVELOPMENT_TEAM is required}"
PROFILE_UUID="${PROFILE_UUID:-}"
EXPORT_OPTIONS_PATH="${EXPORT_OPTIONS_PATH:-${RUNNER_TEMP:-/tmp}/ExportOptions-$$.plist}"

echo "[generate_export_options] Method:      ${EXPORT_METHOD}"
echo "[generate_export_options] Bundle ID:   ${BUNDLE_IDENTIFIER}"
echo "[generate_export_options] Team:        ${DEVELOPMENT_TEAM}"
echo "[generate_export_options] Profile UUID: ${PROFILE_UUID:-<auto>}"

# Build optional provisioningProfiles block
PROVISIONING_BLOCK=""
if [[ -n "${PROFILE_UUID}" ]]; then
  PROVISIONING_BLOCK="
	<key>provisioningProfiles</key>
	<dict>
		<key>${BUNDLE_IDENTIFIER}</key>
		<string>${PROFILE_UUID}</string>
	</dict>"
fi

cat > "${EXPORT_OPTIONS_PATH}" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>method</key>
	<string>${EXPORT_METHOD}</string>
	<key>teamID</key>
	<string>${DEVELOPMENT_TEAM}</string>
	<key>signingStyle</key>
	<string>manual</string>
	<key>stripSwiftSymbols</key>
	<true/>
	<key>uploadBitcode</key>
	<false/>
	<key>uploadSymbols</key>
	<true/>${PROVISIONING_BLOCK}
</dict>
</plist>
EOF

chmod 644 "${EXPORT_OPTIONS_PATH}"

echo "[generate_export_options] Written to: ${EXPORT_OPTIONS_PATH}"

if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
  printf 'export-options-path=%s\n' "${EXPORT_OPTIONS_PATH}" >> "${GITHUB_OUTPUT}"
fi
if [[ -n "${GITHUB_ENV:-}" ]]; then
  printf 'EXPORT_OPTIONS_PATH=%s\n' "${EXPORT_OPTIONS_PATH}" >> "${GITHUB_ENV}"
fi
