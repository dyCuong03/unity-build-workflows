#!/usr/bin/env bash
# =============================================================================
# resolve_build_flow.sh — Build flow resolver (branch-based CI automation)
#
# Reads trigger context from env, writes KEY=value lines to stdout AND
# appends to $GITHUB_OUTPUT when that variable is set in the environment.
# All diagnostic output goes to stderr only — never to stdout.
#
# Inputs (env):
#   EVENT_NAME             push | pull_request | workflow_dispatch
#   REF_NAME               branch/ref name for push or dispatch
#   BASE_REF               PR target branch (empty for push/dispatch)
#   IN_PLATFORM            dispatch: All | Android | WebGL | Linux64 | LinuxServer | iOS
#   IN_ENVIRONMENT         dispatch: production | staging | development
#   IN_RUN_TESTS           dispatch: true | false
#   IN_TEST_MODE           dispatch: EditMode | PlayMode | All
#   IN_BUILD_ADDRESSABLES  dispatch: true | false
#
# Repository Variable inputs (env, optional — set from GitHub vars.*):
#   VAR_DEVELOP_BUILD_PLATFORMS     CSV: Android,WebGL (default)
#   VAR_STAGING_BUILD_PLATFORMS     CSV: Android,WebGL,Linux64,LinuxServer (default)
#   VAR_RELEASE_BUILD_PLATFORMS     CSV: Android,WebGL,Linux64,LinuxServer (default)
#   VAR_DEVELOP_RUN_TESTS           true|false (default: true)
#   VAR_STAGING_RUN_TESTS           true|false (default: true)
#   VAR_RELEASE_RUN_TESTS           true|false (default: true)
#   VAR_DEVELOP_BUILD_ADDRESSABLES  true|false (default: false)
#   VAR_STAGING_BUILD_ADDRESSABLES  true|false (default: false)
#   VAR_RELEASE_BUILD_ADDRESSABLES  true|false (default: true)
#   VAR_DEFAULT_RUNNER_MODE         docker|self-hosted-windows|auto (default: docker)
#
# Outputs (stdout + GITHUB_OUTPUT when set):
#   flow-type           pr-develop | push-develop | pr-staging | push-staging |
#                       pr-release | push-release | manual | none
#   environment         development | staging | production
#   run-tests           true | false
#   test-mode           None | EditMode | PlayMode | All
#   build-addressables  true | false
#   build-android       true | false
#   build-webgl         true | false
#   build-linux64       true | false
#   build-linuxserver   true | false
#   build-ios           true | false  (manual platform=iOS only; NEVER auto)
#   signing             none | android-release
#   platform-source     default | variable | dispatch
#
# Branch matching rules:
#   develop:   exact match
#   staging:   exact match
#   release-*: starts with 'release-' or 'release/'
#
# PR target branch uses BASE_REF; push uses REF_NAME.
#
# Contract: docs/BRANCH_FLOW_CONTRACT.md
# =============================================================================
set -Eeuo pipefail

