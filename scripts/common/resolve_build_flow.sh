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

log_info "EVENT_NAME=${EVENT_NAME} REF_NAME=${REF_NAME} BASE_REF=${BASE_REF}"

# ---------------------------------------------------------------------------
# Branch classification helpers
# ---------------------------------------------------------------------------
_is_develop() { [[ "${1}" == "develop" ]]; }
_is_staging()  { [[ "${1}" == "staging" ]]; }
_is_release()  { [[ "${1}" == release-* || "${1}" == release/* ]]; }

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
build_ios="false"
signing="none"

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
    elif _is_staging "${target}"; then
      flow_type="pr-staging"; environment="staging"
      run_tests="true"; test_mode="All"
      # PR → staging: validation only, no binary builds
    elif _is_release "${target}"; then
      flow_type="pr-release"; environment="production"
      run_tests="true"; test_mode="All"
      build_addressables="true"
      # PR → release-*: validation + addressables check, no binary builds
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
      build_android="true"; build_webgl="true"
    elif _is_staging "${branch}"; then
      flow_type="push-staging"; environment="staging"
      run_tests="true"; test_mode="All"
      build_android="true"; build_webgl="true"
      build_linux64="true"; build_linuxserver="true"
    elif _is_release "${branch}"; then
      flow_type="push-release"; environment="production"
      run_tests="true"; test_mode="All"
      build_addressables="true"
      build_android="true"; build_webgl="true"
      build_linux64="true"; build_linuxserver="true"
      signing="android-release"
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
    log_info "workflow_dispatch: platform=${IN_PLATFORM} environment=${environment} run-tests=${run_tests}"

    # Platform selection — iOS is only ever built via explicit manual dispatch
    case "${IN_PLATFORM}" in
      All)
        # All excludes iOS — no macOS runner in automatic builds
        build_android="true"; build_webgl="true"
        build_linux64="true"; build_linuxserver="true"
        ;;
      Android)     build_android="true" ;;
      WebGL)       build_webgl="true" ;;
      Linux64)     build_linux64="true" ;;
      LinuxServer) build_linuxserver="true" ;;
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

log_info "flow-type=${flow_type} environment=${environment} run-tests=${run_tests} test-mode=${test_mode}"
log_info "build-addressables=${build_addressables} signing=${signing}"
log_info "platforms: android=${build_android} webgl=${build_webgl} linux64=${build_linux64} linuxserver=${build_linuxserver} ios=${build_ios}"

# ---------------------------------------------------------------------------
# Emit all outputs
# ---------------------------------------------------------------------------
emit "flow-type"           "${flow_type}"
emit "environment"         "${environment}"
emit "run-tests"           "${run_tests}"
emit "test-mode"           "${test_mode}"
emit "build-addressables"  "${build_addressables}"
emit "build-android"       "${build_android}"
emit "build-webgl"         "${build_webgl}"
emit "build-linux64"       "${build_linux64}"
emit "build-linuxserver"   "${build_linuxserver}"
emit "build-ios"           "${build_ios}"
emit "signing"             "${signing}"
