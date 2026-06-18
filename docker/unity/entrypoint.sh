#!/usr/bin/env bash
# =============================================================================
# entrypoint.sh — Unity build toolkit container entrypoint
#
# This is the ONLY place Unity is invoked directly inside the container.
# All build logic lives in Company.BuildPipeline.BuildCommand.Execute (C#).
#
# Supported commands:
#   validate            Run project validation (no actual build output)
#   test-editmode       Run Unity EditMode tests
#   test-playmode       Run Unity PlayMode tests
#   build               Execute a full platform build
#   build-addressables  Build Addressable Assets only
#   inspect             Print environment info and exit (no Unity invocation)
#   version             Print Unity version and exit
#
# Usage:
#   entrypoint.sh <command> [options]
#
# Options:
#   --project-path PATH       Path to Unity project root (default: /workspace)
#   --build-config FILE       Path to build config JSON
#   --environment ENV         Build environment: development|staging|production
#   --target-platform PLAT    Build target platform (Android, WebGL, etc.)
#   --build-method METHOD     Override executeMethod (default: Company.BuildPipeline.BuildCommand.Execute)
#   --output-path PATH        Override build output directory
#   --test-results-path PATH  Path for test result XML files
#   --log-dir PATH            Directory to copy Editor.log into after run
# =============================================================================
set -Eeuo pipefail

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
readonly SCRIPT_NAME="$(basename "$0")"
readonly DEFAULT_PROJECT_PATH="/workspace"
readonly DEFAULT_BUILD_METHOD="Company.BuildPipeline.BuildCommand.Execute"
readonly DEFAULT_ENVIRONMENT="development"
readonly UNITY_EDITOR="${UNITY_EDITOR:-/usr/bin/unity-editor}"
readonly UNITY_LOG_FILE="${UNITY_LOG_FILE:-/tmp/unity-home/Editor.log}"

# ---------------------------------------------------------------------------
# Logging helpers
# ---------------------------------------------------------------------------
log_info()  { echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] [INFO]  ${SCRIPT_NAME}: $*" >&2; }
log_warn()  { echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] [WARN]  ${SCRIPT_NAME}: $*" >&2; }
log_error() { echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] [ERROR] ${SCRIPT_NAME}: $*" >&2; }

# ---------------------------------------------------------------------------
# Cleanup trap
# Preserves logs, removes temp credentials, returns license.
# Always runs, regardless of exit code.
# ---------------------------------------------------------------------------
CLEANUP_RAN=0
cleanup() {
    local exit_code=$?
    [[ "${CLEANUP_RAN}" -eq 1 ]] && return
    CLEANUP_RAN=1

    log_info "Running cleanup (exit_code=${exit_code})"

    # Copy Editor.log to mounted log directory
    copy_editor_log

    # Return Unity license (always attempt; failure is non-fatal)
    if [[ -f /usr/local/bin/return-license.sh ]]; then
        /usr/local/bin/return-license.sh || log_warn "License return encountered a non-fatal error"
    fi

    # Remove temp license files (belt-and-suspenders; return-license.sh also does this)
    find /tmp -maxdepth 1 -name "unity-license-*.ulf" -type f -exec rm -f {} + 2>/dev/null || true
    find /tmp -maxdepth 1 -name ".unity3d" -type f -exec rm -f {} + 2>/dev/null || true

    log_info "Cleanup complete"
    exit "${exit_code}"
}
trap cleanup EXIT

# ---------------------------------------------------------------------------
# Path security – reject traversal attempts
# ---------------------------------------------------------------------------
validate_no_traversal() {
    local path="$1" label="$2"
    if [[ "${path}" == *".."* ]]; then
        log_error "Path traversal rejected in ${label}: ${path}"
        exit 1
    fi
}

# ---------------------------------------------------------------------------
# Validate project directory exists and looks like a Unity project
# ---------------------------------------------------------------------------
validate_project_path() {
    local project_path="$1"

    validate_no_traversal "${project_path}" "--project-path"

    if [[ ! -d "${project_path}" ]]; then
        log_error "Project path does not exist or is not a directory: ${project_path}"
        log_error "Mount the Unity project at ${project_path} or pass --project-path"
        exit 1
    fi

    if [[ ! -d "${project_path}/Assets" ]]; then
        log_error "Directory '${project_path}' does not look like a Unity project (missing Assets/ folder)"
        exit 1
    fi
}

