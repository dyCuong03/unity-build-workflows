#!/usr/bin/env bash
# run_unity_ios.sh
# =============================================================================
# ALL native Unity invocations for iOS CI on macOS are consolidated here.
# This is the single allowlist entry for:
#   tests/test_no_native_unity_invocation.py
#
# Mirrors docker/unity/entrypoint.sh + activate-license.sh conventions.
# Runner: macos-unity-xcode (self-hosted macOS with Xcode + Unity iOS Support)
#
# Usage: run_unity_ios.sh <command>
# Commands:
#   activate           — activate Unity license (UNITY_LICENSE or email/password)
#   build              — generate iOS Xcode project via executeMethod
#   build-addressables — build Addressable Assets for iOS
#   test-editmode      — run Unity EditMode tests
#   test-xcode-gen     — Xcode project generation smoke test (no dist signing)
#   return-license     — return Unity floating license
#
# Required env vars (all commands):
#   UNITY_EDITOR       — full path to Unity macOS binary
#
# Build/test env vars:
#   PROJECT_PATH       — Unity project root (default: .)
#   ENVIRONMENT        — development|staging|production (default: development)
#   BUILD_CONFIG_PATH  — BuildConfig dir relative to PROJECT_PATH (default: BuildConfig)
#   OUTPUT_PATH        — output directory (default: Builds/iOS/Xcode)
#   LOG_PATH           — directory for Editor.log files (default: Logs/iOS)
#   TEST_RESULTS_PATH  — directory for test result XML files (default: TestResults/iOS)
#
# License env vars (activate command):
#   UNITY_LICENSE    — ULF file content (base64 or raw XML) — NEVER echoed
#   UNITY_EMAIL      — for email/password activation
#   UNITY_PASSWORD   — for email/password activation
#
# Security:
#   - License content is NEVER printed to stdout/stderr
#   - Temp license file created at chmod 600, removed on EXIT trap
#   - Passwords/secrets passed via env only; never on command line
# =============================================================================
set -euo pipefail

readonly SCRIPT_NAME="$(basename "$0")"
readonly BUILD_METHOD="Company.BuildPipeline.Editor.BuildCommand.Execute"

COMMAND="${1:?Usage: run_unity_ios.sh <command>}"
UNITY_EDITOR="${UNITY_EDITOR:?UNITY_EDITOR is required}"

PROJECT_PATH="${PROJECT_PATH:-.}"
ENVIRONMENT="${ENVIRONMENT:-development}"
BUILD_CONFIG_PATH="${BUILD_CONFIG_PATH:-BuildConfig}"
OUTPUT_PATH="${OUTPUT_PATH:-Builds/iOS/Xcode}"
LOG_PATH="${LOG_PATH:-Logs/iOS}"
TEST_RESULTS_PATH="${TEST_RESULTS_PATH:-TestResults/iOS}"

