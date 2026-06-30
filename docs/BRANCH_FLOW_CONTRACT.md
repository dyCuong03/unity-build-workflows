# Branch-Based Build Flow — Contract

> Extends the explicit-platform-jobs workflow with automatic push/PR flows for
> `develop`, `staging`, `release-*`, while keeping `workflow_dispatch`.
> Platform lists, tests, and addressables flags are configurable via GitHub
> Repository Variables (see [REPOSITORY_VARIABLES.md](REPOSITORY_VARIABLES.md)).

## Flow resolver script (single source of flow logic — testable)

**File (toolkit):** `scripts/common/resolve_build_flow.sh`
Pure bash. Reads env, writes `KEY=value` lines to stdout AND, if `GITHUB_OUTPUT`
is set, appends there too. Never prints secrets.

### Inputs (env)
| Env | Meaning |
|---|---|
| `EVENT_NAME` | `push` \| `pull_request` \| `workflow_dispatch` |
| `REF_NAME` | branch name (push: the branch; PR: head branch; dispatch: current ref) |
| `BASE_REF` | PR target branch (empty for push/dispatch) |
| `IN_PLATFORM` | dispatch input `platform` (All/Android/WebGL/Linux64/LinuxServer/iOS) |
| `IN_ENVIRONMENT` | dispatch input `environment` |
| `IN_RUN_TESTS` | dispatch input `run-tests` (true/false) |
| `IN_TEST_MODE` | dispatch input `test-mode` |
| `IN_BUILD_ADDRESSABLES` | dispatch input `build-addressables` (true/false) |

### Repository Variable inputs (env, optional)
| Env | GitHub Variable | Default |
|---|---|---|
| `VAR_DEVELOP_BUILD_PLATFORMS` | `DEVELOP_BUILD_PLATFORMS` | `Android,WebGL` |
| `VAR_STAGING_BUILD_PLATFORMS` | `STAGING_BUILD_PLATFORMS` | `Android,WebGL,Linux64,LinuxServer` |
| `VAR_RELEASE_BUILD_PLATFORMS` | `RELEASE_BUILD_PLATFORMS` | `Android,WebGL,Linux64,LinuxServer` |
| `VAR_DEVELOP_RUN_TESTS` | `DEVELOP_RUN_TESTS` | `true` |
| `VAR_STAGING_RUN_TESTS` | `STAGING_RUN_TESTS` | `true` |
| `VAR_RELEASE_RUN_TESTS` | `RELEASE_RUN_TESTS` | `true` |
| `VAR_DEVELOP_BUILD_ADDRESSABLES` | `DEVELOP_BUILD_ADDRESSABLES` | `false` |
| `VAR_STAGING_BUILD_ADDRESSABLES` | `STAGING_BUILD_ADDRESSABLES` | `false` |
| `VAR_RELEASE_BUILD_ADDRESSABLES` | `RELEASE_BUILD_ADDRESSABLES` | `true` |
| `VAR_DEFAULT_RUNNER_MODE` | `DEFAULT_RUNNER_MODE` | `docker` |

All repository variable inputs are optional. When unset, the hardcoded defaults
apply. Invalid values cause the script to exit non-zero with a clear error message.
See [REPOSITORY_VARIABLES.md](REPOSITORY_VARIABLES.md) for setup and examples.

### Outputs (all lowercase string values)
| Key | Values |
|---|---|
| `flow-type` | pr-develop \| push-develop \| pr-staging \| push-staging \| pr-release \| push-release \| manual \| none |
| `environment` | development \| staging \| production |
| `run-tests` | true \| false |
| `test-mode` | None \| EditMode \| PlayMode \| All |
| `build-addressables` | true \| false |
| `build-android` | true \| false |
| `build-webgl` | true \| false |
| `build-linux64` | true \| false |
| `build-linuxserver` | true \| false |
| `build-ios` | true \| false  (only manual platform==iOS; never automatic) |
| `signing` | none \| android-release |
| `platform-source` | default \| variable \| dispatch |
| `gh-environment` | GitHub deployment environment: `development` \| `staging` \| `production` (push/manual); **empty** for all PR flows and `none`. PRs never target a GitHub environment, keeping production secrets/approvals off PRs. |