# ---------------------------------------------------------------------------
# PREFLIGHT: verify com.company.build-pipeline is installed in the consumer
# project before launching Unity.
#
# The workflow toolkit invokes
#   Company.BuildPipeline.Editor.BuildCommand.Execute
# as the Unity -executeMethod.  If the package is absent Unity silently exits
# with a non-zero code and no useful log entry — this check makes the failure
# fast and actionable before Unity is launched.
# ---------------------------------------------------------------------------
preflight_check_build_package() {
    local project_path="${1}"
    local manifest="${project_path}/Packages/manifest.json"
    local packages_lock="${project_path}/Packages/packages-lock.json"

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
# Ensure output directories exist
# ---------------------------------------------------------------------------
create_output_dirs() {
    local project_path="$1"
    local build_output="$2"
    local test_results="$3"
    local log_dir="$4"

    for dir in \
        "${build_output}" \
        "${project_path}/BuildReports" \
        "${test_results}" \
        "${log_dir}"; do
        if [[ -n "${dir}" ]]; then
            mkdir -p "${dir}"
            log_info "Ensured directory: ${dir}"
        fi
    done
}

# ---------------------------------------------------------------------------
# Copy Editor.log to the log directory
# ---------------------------------------------------------------------------
copy_editor_log() {
    local log_dir="${ARG_LOG_DIR:-${LOG_DIR:-}}"
    if [[ -z "${log_dir}" ]]; then
        return 0
    fi
    if [[ -f "${UNITY_LOG_FILE}" ]]; then
        mkdir -p "${log_dir}"
        local dest="${log_dir}/Editor.log"
        cp -f "${UNITY_LOG_FILE}" "${dest}" 2>/dev/null \
            && log_info "Editor.log copied to: ${dest}" \
            || log_warn "Could not copy Editor.log to: ${dest}"
    else
        log_warn "Unity log file not found: ${UNITY_LOG_FILE}"
    fi
}

# ---------------------------------------------------------------------------
# Activate Unity license if UNITY_LICENSE (or email/password) is set
# ---------------------------------------------------------------------------
activate_license_if_needed() {
    if [[ -z "${UNITY_LICENSE:-}" && -z "${UNITY_EMAIL:-}" ]]; then
        log_info "No license environment variables set – skipping activation"
        log_info "If your Unity version requires a license, set UNITY_LICENSE or UNITY_EMAIL + UNITY_PASSWORD"
        return 0
    fi
    log_info "License environment variable detected – running activate-license.sh"
    /usr/local/bin/activate-license.sh || {
        log_error "License activation failed. Check UNITY_LICENSE / UNITY_EMAIL / UNITY_PASSWORD."
        log_error "Editor.log may contain additional details."
        copy_editor_log
        exit 1
    }
}

# ---------------------------------------------------------------------------
# Run Unity with the given arguments; stream stdout/stderr; capture exit code
# ---------------------------------------------------------------------------
run_unity() {
    local -a unity_args=("$@")
    log_info "Invoking Unity: ${UNITY_EDITOR} ${unity_args[*]}"

    # Run Unity and capture its real exit code.
    # We disable errexit temporarily to prevent the script from aborting
    # before we can capture the exit code.
    local unity_exit=0
    set +e
    "${UNITY_EDITOR}" "${unity_args[@]}" 2>&1 | tee -a "${UNITY_LOG_FILE}"
    local -a pipe_status=("${PIPESTATUS[@]}")
    set -e
    unity_exit="${pipe_status[0]}"

    if [[ "${unity_exit}" -ne 0 ]]; then
        log_error "Unity exited with code ${unity_exit}"
        log_error "Check ${UNITY_LOG_FILE} or the copied Editor.log for details"
    else
        log_info "Unity exited successfully (code 0)"
    fi

    return "${unity_exit}"
}

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
COMMAND="${1:-inspect}"
shift || true

ARG_PROJECT_PATH="${DEFAULT_PROJECT_PATH}"
ARG_BUILD_CONFIG=""
ARG_ENVIRONMENT="${DEFAULT_ENVIRONMENT}"
ARG_TARGET_PLATFORM="${BUILD_TARGET:-}"
ARG_BUILD_METHOD="${DEFAULT_BUILD_METHOD}"
ARG_OUTPUT_PATH="${BUILD_OUTPUT_PATH:-/workspace/Builds}"
ARG_TEST_RESULTS_PATH="${TEST_RESULTS_PATH:-/workspace/TestResults}"
ARG_LOG_DIR="${LOG_DIR:-/workspace/Logs}"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --project-path)
            ARG_PROJECT_PATH="${2:?'--project-path requires a value'}"
            shift 2
            ;;
        --build-config)
            ARG_BUILD_CONFIG="${2:?'--build-config requires a value'}"
            shift 2
            ;;
        --environment)
            ARG_ENVIRONMENT="${2:?'--environment requires a value'}"
            shift 2
            ;;
        --target-platform)
            ARG_TARGET_PLATFORM="${2:?'--target-platform requires a value'}"
            shift 2
            ;;
        --build-method)
            ARG_BUILD_METHOD="${2:?'--build-method requires a value'}"
            shift 2
            ;;
        --output-path)
            ARG_OUTPUT_PATH="${2:?'--output-path requires a value'}"
            shift 2
            ;;
        --test-results-path)
            ARG_TEST_RESULTS_PATH="${2:?'--test-results-path requires a value'}"
            shift 2
            ;;
        --log-dir)
            ARG_LOG_DIR="${2:?'--log-dir requires a value'}"
            shift 2
            ;;
        --)
            shift
            break
            ;;
        --*)
            log_error "Unknown option: $1"
            log_error "Run 'entrypoint.sh inspect' to see usage"
            exit 1
            ;;
        *)
            log_error "Unexpected positional argument after command: $1"
            exit 1
            ;;
    esac
