# Branch-Based Build Flow — Contract

> Extends the explicit-platform-jobs workflow with automatic push/PR flows for
> `develop`, `staging`, `release-*`, while keeping `workflow_dispatch`.

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

### Flow rules
| Trigger | flow-type | env | tests | addr | platforms built | signing |
|---|---|---|---|---|---|---|
| PR → develop | pr-develop | development | true | false | *(none — validation only)* | none |
| push → develop | push-develop | development | true | false | Android, WebGL | none |
| PR → staging | pr-staging | staging | true | false | *(none)* | none |
| push → staging | push-staging | staging | true | false | Android, WebGL, Linux64, LinuxServer | none |
| PR → release-* | pr-release | production | true | true | *(none)* | none |
| push → release-* | push-release | production | true | true | Android, WebGL, Linux64, LinuxServer | android-release (only if signing secrets exist) |
| workflow_dispatch | manual | `IN_ENVIRONMENT` | `IN_RUN_TESTS` | `IN_BUILD_ADDRESSABLES` | per `IN_PLATFORM` (All ⇒ Android+WebGL+Linux64+LinuxServer; single ⇒ that one; iOS ⇒ build-ios only) | n/a |
| anything else | none | development | false | false | *(none)* | none |

- Branch match: `develop` exact; `staging` exact; `release-*` = ref starts with `release-` or `release/`.
- PR target uses `BASE_REF`; push uses `REF_NAME`.
- iOS is NEVER auto-built (no macOS runner); only manual `platform==iOS`.

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

### Job gating (replaces the inputs.platform checks)
- `unity-tests`  → `if: !cancelled() && needs.validate-project.result=='success' && needs.resolve-config.outputs.run-tests == 'true'`
  with `test-mode: ${{ needs.resolve-config.outputs.test-mode }}`.
- `build-addressables` → `if: !cancelled() && needs.validate-project.result=='success' && needs.resolve-config.outputs.build-addressables == 'true'`.
- `build-<platform>` → `if: !cancelled() && needs.validate-project.result=='success' && (needs.build-addressables.result=='success' || needs.build-addressables.result=='skipped') && needs.resolve-config.outputs.build-<platform> == 'true'`.
- Pass `environment: ${{ needs.resolve-config.outputs.environment }}` to the reusables.

### final-report (always())
Must print: event (`github.event_name`), branch (`github.ref_name`), target branch
(`github.base_ref` or '-'), flow-type, environment, selected platforms, skipped
platforms, blockers (iOS if dispatched without macOS runner), run id, commit.

## Tests
- `tests/test_resolve_build_flow.sh` invocations via pytest (`tests/test_build_flow.py`): assert the 7 scenarios + branch matching (`release-1.2`, `release/1.2`) + non-matching branch ⇒ none.
- Update `tests/test_platform_selection.py` to gate on `needs.resolve-config.outputs.build-<platform>` (mock the resolve-config outputs) instead of `inputs.platform`.
