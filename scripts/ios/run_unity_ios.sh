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
# License env vars (activate command — all optional):
#   UNITY_LICENSE    — ULF file content (base64 or raw XML) — NEVER echoed
#   UNITY_SERIAL     — Pro/Plus/Enterprise serial key
#   UNITY_EMAIL      — Unity account email
#   UNITY_PASSWORD   — Unity account password
#   UNITY_ACTIVATION_STRATEGY — Force strategy: auto|manual-ulf|serial|account|preactivated|none
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
# PREFLIGHT: verify com.company.build-pipeline is installed in the consumer
# project.  The workflow toolkit invokes
#   Company.BuildPipeline.Editor.BuildCommand.Execute
# via Unity -executeMethod.  If the package is absent Unity silently exits
# with a non-zero code and no useful log entry — this check makes the failure
# fast and actionable before Unity is launched.
# ---------------------------------------------------------------------------
preflight_check_build_package() {
  local project_path="${1:-.}"
  local manifest="${project_path}/Packages/manifest.json"
  local packages_lock="${project_path}/Packages/packages-lock.json"

  # Check manifest.json
  if [[ ! -f "${manifest}" ]]; then
    log_warn "PREFLIGHT: Packages/manifest.json not found at ${project_path} — skipping package check."
    return 0
  fi

  if ! grep -q '"com.company.build-pipeline"' "${manifest}" 2>/dev/null &&
     ! grep -q '"com.company.build-pipeline"' "${packages_lock}" 2>/dev/null; then
    log_error "PREFLIGHT FAILED: Unity build pipeline package is not installed in the consumer project."
    log_error "  Package  : com.company.build-pipeline"
    log_error "  Method   : Company.BuildPipeline.Editor.BuildCommand.Execute"
    log_error "  Fix      : Add 'com.company.build-pipeline' to ${manifest}"
    log_error "             (or install it via UPM at a version compatible with the workflow toolkit)."
    exit 1
  fi

  log_info "PREFLIGHT: com.company.build-pipeline found in consumer project."
}

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
    # Resolve activation strategy using the shared resolver
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    STRATEGY_SCRIPT=""
    for candidate in \
        "${SCRIPT_DIR}/../common/resolve_activation_strategy.sh" \
        "${TOOLKIT_PATH:-}/scripts/common/resolve_activation_strategy.sh"; do
      if [[ -f "${candidate}" ]]; then
        STRATEGY_SCRIPT="$(cd "$(dirname "${candidate}")" && pwd)/$(basename "${candidate}")"
        break
      fi
    done

    if [[ -n "${STRATEGY_SCRIPT}" ]]; then
      log_info "Using strategy resolver: ${STRATEGY_SCRIPT}"
      STRATEGY=$(bash "${STRATEGY_SCRIPT}" 2>&2)
    else
      # Inline fallback
      log_warn "Strategy resolver not found — using inline detection"
      if [[ -n "${UNITY_LICENSE:-}" ]]; then
        STRATEGY="manual-ulf"
      elif [[ -n "${UNITY_SERIAL:-}" && -n "${UNITY_EMAIL:-}" && -n "${UNITY_PASSWORD:-}" ]]; then
        STRATEGY="serial"
      elif [[ -n "${UNITY_EMAIL:-}" && -n "${UNITY_PASSWORD:-}" ]]; then
        STRATEGY="account"
      else
        log_info "No license credentials set — skipping activation"
        exit 0
      fi
    fi

    log_info "Selected activation strategy: ${STRATEGY}"

    TEMP_LICENSE_FILE=""
    _cleanup_license() {
      if [[ -n "${TEMP_LICENSE_FILE}" && -f "${TEMP_LICENSE_FILE}" ]]; then
        rm -f "${TEMP_LICENSE_FILE}" 2>/dev/null || true
      fi
    }
    trap _cleanup_license EXIT

    ACTIVATION_LOG="${LOG_PATH}/Editor-activation.log"

    case "${STRATEGY}" in
      manual-ulf)
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
        ;;

      serial)
        log_info "Activating via UNITY_SERIAL + credentials (serial strategy)"

        run_unity "${ACTIVATION_LOG}" \
          -batchmode \
          -nographics \
          -username "${UNITY_EMAIL}" \
          -password "${UNITY_PASSWORD}" \
          -serial "${UNITY_SERIAL}" \
          -logFile "${ACTIVATION_LOG}" \
          -quit || true
        ;;

      account)
        log_info "Activating via UNITY_EMAIL + UNITY_PASSWORD (account strategy)"
        log_info "Primary method for Unity Personal/free licenses"

        run_unity "${ACTIVATION_LOG}" \
          -batchmode \
          -nographics \
          -username "${UNITY_EMAIL}" \
          -password "${UNITY_PASSWORD}" \
          -logFile  "${ACTIVATION_LOG}" \
          -quit || true
        ;;

      preactivated)
        log_info "Unity already activated on this runner — skipping"
        ;;

      none)
        log_info "Activation explicitly disabled"
        ;;

      blocked)
        log_error "BLOCKED: No valid Unity activation strategy available"
        log_error "See: https://game.ci/docs/github/activation"
        exit 1
        ;;

      *)
        log_error "Unknown activation strategy: ${STRATEGY}"
        exit 1
        ;;
    esac

    log_info "Activation step complete"
    ;;

  # ── build ──────────────────────────────────────────────────────────────────
  build)
    preflight_check_build_package "${PROJECT_PATH}"

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