done

# Validate extra paths for traversal
[[ -n "${ARG_BUILD_CONFIG}" ]]       && validate_no_traversal "${ARG_BUILD_CONFIG}"       "--build-config"
[[ -n "${ARG_OUTPUT_PATH}" ]]        && validate_no_traversal "${ARG_OUTPUT_PATH}"        "--output-path"
[[ -n "${ARG_TEST_RESULTS_PATH}" ]]  && validate_no_traversal "${ARG_TEST_RESULTS_PATH}"  "--test-results-path"
[[ -n "${ARG_LOG_DIR}" ]]            && validate_no_traversal "${ARG_LOG_DIR}"            "--log-dir"

# ---------------------------------------------------------------------------
# Command dispatch
# ---------------------------------------------------------------------------
case "${COMMAND}" in

    # -----------------------------------------------------------------------
    version)
        log_info "Unity version: ${UNITY_VERSION:-unknown}"
        if [[ -x "${UNITY_EDITOR}" ]]; then
            "${UNITY_EDITOR}" -version 2>/dev/null || true
        fi
        exit 0
        ;;

    # -----------------------------------------------------------------------
    inspect)
        log_info "=== Unity Build Toolkit Container Inspect ==="
        log_info "Unity Editor   : ${UNITY_EDITOR}"
        log_info "Unity Version  : ${UNITY_VERSION:-unset}"
        log_info "Build Target   : ${ARG_TARGET_PLATFORM:-unset}"
        log_info "Environment    : ${ARG_ENVIRONMENT}"
        log_info "Project Path   : ${ARG_PROJECT_PATH}"
        log_info "Output Path    : ${ARG_OUTPUT_PATH}"
        log_info "Build Config   : ${ARG_BUILD_CONFIG:-unset}"
        log_info "Build Method   : ${ARG_BUILD_METHOD}"
        log_info "Log Dir        : ${ARG_LOG_DIR}"
        log_info "Unity execpath : $(command -v unity-editor 2>/dev/null || echo 'not found in PATH')"
        log_info "HOME           : ${HOME}"
        log_info "USER           : $(id)"
        log_info "Disk usage:"
        df -h /workspace 2>/dev/null || true
        exit 0
        ;;

    # -----------------------------------------------------------------------
    validate)
        validate_project_path "${ARG_PROJECT_PATH}"
        create_output_dirs "${ARG_PROJECT_PATH}" "${ARG_OUTPUT_PATH}" \
                           "${ARG_TEST_RESULTS_PATH}" "${ARG_LOG_DIR}"
        activate_license_if_needed

        log_info "Running project validation (validate-only, no build output)"

        unity_args=(
            -batchmode
            -nographics
            -projectPath "${ARG_PROJECT_PATH}"
            -executeMethod "${ARG_BUILD_METHOD}"
            -logFile "${UNITY_LOG_FILE}"
            -quit
            -customArgs "command=validate"
        )

        [[ -n "${ARG_BUILD_CONFIG}" ]]   && unity_args+=(-customArgs "buildConfig=${ARG_BUILD_CONFIG}")
        [[ -n "${ARG_ENVIRONMENT}" ]]    && unity_args+=(-customArgs "environment=${ARG_ENVIRONMENT}")
        [[ -n "${ARG_TARGET_PLATFORM}" ]] && unity_args+=(-buildTarget "${ARG_TARGET_PLATFORM}")
        unity_args+=(-customArgs "outputPath=${ARG_OUTPUT_PATH}")

        run_unity "${unity_args[@]}"
        ;;

    # -----------------------------------------------------------------------
    test-editmode)
        validate_project_path "${ARG_PROJECT_PATH}"
        create_output_dirs "${ARG_PROJECT_PATH}" "${ARG_OUTPUT_PATH}" \
                           "${ARG_TEST_RESULTS_PATH}" "${ARG_LOG_DIR}"
        activate_license_if_needed

        log_info "Running EditMode tests"

        unity_args=(
            -batchmode
            -nographics
            -projectPath "${ARG_PROJECT_PATH}"
            -runTests
            -testPlatform EditMode
            -testResults "${ARG_TEST_RESULTS_PATH}/editmode-results.xml"
            -logFile "${UNITY_LOG_FILE}"
        )

        [[ -n "${ARG_BUILD_CONFIG}" ]] && unity_args+=(-customArgs "buildConfig=${ARG_BUILD_CONFIG}")
        [[ -n "${ARG_TARGET_PLATFORM}" ]] && unity_args+=(-buildTarget "${ARG_TARGET_PLATFORM}")

        run_unity "${unity_args[@]}"
        ;;

    # -----------------------------------------------------------------------
    test-playmode)
        validate_project_path "${ARG_PROJECT_PATH}"
        create_output_dirs "${ARG_PROJECT_PATH}" "${ARG_OUTPUT_PATH}" \
                           "${ARG_TEST_RESULTS_PATH}" "${ARG_LOG_DIR}"
        activate_license_if_needed

        log_info "Running PlayMode tests"

        unity_args=(
            -batchmode
            -nographics
            -projectPath "${ARG_PROJECT_PATH}"
            -runTests
            -testPlatform PlayMode
            -testResults "${ARG_TEST_RESULTS_PATH}/playmode-results.xml"
            -logFile "${UNITY_LOG_FILE}"
        )

        [[ -n "${ARG_BUILD_CONFIG}" ]] && unity_args+=(-customArgs "buildConfig=${ARG_BUILD_CONFIG}")
        [[ -n "${ARG_TARGET_PLATFORM}" ]] && unity_args+=(-buildTarget "${ARG_TARGET_PLATFORM}")

        run_unity "${unity_args[@]}"
        ;;

    # -----------------------------------------------------------------------
    build)
        validate_project_path "${ARG_PROJECT_PATH}"
        preflight_check_build_package "${ARG_PROJECT_PATH}"

        if [[ -z "${ARG_TARGET_PLATFORM}" ]]; then
            log_error "--target-platform is required for the 'build' command"
            log_error "Example: entrypoint.sh build --target-platform Android"
            exit 1
        fi

        create_output_dirs "${ARG_PROJECT_PATH}" "${ARG_OUTPUT_PATH}" \
                           "${ARG_TEST_RESULTS_PATH}" "${ARG_LOG_DIR}"
        activate_license_if_needed

        log_info "Building platform: ${ARG_TARGET_PLATFORM}"

        unity_args=(
            -batchmode
            -nographics
            -projectPath "${ARG_PROJECT_PATH}"
            -executeMethod "${ARG_BUILD_METHOD}"
            -buildTarget "${ARG_TARGET_PLATFORM}"
            -logFile "${UNITY_LOG_FILE}"
            -quit
            -customArgs "command=build"
            -customArgs "environment=${ARG_ENVIRONMENT}"
            -customArgs "outputPath=${ARG_OUTPUT_PATH}"
        )

        [[ -n "${ARG_BUILD_CONFIG}" ]] && unity_args+=(-customArgs "buildConfig=${ARG_BUILD_CONFIG}")

        run_unity "${unity_args[@]}"
        ;;

    # -----------------------------------------------------------------------
    build-addressables)
        validate_project_path "${ARG_PROJECT_PATH}"
        preflight_check_build_package "${ARG_PROJECT_PATH}"
        create_output_dirs "${ARG_PROJECT_PATH}" "${ARG_OUTPUT_PATH}" \
                           "${ARG_TEST_RESULTS_PATH}" "${ARG_LOG_DIR}"
        activate_license_if_needed

        log_info "Building Addressable Assets"

        unity_args=(
            -batchmode
            -nographics
            -projectPath "${ARG_PROJECT_PATH}"
            -executeMethod "${ARG_BUILD_METHOD}"
            -logFile "${UNITY_LOG_FILE}"
            -quit
            -customArgs "command=build-addressables"
            -customArgs "environment=${ARG_ENVIRONMENT}"
            -customArgs "outputPath=${ARG_OUTPUT_PATH}"
        )

        [[ -n "${ARG_BUILD_CONFIG}" ]]    && unity_args+=(-customArgs "buildConfig=${ARG_BUILD_CONFIG}")
        [[ -n "${ARG_TARGET_PLATFORM}" ]] && unity_args+=(-buildTarget "${ARG_TARGET_PLATFORM}")

        run_unity "${unity_args[@]}"
        ;;

    # -----------------------------------------------------------------------
    *)
        log_error "Unknown command: '${COMMAND}'"
        log_error ""
        log_error "Supported commands:"
        log_error "  validate          – validate project without building"
        log_error "  test-editmode     – run Unity EditMode tests"
        log_error "  test-playmode     – run Unity PlayMode tests"
        log_error "  build             – build for a target platform"
        log_error "  build-addressables – build Addressable Assets"
        log_error "  inspect           – print environment info (no Unity invocation)"
        log_error "  version           – print Unity version"
        exit 1
        ;;
esac
