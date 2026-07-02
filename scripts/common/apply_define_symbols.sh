#!/usr/bin/env bash
# apply_define_symbols.sh
#
# Append extra Scripting Define Symbols into ProjectSettings/ProjectSettings.asset
# before a Unity build, so per-branch symbols (configured via GitHub Repository
# Variables and resolved by resolve_build_flow.sh) take effect at build time.
#
# Semantics: ADDITIVE. The resolved symbols are merged (deduplicated) into EVERY
# platform group already present under the `scriptingDefineSymbols:` map. Existing
# project symbols (e.g. ODIN_INSPECTOR, DOTWEEN) are preserved — they are needed
# to compile. This is why we append rather than replace.
#
# Lane-agnostic: patches the serialized asset directly, so the docker (game-ci)
# and self-hosted (Windows/macOS) lanes all pick the symbols up identically, and
# the `define-symbols-count` metric (which reads the same field) stays truthful.
#
# Inputs (environment):
#   DEFINE_SYMBOLS   Symbols to add. ';' or ',' separated (e.g. "STAGING;PROFILER").
#                    Empty/unset → no-op (exit 0).
#   PROJECT_PATH     Unity project root (default: ".").
#
# All diagnostic output goes to stderr; the asset file is edited in place.
set -euo pipefail

DEFINE_SYMBOLS="${DEFINE_SYMBOLS:-}"
PROJECT_PATH="${PROJECT_PATH:-.}"

log() { echo "[apply_define_symbols] $*" >&2; }

# Normalise separators (commas → semicolons), strip whitespace around each token,
# drop empty tokens, and collapse to a clean ';'-joined string.
# Normalise, then keep ONLY valid define identifiers ([A-Za-z_][A-Za-z0-9_]*).
# This guards against malformed/corrupted variable values (spaces, tabs,
# newlines, punctuation) that would otherwise reach Unity and break compilation.
_raw="$(printf '%s' "${DEFINE_SYMBOLS}" \
  | tr ',' '\n' | tr ';' '\n' \
  | sed 's/^[[:space:]]*//; s/[[:space:]]*$//' \
  | sed '/^$/d')"
_valid="$(printf '%s\n' "${_raw}" | grep -E '^[A-Za-z_][A-Za-z0-9_]*$' || true)"
_dropped="$(printf '%s\n' "${_raw}" | grep -Ev '^[A-Za-z_][A-Za-z0-9_]*$' || true)"
if [ -n "${_dropped}" ]; then
  log "::warning:: Ignoring invalid define symbol token(s) (not a valid identifier): $(printf '%s' "${_dropped}" | paste -sd '|' -)"
fi
SYMS="$(printf '%s\n' "${_valid}" | sed '/^$/d' | paste -sd ';' - )"

if [ -z "${SYMS}" ]; then
  log "No define symbols to apply (DEFINE_SYMBOLS empty); skipping."
  exit 0
fi

PS="${PROJECT_PATH%/}/ProjectSettings/ProjectSettings.asset"
if [ ! -f "${PS}" ]; then
  log "::warning:: ProjectSettings.asset not found at ${PS}; skipping define-symbol injection."
  exit 0
fi

if ! grep -q '^  scriptingDefineSymbols:' "${PS}"; then
  log "::warning:: No 'scriptingDefineSymbols:' block in ${PS}; skipping."
  exit 0
fi

log "Applying define symbols: ${SYMS}"

TMP="$(mktemp)"
awk -v add="${SYMS}" '
  # Merge the extra symbols into an existing ";"-joined value, skipping dups.
  function merge(val,   n,parts,m,A,i,j,found,out,s) {
    n = split(val, parts, ";")
    out = val
    m = split(add, A, ";")
    for (i = 1; i <= m; i++) {
      s = A[i]
      if (s == "") continue
      found = 0
      for (j = 1; j <= n; j++) { if (parts[j] == s) { found = 1; break } }
      if (!found) { out = (out == "") ? s : out ";" s }
    }
    return out
  }
  BEGIN { inblock = 0 }
  {
    line = $0
    sub(/\r$/, "", line)                       # tolerate CRLF

    if (line ~ /^  scriptingDefineSymbols:[[:space:]]*$/) {
      inblock = 1
      print line
      next
    }

    if (inblock == 1) {
      if (line ~ /^    /) {                     # child entry: "    Group: value"
        idx = index(line, ":")
        if (idx > 0) {
          key = substr(line, 1, idx)
          val = substr(line, idx + 1)
          sub(/^[ \t]+/, "", val)
          newval = merge(val)
          if (newval == "") print key
          else print key " " newval
          next
        }
      } else {
        inblock = 0                             # dedent → block ended
      }
    }
    print line
  }
' "${PS}" > "${TMP}"

mv "${TMP}" "${PS}"

log "Done. Groups under scriptingDefineSymbols now include: ${SYMS}"
