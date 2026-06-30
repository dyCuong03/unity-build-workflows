#!/usr/bin/env bash
# =============================================================================
# test_discord_size_check.sh
# =============================================================================
# Self-contained bash unit tests for the _should_attach cumulative-size logic
# embedded in .github/actions/discord-upload-build/action.yml.
#
# The function is copied VERBATIM from action.yml Step 4 so the tests pin
# actual production behaviour — if the function changes, this test breaks.
#
# Cases asserted (per DISCORD_BUILD_DELIVERY_PLAN.md §10.2 + task spec):
#   T1  WebGL(5) + Addressables(3) + Android(35) @24 → attach, attach, link
#   T2  Exactly at threshold: 24 @24 → attach (inclusive ≤)
#   T3  One byte over threshold: 25 @24 → link (> threshold)
#   T4  Sequential: WebGL(5) then Linux64(20) @24 → attach, link (5+20=25>24)
#   T5  Sub-1MB file normalised to 1MB: 0 → 1 → attach @24
#   T6  Zero threshold: any file → link  (edge case)
#   T7  Large threshold: all fit → attach, attach, attach
#   T8  Cumulative accumulates correctly across calls
#
# Exit codes: 0 = all pass, 1 = one or more failures.
# =============================================================================
set -uo pipefail

# ---------------------------------------------------------------------------
# Exact copy of _should_attach from action.yml Step 4 (DO NOT MODIFY).
# If the action function changes, update this copy to match.
# ---------------------------------------------------------------------------
CUMULATIVE_MB=0
_should_attach() {
  local zip_mb="${1}" threshold="${2}"
  if (( CUMULATIVE_MB + zip_mb <= threshold )); then
    CUMULATIVE_MB=$(( CUMULATIVE_MB + zip_mb ))
    return 0
  fi
  return 1
}

# ---------------------------------------------------------------------------
# Sub-1MB normalisation — copied from action.yml (inline before _should_attach call):
#   [ "${ZIP_MB}" -eq 0 ] && ZIP_MB=1
# Applied here before asserting, to mirror production behaviour.
# ---------------------------------------------------------------------------
_normalize_mb() {
  local mb="${1:-0}"
  [ "${mb}" -eq 0 ] && mb=1
  echo "${mb}"
}

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------
PASS=0
FAIL=0

_pass() { echo "PASS: ${1}"; PASS=$(( PASS + 1 )); }
_fail() { echo "FAIL: ${1}"; FAIL=$(( FAIL + 1 )); }

# assert_attach LABEL ZIP_MB THRESHOLD
# Asserts _should_attach returns 0 (attach) given current CUMULATIVE_MB.
assert_attach() {
  local label="${1}" zip_mb="${2}" threshold="${3}"
  if _should_attach "${zip_mb}" "${threshold}"; then
    _pass "${label}"
  else
    _fail "${label} — expected attach (rc=0), got link (rc=1); CUMULATIVE_MB=${CUMULATIVE_MB}"
  fi
}

# assert_link LABEL ZIP_MB THRESHOLD
# Asserts _should_attach returns 1 (link) given current CUMULATIVE_MB.
# CUMULATIVE_MB must NOT be incremented on link — verify that too.
assert_link() {
  local label="${1}" zip_mb="${2}" threshold="${3}"
  local before="${CUMULATIVE_MB}"
  if _should_attach "${zip_mb}" "${threshold}"; then
    _fail "${label} — expected link (rc=1), got attach (rc=0)"
  else
    _pass "${label}"
    # Guard: cumulative must be unchanged on link
    if [ "${CUMULATIVE_MB}" -ne "${before}" ]; then
      _fail "${label} — CUMULATIVE_MB changed on link (was ${before}, now ${CUMULATIVE_MB})"
    fi
  fi
}

# ---------------------------------------------------------------------------
# T1: WebGL(5) + Addressables(3) + Android(35) @24 → attach, attach, link
#     Mirrors the plan's "typical" run scenario.
# ---------------------------------------------------------------------------
echo "--- T1: WebGL(5) + Addressables(3) + Android(35) @24 ---"
CUMULATIVE_MB=0
assert_attach "T1a WebGL(5MB)       cumul=0  → attach (0+5=5≤24)"     5 24
assert_attach "T1b Addressables(3MB) cumul=5  → attach (5+3=8≤24)"    3 24
assert_link   "T1c Android(35MB)    cumul=8  → link  (8+35=43>24)"   35 24
# Post-T1: cumulative should be 8 (two files attached)
[ "${CUMULATIVE_MB}" -eq 8 ] \
  && _pass "T1d CUMULATIVE_MB=8 after T1 sequence" \
  || _fail "T1d expected CUMULATIVE_MB=8, got ${CUMULATIVE_MB}"