# ---------------------------------------------------------------------------
# Logging — stderr only
# ---------------------------------------------------------------------------
_log_prefix="resolve-build-flow"
log_info()  { printf '[%s] [INFO]  %s: %s\n'  "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "${_log_prefix}" "$*" >&2; }
log_warn()  { printf '[%s] [WARN]  %s: %s\n'  "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "${_log_prefix}" "$*" >&2; }
log_error() { printf '[%s] [ERROR] %s: %s\n'  "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "${_log_prefix}" "$*" >&2; }

# ---------------------------------------------------------------------------
# emit KEY VALUE — write to stdout and (if set) append to $GITHUB_OUTPUT
# ---------------------------------------------------------------------------
emit() {
    local key="$1" val="$2"
    printf '%s=%s\n' "${key}" "${val}"
    if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
        printf '%s=%s\n' "${key}" "${val}" >> "${GITHUB_OUTPUT}"
    fi
}

# ---------------------------------------------------------------------------
# Inputs — read from env, never fail on missing (default to empty)
# ---------------------------------------------------------------------------
EVENT_NAME="${EVENT_NAME:-}"
REF_NAME="${REF_NAME:-}"
BASE_REF="${BASE_REF:-}"
IN_PLATFORM="${IN_PLATFORM:-}"
IN_ENVIRONMENT="${IN_ENVIRONMENT:-production}"
IN_RUN_TESTS="${IN_RUN_TESTS:-false}"
IN_TEST_MODE="${IN_TEST_MODE:-All}"
IN_BUILD_ADDRESSABLES="${IN_BUILD_ADDRESSABLES:-false}"
IN_DEFINE_SYMBOLS="${IN_DEFINE_SYMBOLS:-}"   # manual-dispatch extra define symbols (optional)

# Repository variable inputs (optional, from GitHub vars.*)
VAR_DEVELOP_BUILD_PLATFORMS="${VAR_DEVELOP_BUILD_PLATFORMS:-}"
VAR_STAGING_BUILD_PLATFORMS="${VAR_STAGING_BUILD_PLATFORMS:-}"
VAR_RELEASE_BUILD_PLATFORMS="${VAR_RELEASE_BUILD_PLATFORMS:-}"
VAR_DEVELOP_RUN_TESTS="${VAR_DEVELOP_RUN_TESTS:-}"
VAR_STAGING_RUN_TESTS="${VAR_STAGING_RUN_TESTS:-}"
VAR_RELEASE_RUN_TESTS="${VAR_RELEASE_RUN_TESTS:-}"
VAR_DEVELOP_BUILD_ADDRESSABLES="${VAR_DEVELOP_BUILD_ADDRESSABLES:-}"
VAR_STAGING_BUILD_ADDRESSABLES="${VAR_STAGING_BUILD_ADDRESSABLES:-}"
VAR_RELEASE_BUILD_ADDRESSABLES="${VAR_RELEASE_BUILD_ADDRESSABLES:-}"
VAR_DEFAULT_RUNNER_MODE="${VAR_DEFAULT_RUNNER_MODE:-}"
# Per-branch extra Scripting Define Symbols (additive; ';' or ',' separated).
# Applied to ProjectSettings.asset at build time by apply_define_symbols.sh.
VAR_DEVELOP_DEFINE_SYMBOLS="${VAR_DEVELOP_DEFINE_SYMBOLS:-}"
VAR_STAGING_DEFINE_SYMBOLS="${VAR_STAGING_DEFINE_SYMBOLS:-}"
VAR_RELEASE_DEFINE_SYMBOLS="${VAR_RELEASE_DEFINE_SYMBOLS:-}"

log_info "EVENT_NAME=${EVENT_NAME} REF_NAME=${REF_NAME} BASE_REF=${BASE_REF}"

# ---------------------------------------------------------------------------
# Branch classification helpers
# ---------------------------------------------------------------------------
_is_develop() { [[ "${1}" == "develop" ]]; }
_is_staging()  { [[ "${1}" == "staging" ]]; }
_is_release()  { [[ "${1}" == release-* || "${1}" == release/* ]]; }

# ---------------------------------------------------------------------------
# Platform validation and CSV parsing
# ---------------------------------------------------------------------------
VALID_PLATFORMS="Android WebGL Linux64 LinuxServer Windows64 iOS"

validate_platform() {
    local plat="$1"
    for valid in ${VALID_PLATFORMS}; do
        [[ "${plat}" == "${valid}" ]] && return 0
    done
    return 1
}

# parse_platforms CSV_STRING VAR_NAME
#   Parses comma-separated platform list, validates each entry.
#   Exits with error if any platform is invalid.
#   Prints validated platforms space-separated to stdout.
parse_platforms() {
    local csv="$1" var_name="$2"
    # Replace commas with spaces for safe iteration (IFS stays default)
    local normalized="${csv//,/ }"
    local platforms=()
    for plat in ${normalized}; do
        # Trim any remaining whitespace
        plat="$(echo "${plat}" | tr -d '[:space:]')"
        [[ -z "${plat}" ]] && continue
        if ! validate_platform "${plat}"; then
            log_error "Invalid platform '${plat}' in ${var_name}='${csv}'. Allowed: ${VALID_PLATFORMS}"
            exit 1
        fi
        platforms+=("${plat}")
    done
    echo "${platforms[*]}"
}

# set_platforms_from_list SPACE_SEPARATED_LIST
#   Sets build_android/webgl/linux64/linuxserver/ios from a validated platform list.
#   iOS is NEVER set from branch flows (only manual dispatch).
set_platforms_from_list() {
    local list="$1" allow_ios="${2:-false}"
    build_android="false"
    build_webgl="false"
    build_linux64="false"
    build_linuxserver="false"
    build_windows64="false"
    if [[ "${allow_ios}" == "true" ]]; then
        build_ios="false"
    fi
    for plat in ${list}; do
        case "${plat}" in
            Android)     build_android="true" ;;
            WebGL)       build_webgl="true" ;;
            Linux64)     build_linux64="true" ;;
            LinuxServer) build_linuxserver="true" ;;
            Windows64)   build_windows64="true" ;;
            iOS)
                if [[ "${allow_ios}" == "true" ]]; then
                    build_ios="true"
                else
                    log_warn "iOS in platform list ignored for branch flow (manual dispatch only)"
                fi
                ;;
        esac
    done
}

# ---------------------------------------------------------------------------
# Output variable defaults (overridden per flow below)
# ---------------------------------------------------------------------------
flow_type="none"
environment="development"
run_tests="false"
test_mode="None"
build_addressables="false"
build_android="false"
build_webgl="false"
build_linux64="false"
build_linuxserver="false"
build_windows64="false"
build_ios="false"
signing="none"
platform_source="default"
android_export_type="apk"   # apk | aab (Android output format)
define_symbols=""           # extra Scripting Define Symbols (branch-scoped, additive)

# ---------------------------------------------------------------------------
# Default platform lists per branch (used when no repo variable is set)
# ---------------------------------------------------------------------------
DEFAULT_DEVELOP_PLATFORMS="Android WebGL"
DEFAULT_STAGING_PLATFORMS="Android WebGL Linux64 LinuxServer Windows64"
DEFAULT_RELEASE_PLATFORMS="Android WebGL Linux64 LinuxServer Windows64"

# ---------------------------------------------------------------------------
# resolve_branch_platforms BRANCH_TYPE
#   Resolves platforms for a push event using repo variables or defaults.
#   Sets build_* flags and platform_source.
#   BRANCH_TYPE: develop | staging | release
# ---------------------------------------------------------------------------
resolve_branch_platforms() {
    local branch_type="$1"
    local var_value="" default_list="" var_name=""

    case "${branch_type}" in
        develop)
            var_value="${VAR_DEVELOP_BUILD_PLATFORMS}"
            var_name="VAR_DEVELOP_BUILD_PLATFORMS"
            default_list="${DEFAULT_DEVELOP_PLATFORMS}"
            ;;
        staging)
            var_value="${VAR_STAGING_BUILD_PLATFORMS}"
            var_name="VAR_STAGING_BUILD_PLATFORMS"
            default_list="${DEFAULT_STAGING_PLATFORMS}"
            ;;
        release)
            var_value="${VAR_RELEASE_BUILD_PLATFORMS}"
            var_name="VAR_RELEASE_BUILD_PLATFORMS"
            default_list="${DEFAULT_RELEASE_PLATFORMS}"
            ;;
    esac

    if [[ -n "${var_value}" ]]; then
        local validated
        validated="$(parse_platforms "${var_value}" "${var_name}")"
        set_platforms_from_list "${validated}"
        platform_source="variable"
        log_info "Platforms from repo variable ${var_name}='${var_value}'"
    else
        set_platforms_from_list "${default_list}"
        platform_source="default"
        log_info "Platforms from defaults: ${default_list}"
    fi
}

# ---------------------------------------------------------------------------
# resolve_branch_optional BRANCH_TYPE
#   Resolves optional run-tests and build-addressables from repo variables.
#   Only overrides if the repo variable is set (non-empty).
#   BRANCH_TYPE: develop | staging | release
# ---------------------------------------------------------------------------
resolve_branch_optional() {
    local branch_type="$1"
    local var_run_tests="" var_build_addr=""

    case "${branch_type}" in
        develop)
            var_run_tests="${VAR_DEVELOP_RUN_TESTS}"
            var_build_addr="${VAR_DEVELOP_BUILD_ADDRESSABLES}"
            ;;
        staging)
            var_run_tests="${VAR_STAGING_RUN_TESTS}"
            var_build_addr="${VAR_STAGING_BUILD_ADDRESSABLES}"
            ;;
        release)
            var_run_tests="${VAR_RELEASE_RUN_TESTS}"
            var_build_addr="${VAR_RELEASE_BUILD_ADDRESSABLES}"
            ;;
    esac

    if [[ -n "${var_run_tests}" ]]; then
        if [[ "${var_run_tests}" == "true" || "${var_run_tests}" == "false" ]]; then
            run_tests="${var_run_tests}"
            log_info "run-tests from repo variable: ${var_run_tests}"
        else
            log_error "Invalid VAR_${branch_type^^}_RUN_TESTS='${var_run_tests}'. Must be 'true' or 'false'."
            exit 1
        fi
    fi

    if [[ -n "${var_build_addr}" ]]; then
        if [[ "${var_build_addr}" == "true" || "${var_build_addr}" == "false" ]]; then
            build_addressables="${var_build_addr}"
            log_info "build-addressables from repo variable: ${var_build_addr}"
        else
            log_error "Invalid VAR_${branch_type^^}_BUILD_ADDRESSABLES='${var_build_addr}'. Must be 'true' or 'false'."
            exit 1
        fi
    fi
}

# ---------------------------------------------------------------------------
# resolve_branch_define_symbols BRANCH_TYPE
#   Resolves extra Scripting Define Symbols from a per-branch repo variable.
#   Additive: these are merged into the project's existing symbols at build
#   time (see apply_define_symbols.sh). Only sets define_symbols if the repo
#   variable is non-empty; otherwise leaves it as the default (empty).
#   BRANCH_TYPE: develop | staging | release
# ---------------------------------------------------------------------------
resolve_branch_define_symbols() {
    local branch_type="$1"
    local var_value=""

    case "${branch_type}" in
        develop) var_value="${VAR_DEVELOP_DEFINE_SYMBOLS}" ;;
        staging) var_value="${VAR_STAGING_DEFINE_SYMBOLS}" ;;
        release) var_value="${VAR_RELEASE_DEFINE_SYMBOLS}" ;;
    esac

    if [[ -n "${var_value}" ]]; then
        define_symbols="${var_value}"
        log_info "define-symbols from repo variable VAR_${branch_type^^}_DEFINE_SYMBOLS='${var_value}'"
    fi
}

# ---------------------------------------------------------------------------
# Flow resolution
# ---------------------------------------------------------------------------
case "${EVENT_NAME}" in

  pull_request)
    target="${BASE_REF}"
    log_info "pull_request: target=${target}"
    if _is_develop "${target}"; then
      flow_type="pr-develop"; environment="development"
      run_tests="true"; test_mode="All"
      # PR → develop: validation only, no binary builds
      resolve_branch_optional "develop"
      resolve_branch_define_symbols "develop"
    elif _is_staging "${target}"; then
      flow_type="pr-staging"; environment="staging"
      run_tests="true"; test_mode="All"
      # PR → staging: validation only, no binary builds
      resolve_branch_optional "staging"
      resolve_branch_define_symbols "staging"
    elif _is_release "${target}"; then
      flow_type="pr-release"; environment="production"
      run_tests="true"; test_mode="All"
      build_addressables="true"
      # PR → release-*: validation + addressables check, no binary builds
      resolve_branch_optional "release"
      resolve_branch_define_symbols "release"
    else
      log_warn "PR target branch '${target}' does not match develop/staging/release-*; flow=none"
    fi
    ;;

  push)
    branch="${REF_NAME}"
    log_info "push: branch=${branch}"
    if _is_develop "${branch}"; then
      flow_type="push-develop"; environment="development"
      run_tests="true"; test_mode="All"
      resolve_branch_platforms "develop"
      resolve_branch_optional "develop"
      resolve_branch_define_symbols "develop"
    elif _is_staging "${branch}"; then
      flow_type="push-staging"; environment="staging"
      run_tests="true"; test_mode="All"
      resolve_branch_platforms "staging"
      resolve_branch_optional "staging"
      resolve_branch_define_symbols "staging"
    elif _is_release "${branch}"; then
      flow_type="push-release"; environment="production"
      run_tests="true"; test_mode="All"
      build_addressables="true"
      resolve_branch_platforms "release"
      resolve_branch_optional "release"
      resolve_branch_define_symbols "release"
      signing="android-release"
      android_export_type="aab"   # release builds produce an App Bundle for the Play Store
    else
      log_warn "Push branch '${branch}' does not match develop/staging/release-*; flow=none"
    fi
    ;;

  workflow_dispatch)
    flow_type="manual"
    environment="${IN_ENVIRONMENT}"
    run_tests="${IN_RUN_TESTS}"
    test_mode="${IN_TEST_MODE}"
    build_addressables="${IN_BUILD_ADDRESSABLES}"
    platform_source="dispatch"
    android_export_type="${IN_ANDROID_EXPORT:-apk}"
    define_symbols="${IN_DEFINE_SYMBOLS}"
    log_info "workflow_dispatch: platform=${IN_PLATFORM} environment=${environment} run-tests=${run_tests}"

    # Platform selection — iOS is only ever built via explicit manual dispatch
    case "${IN_PLATFORM}" in
      All)
        # All excludes iOS — no macOS runner in automatic builds
        build_android="true"; build_webgl="true"
        build_linux64="true"; build_linuxserver="true"
        build_windows64="true"
        ;;
      Android)     build_android="true" ;;
      WebGL)       build_webgl="true" ;;
      Linux64)     build_linux64="true" ;;
      LinuxServer) build_linuxserver="true" ;;
      Windows64)   build_windows64="true" ;;
      iOS)
        # iOS: manual only; reusable guard will block if no macOS runner
        build_ios="true"
        ;;
      "")
        log_warn "IN_PLATFORM not set for workflow_dispatch; no platform builds will run"
        ;;
      *)
        log_warn "Unknown IN_PLATFORM='${IN_PLATFORM}'; no platform builds will run"
        ;;
    esac
    ;;

  "")
    log_warn "EVENT_NAME is empty; flow=none"
    ;;

  *)
    log_warn "Unrecognised EVENT_NAME='${EVENT_NAME}'; flow=none"
    ;;
esac

# ---------------------------------------------------------------------------
# Normalise: if run-tests is false, test-mode must be None
# ---------------------------------------------------------------------------
if [[ "${run_tests}" == "false" ]]; then
    test_mode="None"
fi

# ---------------------------------------------------------------------------
# GitHub deployment environment (distinct from the Unity build `environment`).
# Only push and manual flows map to a real GitHub Environment / deployment.
# Pull-request flows are validation-only and MUST NOT target a GitHub
# environment (keeps production-scoped secrets/approvals away from PRs).
# ---------------------------------------------------------------------------
case "${flow_type}" in
    pr-develop|pr-staging|pr-release|none) gh_environment="" ;;
    *)                                     gh_environment="${environment}" ;;
esac

log_info "gh-environment=${gh_environment} (deployment target; empty = none)"
log_info "flow-type=${flow_type} environment=${environment} run-tests=${run_tests} test-mode=${test_mode}"
log_info "build-addressables=${build_addressables} signing=${signing}"
log_info "platforms: android=${build_android} webgl=${build_webgl} linux64=${build_linux64} linuxserver=${build_linuxserver} windows64=${build_windows64} ios=${build_ios}"
log_info "platform-source=${platform_source}"
log_info "define-symbols=${define_symbols:-<none>}"

# ---------------------------------------------------------------------------
# Emit all outputs
# ---------------------------------------------------------------------------
emit "flow-type"           "${flow_type}"
emit "define-symbols"      "${define_symbols}"
emit "environment"         "${environment}"
emit "gh-environment"      "${gh_environment}"
emit "run-tests"           "${run_tests}"
emit "test-mode"           "${test_mode}"
emit "build-addressables"  "${build_addressables}"
emit "build-android"       "${build_android}"
emit "build-webgl"         "${build_webgl}"
emit "build-linux64"       "${build_linux64}"
emit "build-linuxserver"   "${build_linuxserver}"
emit "build-windows64"     "${build_windows64}"
emit "build-ios"           "${build_ios}"
emit "signing"             "${signing}"
emit "android-export-type" "${android_export_type}"
emit "platform-source"     "${platform_source}"
