#!/usr/bin/env bash
# deploy_cloudflare_pages.sh
# Deploy Unity WebGL build to Cloudflare Pages using Wrangler.
# Usage: deploy_cloudflare_pages.sh <webgl-build-dir> <environment> <version>
set -euo pipefail

WEBGL_DIR="${1:?Usage: deploy_cloudflare_pages.sh <webgl-build-dir> <environment> <version>}"
ENVIRONMENT="${2:-staging}"
VERSION="${3:-0.0.0}"

CLOUDFLARE_API_TOKEN="${CLOUDFLARE_API_TOKEN:?CLOUDFLARE_API_TOKEN is required}"
CLOUDFLARE_ACCOUNT_ID="${CLOUDFLARE_ACCOUNT_ID:?CLOUDFLARE_ACCOUNT_ID is required}"
PROJECT_NAME="${CLOUDFLARE_PAGES_PROJECT:-unity-webgl-build}"

# Mask token in logs
echo "::add-mask::${CLOUDFLARE_API_TOKEN}"

echo "[deploy_cloudflare] WebGL dir: $WEBGL_DIR"
echo "[deploy_cloudflare] Environment: $ENVIRONMENT"
echo "[deploy_cloudflare] Version: $VERSION"
echo "[deploy_cloudflare] Project: $PROJECT_NAME"

if [[ ! -d "$WEBGL_DIR" ]]; then
  echo "ERROR: WebGL directory not found: $WEBGL_DIR" >&2
  exit 1
fi

# Verify wrangler is available
if ! command -v wrangler &>/dev/null; then
  echo "[deploy_cloudflare] wrangler not found — installing via npm"
  npm install -g wrangler@latest 2>/dev/null
fi

if ! command -v wrangler &>/dev/null; then
  echo "ERROR: wrangler could not be installed" >&2
  exit 1
fi

# Determine branch name from environment
case "$ENVIRONMENT" in
  production)  CF_BRANCH="main" ;;
  staging)     CF_BRANCH="staging" ;;
  *)           CF_BRANCH="dev-${GITHUB_RUN_NUMBER:-0}" ;;
esac

echo "[deploy_cloudflare] Deploying to branch: $CF_BRANCH"

DEPLOY_OUTPUT=$(wrangler pages deploy "$WEBGL_DIR" \
  --project-name "$PROJECT_NAME" \
  --branch "$CF_BRANCH" \
  --commit-message "Deploy v${VERSION} (${ENVIRONMENT}) [run #${GITHUB_RUN_NUMBER:-0}]" \
  2>&1) || {
  echo "ERROR: Wrangler deploy failed:" >&2
  echo "$DEPLOY_OUTPUT" >&2
  exit 1
}

echo "$DEPLOY_OUTPUT"

# Extract deployment URL from output
DEPLOY_URL=$(echo "$DEPLOY_OUTPUT" | grep -oP 'https://[^\s]+\.pages\.dev[^\s]*' | head -1 || true)

if [[ -n "$DEPLOY_URL" ]]; then
  echo "[deploy_cloudflare] Deployed to: $DEPLOY_URL"

  # Set GitHub output
  if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
    echo "url=$DEPLOY_URL" >> "$GITHUB_OUTPUT"
  fi
else
  echo "[deploy_cloudflare] WARNING: Could not extract deployment URL from output"
fi

# Write summary
if [[ -n "${GITHUB_STEP_SUMMARY:-}" ]]; then
  cat >> "$GITHUB_STEP_SUMMARY" << EOF

### Cloudflare Pages Deploy

| Field | Value |
|-------|-------|
| Project | \`$PROJECT_NAME\` |
| Branch | \`$CF_BRANCH\` |
| Version | \`$VERSION\` |
| URL | ${DEPLOY_URL:-N/A} |
EOF
fi

echo "[deploy_cloudflare] Deployment complete"