### Flow rules
| Trigger | flow-type | env | tests | addr | platforms built | signing | platform-source |
|---|---|---|---|---|---|---|---|
| PR → develop | pr-develop | development | true | false | *(none — validation only)* | none | default |
| push → develop | push-develop | development | true | false | Android, WebGL | none | default or variable |
| PR → staging | pr-staging | staging | true | false | *(none)* | none | default |
| push → staging | push-staging | staging | true | false | Android, WebGL, Linux64, LinuxServer | none | default or variable |
| PR → release-* | pr-release | production | true | true | *(none)* | none | default |
| push → release-* | push-release | production | true | true | Android, WebGL, Linux64, LinuxServer | android-release | default or variable |
| workflow_dispatch | manual | `IN_ENVIRONMENT` | `IN_RUN_TESTS` | `IN_BUILD_ADDRESSABLES` | per `IN_PLATFORM` | n/a | dispatch |
| anything else | none | development | false | false | *(none)* | none | default |

**Notes:**
- Branch match: `develop` exact; `staging` exact; `release-*` = ref starts with `release-` or `release/`.
- PR target uses `BASE_REF`; push uses `REF_NAME`.
- iOS is NEVER auto-built (no macOS runner); only manual `platform==iOS`.
- `workflow_dispatch` always uses dispatch inputs — repository variables are ignored.
- "default or variable" in the platform-source column: the output is `variable` when
  the corresponding `VAR_*_BUILD_PLATFORMS` env var is set and valid; otherwise `default`.
- `run-tests` and `build-addressables` can also be overridden by repo variables per branch.
  The variable is applied after the branch default, so it takes precedence.

### Platform validation
Allowed platform names (case-sensitive): `Android`, `WebGL`, `Linux64`, `LinuxServer`, `iOS`.
An invalid name in any `VAR_*_BUILD_PLATFORMS` variable causes the script to exit with
a non-zero status and an error message listing the invalid name and the allowed set.

### Priority order
For push/PR events:
1. Repository Variable (if set and valid) — `platform-source=variable`
2. Hardcoded default — `platform-source=default`

For `workflow_dispatch`:
1. Dispatch inputs always win — `platform-source=dispatch`

## Consumer workflow (`.github/workflows/unity-build.yml`)

### Triggers
```yaml
on:
  workflow_dispatch: { inputs: <existing 9 inputs unchanged> }
  push:
    branches: [develop, staging, 'release-*']
  pull_request:
    branches: [develop, staging, 'release-*']
```

### resolve-config job
- Checkout consumer; also obtain the toolkit (checkout repo dyCuong03/unity-build-workflows @ TOOLKIT_REF into a path, OR use the submodule) so `resolve_build_flow.sh` is available.
- Run the resolver with the env mapping above; export ALL resolver outputs as job
  outputs **plus** the existing `unity-version` / `project-path` / `toolkit-ref`.
- Pass `vars.*` as `VAR_*` env vars so the resolver can read repository variables.

### Job gating (replaces the inputs.platform checks)
- `unity-tests`  → `if: !cancelled() && needs.validate-project.result=='success' && needs.resolve-config.outputs.run-tests == 'true'`
  with `test-mode: ${{ needs.resolve-config.outputs.test-mode }}`.
- `build-addressables` → `if: !cancelled() && needs.validate-project.result=='success' && needs.resolve-config.outputs.build-addressables == 'true'`.
- `build-<platform>` → `if: !cancelled() && needs.validate-project.result=='success' && (needs.build-addressables.result=='success' || needs.build-addressables.result=='skipped') && needs.resolve-config.outputs.build-<platform> == 'true'`.
- Pass `environment: ${{ needs.resolve-config.outputs.environment }}` to the reusables.

### final-report (always())
Must print: event (`github.event_name`), branch (`github.ref_name`), target branch
(`github.base_ref` or '-'), flow-type, environment, platform-source, selected platforms,
skipped platforms, blockers (iOS if dispatched without macOS runner), repository variable
values (when platform-source is `variable`), run id, commit.

## Tests
- `tests/test_build_flow.py`: F1–F13 (original scenarios) + V1–V13 (repository variable scenarios).
  - V1: no variables → defaults
  - V2–V4: develop/staging/release variable override
  - V5: invalid platform → exit non-zero
  - V6: dispatch overrides variables
  - V7: run-tests variable override
  - V8: build-addressables variable override
  - V9: platform-source emitted for all flows
  - V10–V11: invalid run-tests/build-addressables → exit non-zero
  - V12: iOS in variable ignored for branch flows
  - V13: whitespace in CSV handled
- `tests/test_platform_selection.py`: gate on `needs.resolve-config.outputs.build-<platform>`.