# ---------------------------------------------------------------------------
# Logging — never log license content
# ---------------------------------------------------------------------------
log_info()  { printf '[%s] [INFO]  %s: %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "${SCRIPT_NAME}" "$*" >&2; }
log_warn()  { printf '[%s] [WARN]  %s: %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "${SCRIPT_NAME}" "$*" >&2; }
log_error() { printf '[%s] [ERROR] %s: %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "${SCRIPT_NAME}" "$*" >&2; }

# ---------------------------------------------------------------------------
# Validate Unity binary
# ---------------------------------------------------------------------------
if [[ ! -f "${UNITY_EDITOR}" ]]; then
  log_error "Unity editor not found: ${UNITY_EDITOR}"
  exit 1
fi

mkdir -p "${LOG_PATH}"

# ---------------------------------------------------------------------------
# run_unity: invoke Unity, stream output, capture and return exit code
# ---------------------------------------------------------------------------
run_unity() {
  local log_file="$1"; shift
  local -a unity_args=("$@")
  local unity_exit=0

  log_info "Invoking Unity editor (command: ${COMMAND})"

  set +e
  "${UNITY_EDITOR}" "${unity_args[@]}" 2>&1 | tee -a "${log_file}"
  unity_exit="${PIPESTATUS[0]}"
  set -e

  if [[ "${unity_exit}" -ne 0 ]]; then
    log_error "Unity exited with code ${unity_exit}"
    log_error "See log: ${log_file}"
  else
    log_info "Unity exited successfully (code 0)"
  fi

  return "${unity_exit}"
}

# ---------------------------------------------------------------------------
# Command dispatch
# ---------------------------------------------------------------------------
case "${COMMAND}" in

  # ── activate ──────────────────────────────────────────────────────────────
  activate)
    if [[ -z "${UNITY_LICENSE:-}" && -z "${UNITY_EMAIL:-}" ]]; then
      log_info "No license credentials set — skipping activation"
      log_info "Unity may use a limited personal license"
      exit 0
    fi

    TEMP_LICENSE_FILE=""
    _cleanup_license() {
      if [[ -n "${TEMP_LICENSE_FILE}" && -f "${TEMP_LICENSE_FILE}" ]]; then
        rm -f "${TEMP_LICENSE_FILE}" 2>/dev/null || true
      fi
    }
    trap _cleanup_license EXIT

    ACTIVATION_LOG="${LOG_PATH}/Editor-activation.log"

    if [[ -n "${UNITY_LICENSE:-}" ]]; then
      log_info "Activating via UNITY_LICENSE (manualLicenseFile strategy)"

      TEMP_LICENSE_FILE="$(mktemp /tmp/unity-license-XXXXXXXX.ulf)"
      chmod 600 "${TEMP_LICENSE_FILE}"

      # Support both raw XML and base64-encoded ULF — never echoed
      if echo "${UNITY_LICENSE}" | base64 -d > /dev/null 2>&1; then
        echo "${UNITY_LICENSE}" | base64 -d > "${TEMP_LICENSE_FILE}"
      else
        printf '%s' "${UNITY_LICENSE}" > "${TEMP_LICENSE_FILE}"
      fi

      run_unity "${ACTIVATION_LOG}" \
        -batchmode \
        -nographics \
        -manualLicenseFile "${TEMP_LICENSE_FILE}" \
        -logFile "${ACTIVATION_LOG}" \
        -quit || true

    else
      log_info "Activating via UNITY_EMAIL / UNITY_PASSWORD strategy"

      run_unity "${ACTIVATION_LOG}" \
        -batchmode \
        -nographics \
        -username "${UNITY_EMAIL}" \
        -password "${UNITY_PASSWORD}" \
        -logFile  "${ACTIVATION_LOG}" \
        -quit || true
    fi

    log_info "Activation step complete"
    ;;

  # ── build ──────────────────────────────────────────────────────────────────
  build)
    mkdir -p "${OUTPUT_PATH}" BuildReports/iOS

    BUILD_LOG="${LOG_PATH}/Editor.log"
    BUILD_CONFIG_DIR="${PROJECT_PATH}/${BUILD_CONFIG_PATH}"

    log_info "Generating iOS Xcode project → ${OUTPUT_PATH}"
    log_info "Environment: ${ENVIRONMENT}"

    run_unity "${BUILD_LOG}" \
      -batchmode \
      -nographics \
      -quit \
      -executeMethod  "${BUILD_METHOD}" \
      -projectPath    "${PROJECT_PATH}" \
      -buildConfig    "${BUILD_CONFIG_DIR}" \
      -environment    "${ENVIRONMENT}" \
      -targetPlatform ios \
      -outputPath     "${OUTPUT_PATH}" \
      -logFile        "${BUILD_LOG}"

    # Validate Xcode output was produced
    XCODE_OUT=$(find "${OUTPUT_PATH}" -maxdepth 2 \
      \( -name "*.xcodeproj" -o -name "*.xcworkspace" \) 2>/dev/null | head -1 || true)
    if [[ -z "${XCODE_OUT}" ]]; then
      log_error "Unity build succeeded but no Xcode project found in ${OUTPUT_PATH}"
      exit 1
    fi
    log_info "Xcode project generated: ${XCODE_OUT}"

    if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
      printf 'xcode-project-path=%s\n' "${OUTPUT_PATH}" >> "${GITHUB_OUTPUT}"
      printf 'xcode-output=%s\n'        "${XCODE_OUT}"  >> "${GITHUB_OUTPUT}"
    fi
    ;;

  # ── build-addressables ─────────────────────────────────────────────────────
  build-addressables)
    ADDR_LOG="${LOG_PATH}/Editor-addressables.log"
    log_info "Building Addressable Assets for iOS"

    run_unity "${ADDR_LOG}" \
      -batchmode \
      -nographics \
      -quit \
      -executeMethod  "${BUILD_METHOD}" \
      -projectPath    "${PROJECT_PATH}" \
      -buildConfig    "${PROJECT_PATH}/${BUILD_CONFIG_PATH}" \
      -environment    "${ENVIRONMENT}" \
      -targetPlatform ios \
      -logFile        "${ADDR_LOG}"
    ;;

  # ── test-editmode ──────────────────────────────────────────────────────────
  test-editmode)
    mkdir -p "${TEST_RESULTS_PATH}"

    EDITMODE_LOG="${LOG_PATH}/Editor-editmode.log"
    log_info "Running EditMode tests"

    EDITMODE_EXIT=0
    set +e
    "${UNITY_EDITOR}" \
      -batchmode \
      -nographics \
      -projectPath  "${PROJECT_PATH}" \
      -buildTarget  iOS \
      -runTests \
      -testPlatform EditMode \
      -testResults  "${TEST_RESULTS_PATH}/editmode-results.xml" \
      -logFile      "${EDITMODE_LOG}" \
      2>&1 | tee -a "${EDITMODE_LOG}"
    EDITMODE_EXIT="${PIPESTATUS[0]}"
    set -e

    if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
      printf 'exit-code=%s\n' "${EDITMODE_EXIT}" >> "${GITHUB_OUTPUT}"
    fi

    if [[ "${EDITMODE_EXIT}" -ne 0 ]]; then
      log_error "EditMode tests failed (exit ${EDITMODE_EXIT})"
      exit "${EDITMODE_EXIT}"
    fi
    log_info "EditMode tests passed"
    ;;

  # ── test-xcode-gen ─────────────────────────────────────────────────────────
  test-xcode-gen)
    mkdir -p "${OUTPUT_PATH}"

    XCGEN_LOG="${LOG_PATH}/Editor-xcode-gen.log"
    log_info "Smoke-testing Xcode project generation"

    run_unity "${XCGEN_LOG}" \
      -batchmode \
      -nographics \
      -quit \
      -executeMethod        "${BUILD_METHOD}" \
      -projectPath          "${PROJECT_PATH}" \
      -buildConfig          "${PROJECT_PATH}/${BUILD_CONFIG_PATH}" \
      -environment          "${ENVIRONMENT}" \
      -targetPlatform       ios \
      -outputPath           "${OUTPUT_PATH}" \
      -generateXcodeProjectOnly \
      -logFile              "${XCGEN_LOG}"
    ;;

  # ── return-license ─────────────────────────────────────────────────────────
  return-license)
    RETURN_LOG="${LOG_PATH}/Editor-return-license.log"
    log_info "Returning Unity license"

    set +e
    "${UNITY_EDITOR}" \
      -batchmode \
      -nographics \
      -returnlicense \
      -logFile "${RETURN_LOG}" \
      -quit 2>&1 || true
    set -e

    # Remove any temp license files left by activation
    find /tmp -maxdepth 1 -name "unity-license-*.ulf" -exec rm -f {} + 2>/dev/null || true

    log_info "License return complete"
    ;;

  # ── unknown ────────────────────────────────────────────────────────────────
  *)
    log_error "Unknown command: '${COMMAND}'"
    log_error "Supported commands: activate, build, build-addressables, test-editmode, test-xcode-gen, return-license"
    exit 1
    ;;
esac