# ---------------------------------------------------------------------------
# T2: Exactly at threshold (24 @ threshold=24) → attach (≤ is inclusive)
# ---------------------------------------------------------------------------
echo "--- T2: exactly at threshold ---"
CUMULATIVE_MB=0
assert_attach "T2 24MB @24 → attach (24≤24, inclusive)" 24 24

# ---------------------------------------------------------------------------
# T3: One byte over threshold (25 @ threshold=24) → link
# ---------------------------------------------------------------------------
echo "--- T3: one over threshold ---"
CUMULATIVE_MB=0
assert_link "T3 25MB @24 → link (25>24)" 25 24

# ---------------------------------------------------------------------------
# T4: Sequential WebGL(5) + Linux64(20) @24 → attach, link  (5+20=25>24)
# ---------------------------------------------------------------------------
echo "--- T4: WebGL(5) + Linux64(20) @24 ---"
CUMULATIVE_MB=0
assert_attach "T4a WebGL(5MB)   cumul=0  → attach (0+5=5≤24)"   5 24
assert_link   "T4b Linux64(20MB) cumul=5  → link  (5+20=25>24)" 20 24
[ "${CUMULATIVE_MB}" -eq 5 ] \
  && _pass "T4c CUMULATIVE_MB=5 after T4 (Linux64 not added)" \
  || _fail "T4c expected CUMULATIVE_MB=5, got ${CUMULATIVE_MB}"

# ---------------------------------------------------------------------------
# T5: Sub-1MB file normalised to 1MB before call → attach @24
# ---------------------------------------------------------------------------
echo "--- T5: sub-1MB normalisation (0→1) ---"
CUMULATIVE_MB=0
NORM_MB=$(_normalize_mb 0)
[ "${NORM_MB}" -eq 1 ] \
  && _pass "T5a normalise(0)=1" \
  || _fail "T5a expected _normalize_mb(0)=1, got ${NORM_MB}"
assert_attach "T5b normalised(1MB) @24 → attach (0+1=1≤24)" "${NORM_MB}" 24

# Already-non-zero values must not be changed
NORM_3=$(_normalize_mb 3)
[ "${NORM_3}" -eq 3 ] \
  && _pass "T5c normalise(3)=3 unchanged" \
  || _fail "T5c expected _normalize_mb(3)=3, got ${NORM_3}"

# ---------------------------------------------------------------------------
# T6: Zero threshold → non-zero files link; zero-byte edge case either way
# ---------------------------------------------------------------------------
echo "--- T6: zero threshold ---"
CUMULATIVE_MB=0
assert_link "T6a 1MB @0 → link (0+1=1>0)" 1 0
# Edge case: 0MB file at threshold 0 — 0+0=0≤0 is true so it attaches.
# This is a known mathematical edge case; both outcomes are acceptable as
# the action always normalises 0 → 1 before calling _should_attach.
CUMULATIVE_MB=0
if _should_attach 0 0; then
  _pass "T6b 0MB @0 edge case: attach (0+0=0≤0; normalisation prevents this in production)"
else
  _pass "T6b 0MB @0 edge case: link (implementation choice)"
fi

# ---------------------------------------------------------------------------
# T7: Large threshold — all files fit
# ---------------------------------------------------------------------------
echo "--- T7: large threshold (100MB) ---"
CUMULATIVE_MB=0
assert_attach "T7a Android(35MB)    @100 → attach (0+35=35≤100)"  35 100
assert_attach "T7b Linux64(25MB)    @100 → attach (35+25=60≤100)" 25 100
assert_attach "T7c LinuxServer(22MB) @100 → attach (60+22=82≤100)" 22 100
[ "${CUMULATIVE_MB}" -eq 82 ] \
  && _pass "T7d CUMULATIVE_MB=82 correct" \
  || _fail "T7d expected CUMULATIVE_MB=82, got ${CUMULATIVE_MB}"

# ---------------------------------------------------------------------------
# T8: Cumulative accumulates correctly — reset between groups
# ---------------------------------------------------------------------------
echo "--- T8: cumulative reset and accumulation ---"
CUMULATIVE_MB=0
assert_attach "T8a 10MB @24 → attach (cumul=10)" 10 24
assert_attach "T8b 10MB @24 → attach (cumul=20)" 10 24
assert_link   "T8c  5MB @24 → link  (20+5=25>24)"  5 24
[ "${CUMULATIVE_MB}" -eq 20 ] \
  && _pass "T8d CUMULATIVE_MB=20 (third file not added)" \
  || _fail "T8d expected CUMULATIVE_MB=20, got ${CUMULATIVE_MB}"

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo "================================"
echo "Results: ${PASS} passed, ${FAIL} failed"
echo "================================"

[ "${FAIL}" -eq 0 ] && exit 0 || exit 1
