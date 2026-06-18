#!/usr/bin/env bash
# import_certificate.sh
# Imports a base64-encoded Apple distribution certificate (.p12) into the signing keychain.
# Required env vars:
#   IOS_DISTRIBUTION_CERTIFICATE_BASE64   — base64-encoded .p12
#   IOS_DISTRIBUTION_CERTIFICATE_PASSWORD — p12 passphrase
#   KEYCHAIN_PATH                         — from create_keychain.sh
#   KEYCHAIN_PASSWORD                     — from create_keychain.sh
set -euo pipefail

CERT_BASE64="${IOS_DISTRIBUTION_CERTIFICATE_BASE64:?IOS_DISTRIBUTION_CERTIFICATE_BASE64 is required}"
CERT_PASSWORD="${IOS_DISTRIBUTION_CERTIFICATE_PASSWORD:?IOS_DISTRIBUTION_CERTIFICATE_PASSWORD is required}"
KEYCHAIN_PATH="${KEYCHAIN_PATH:?KEYCHAIN_PATH is required (run create_keychain.sh first)}"
KEYCHAIN_PASSWORD="${KEYCHAIN_PASSWORD:?KEYCHAIN_PASSWORD is required (run create_keychain.sh first)}"

# Mask secrets
echo "::add-mask::${CERT_PASSWORD}"
echo "::add-mask::${KEYCHAIN_PASSWORD}"

CERT_PATH="${RUNNER_TEMP:-/tmp}/distribution-cert-$$.p12"

echo "[import_certificate] Decoding and importing certificate..."

# Decode — must succeed or we have a bad secret
if ! echo "${CERT_BASE64}" | base64 --decode > "${CERT_PATH}" 2>/dev/null; then
  echo "::error::Failed to base64-decode IOS_DISTRIBUTION_CERTIFICATE_BASE64" >&2
  exit 1
fi
chmod 600 "${CERT_PATH}"

# Import into the isolated keychain
security import \
  "${CERT_PATH}" \
  -k "${KEYCHAIN_PATH}" \
  -P "${CERT_PASSWORD}" \
  -A \
  -T /usr/bin/codesign \
  -T /usr/bin/security

# Allow codesign to use the key without interactive prompts
security set-key-partition-list \
  -S apple-tool:,apple: \
  -s \
  -k "${KEYCHAIN_PASSWORD}" \
  "${KEYCHAIN_PATH}"

# Remove temp cert immediately
rm -f "${CERT_PATH}"

echo "[import_certificate] Certificate imported and temp file removed"
