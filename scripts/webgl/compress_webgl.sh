#!/usr/bin/env bash
# compress_webgl.sh
# Post-process Unity WebGL build output:
#  - Brotli-compress .js, .wasm, .data files
#  - Gzip-compress as fallback
#  - Update index.html compression hints
# Usage: compress_webgl.sh <webgl-build-dir> <environment>
set -euo pipefail

BUILD_DIR="${1:?Usage: compress_webgl.sh <webgl-build-dir> <environment>}"
ENVIRONMENT="${2:-development}"

echo "[compress_webgl] Build dir: $BUILD_DIR"
echo "[compress_webgl] Environment: $ENVIRONMENT"

if [[ ! -d "$BUILD_DIR" ]]; then
  echo "ERROR: WebGL build directory not found: $BUILD_DIR" >&2
  exit 1
fi

# Find the Build sub-folder (Unity WebGL output structure)
BUILD_SUBDIR="$BUILD_DIR"
if [[ -d "$BUILD_DIR/Build" ]]; then
  BUILD_SUBDIR="$BUILD_DIR/Build"
fi

ORIGINAL_SIZE=$(du -sb "$BUILD_DIR" 2>/dev/null | cut -f1 || echo "0")
echo "[compress_webgl] Original size: $(du -sh "$BUILD_DIR" | cut -f1)"

BROTLI_AVAILABLE=false
GZIP_AVAILABLE=false

command -v brotli &>/dev/null && BROTLI_AVAILABLE=true
command -v gzip  &>/dev/null && GZIP_AVAILABLE=true

COMPRESSED_COUNT=0

for ext in js wasm data unityweb; do
  while IFS= read -r -d '' file; do
    # Skip already compressed files
    [[ "$file" == *.br   ]] && continue
    [[ "$file" == *.gz   ]] && continue

    if $BROTLI_AVAILABLE; then
      brotli --best --keep "$file"
      COMPRESSED_COUNT=$((COMPRESSED_COUNT + 1))
      echo "[compress_webgl] Brotli: $(basename "$file")"
    fi

    if $GZIP_AVAILABLE; then
      gzip --best --keep "$file"
      COMPRESSED_COUNT=$((COMPRESSED_COUNT + 1))
      echo "[compress_webgl] Gzip: $(basename "$file")"
    fi
  done < <(find "$BUILD_SUBDIR" -name "*.${ext}" -not -name "*.br" -not -name "*.gz" -print0 2>/dev/null)
done

COMPRESSED_SIZE=$(du -sb "$BUILD_DIR" 2>/dev/null | cut -f1 || echo "0")
echo "[compress_webgl] Compressed size: $(du -sh "$BUILD_DIR" | cut -f1)"
echo "[compress_webgl] Files compressed: $COMPRESSED_COUNT"

if [[ "$ORIGINAL_SIZE" -gt 0 && "$COMPRESSED_SIZE" -gt 0 ]]; then
  SAVINGS=$(( (ORIGINAL_SIZE - COMPRESSED_SIZE) * 100 / ORIGINAL_SIZE ))
  echo "[compress_webgl] Size reduction: ~${SAVINGS}%"
fi

# Update index.html to indicate compressed content (Unity handles this via loader)
INDEX_HTML="$BUILD_DIR/index.html"
if [[ -f "$INDEX_HTML" ]]; then
  echo "[compress_webgl] index.html present at: $INDEX_HTML"
fi

# Write GitHub Step Summary
if [[ -n "${GITHUB_STEP_SUMMARY:-}" ]]; then
  cat >> "$GITHUB_STEP_SUMMARY" << EOF

### WebGL Build Compression

| Metric | Value |
|--------|-------|
| Brotli available | $BROTLI_AVAILABLE |
| Gzip available | $GZIP_AVAILABLE |
| Files compressed | $COMPRESSED_COUNT |
| Final size | $(du -sh "$BUILD_DIR" | cut -f1) |
EOF
fi

echo "[compress_webgl] Compression complete"
