# Repository Variables — Configuration Guide

GitHub Repository Variables let you customize Unity version/build settings,
which platforms are built, whether tests run, addressables pre-building,
runner selection, caching, and artifact retention — per branch flow — without
editing workflow files. Variables are grouped by concern (`UNITY_*`,
`BUILD_*`, `TEST_*`, `ADDRESSABLES_*`, `RUNNER_*`, `CACHE_*`, `ARTIFACT_*`).

> **Variables vs Secrets:** Variables are for non-sensitive configuration
> (platform lists, versions, boolean flags). Secrets are for sensitive values
> like `UNITY_LICENSE`, `UNITY_EMAIL`, `UNITY_PASSWORD`, keystore passwords,
> and Apple signing credentials. Config is always resolved server-side inside
> the workflow — never put secrets in variables. See
> [BRANCH_FLOW_CONTRACT.md](BRANCH_FLOW_CONTRACT.md) for how the resolver
> consumes these variables and what it outputs to downstream jobs.

## How to configure

1. Go to your repository on GitHub
2. Navigate to **Settings → Secrets and variables → Actions → Variables**
3. Click **New repository variable**
4. Enter the variable name and value
5. Click **Add variable**

Variables take effect on the next workflow run — no code changes needed.

## Configuration priority

Every setting is resolved by `scripts/common/resolve_build_flow.sh` using the
same layered priority, highest first:

1. **`workflow_dispatch` input** — an explicit value chosen when manually
   running the workflow (e.g. the `clean-build` dispatch input). Only present
   for manual runs; skipped entirely for `push`/`pull_request` events.
2. **New repo variable** — the grouped variable documented below (e.g.
   `BUILD_DEVELOP_PLATFORMS`), if set to a non-empty value.
3. **Legacy repo variable** — the old, ungrouped variable name (e.g.
   `DEVELOP_BUILD_PLATFORMS`), if set to a non-empty value. Used only when the
   new variable is unset, so existing repos keep working unchanged. The
   resolver logs a deprecation note naming the new variable to migrate to.
4. **`ProjectVersion.txt`** — Unity-version only. If `UNITY_VERSION` isn't set
   by any variable, the resolver reads the version from the project's
   `ProjectVersion.txt`.
5. **Toolkit default** — the hardcoded fallback baked into the resolver,
   documented in the "Default" column of each table below.

For `push`/`pull_request` events (no dispatch layer), priority is simply
**New variable → Legacy variable → (ProjectVersion.txt for Unity version) →
Toolkit default**. The resolver never *requires* a new variable to be set —
an unconfigured repo behaves exactly as it did before this refactor.

## UNITY

| Variable | Default | Applies to | Notes |
|---|---|---|---|
| `UNITY_VERSION` | `ProjectVersion.txt` → toolkit default | all flows | Detected version is printed in the Resolve Config report. Never hard-fails when unset. |
| `UNITY_PROJECT_PATH` | `.` | all flows | Path to the Unity project root, relative to repo root. |
| `UNITY_BUILD_METHOD` | *(empty = game-ci default)* | all flows | Override the Unity build method invoked by game-ci. |
| `UNITY_DEVELOP_DEFINE_SYMBOLS` | *(empty)* | `push/PR → develop` | Legacy: `DEVELOP_DEFINE_SYMBOLS`. |
| `UNITY_STAGING_DEFINE_SYMBOLS` | *(empty)* | `push/PR → staging` | Legacy: `STAGING_DEFINE_SYMBOLS`. |
| `UNITY_RELEASE_DEFINE_SYMBOLS` | *(empty)* | `push/PR → release-*` | Legacy: `RELEASE_DEFINE_SYMBOLS`. |

Define-symbols variables are **additive** — the listed symbols are merged
into every platform group at build time; existing project symbols (e.g.
`ODIN_INSPECTOR`, `DOTWEEN`) are preserved and duplicates de-duplicated.
Format: `';'` or `','` separated (whitespace trimmed), e.g.
`STAGING;PROFILER_ENABLED`. Manual `workflow_dispatch` runs ignore these
variables (they are branch-scoped) — pass the `define-symbols` dispatch input
instead.

```
UNITY_VERSION=2022.3.45f1
UNITY_PROJECT_PATH=.
UNITY_DEVELOP_DEFINE_SYMBOLS=DEVELOPMENT_BUILD;VERBOSE_LOGGING
UNITY_STAGING_DEFINE_SYMBOLS=STAGING;PROFILER_ENABLED
UNITY_RELEASE_DEFINE_SYMBOLS=PRODUCTION;LIVE_BACKEND
```

## BUILD

| Variable | Default | Applies to | Notes |
|---|---|---|---|
| `BUILD_DEVELOP_PLATFORMS` | `Android,WebGL` | `push → develop` | Legacy: `DEVELOP_BUILD_PLATFORMS`. |
| `BUILD_STAGING_PLATFORMS` | `Android,WebGL,Linux64,LinuxServer,Windows64` | `push → staging` | Legacy: `STAGING_BUILD_PLATFORMS`. |
| `BUILD_RELEASE_PLATFORMS` | `Android,WebGL,Linux64,LinuxServer,Windows64` | `push → release-*` | Legacy: `RELEASE_BUILD_PLATFORMS`. |
| `BUILD_TIMEOUT_MINUTES` | `120` | all build jobs | Positive integer; per-job timeout in minutes. |
| `BUILD_CLEAN` | `false` | all build jobs | See [BUILD_CLEAN](#build_clean-clean-vs-incremental-builds) below. |

Platform lists are comma-separated and case-sensitive. **Allowed platform
names:** `Android`, `WebGL`, `Linux64`, `LinuxServer`, `Windows64`, `iOS`.

> **iOS note:** iOS in a platform variable is silently ignored for branch
> flows because iOS requires a self-hosted macOS runner. Use
> `workflow_dispatch` with `platform=iOS` for iOS builds — see
> [Known limitations](#known-limitations).

```
BUILD_DEVELOP_PLATFORMS=Android,WebGL
BUILD_STAGING_PLATFORMS=Android,WebGL,Linux64,LinuxServer,Windows64
BUILD_RELEASE_PLATFORMS=Android,WebGL,Linux64,LinuxServer,Windows64
BUILD_TIMEOUT_MINUTES=120
BUILD_CLEAN=false
```

### BUILD_CLEAN: clean vs incremental builds

- **`true` (clean):** forces a clean build — no stale artifacts carried over.
  The Library cache is cleared only when the selected runner mode requires it
  to guarantee a clean state. Use this when you need certainty over speed.
- **`false` (incremental, default):** reuses the Library/Gradle/NuGet caches
  from the previous run for faster builds.

Manual runs can override the variable with the `Clean Build` `workflow_dispatch`
input, which accepts `auto | true | false`:

- `auto` — use the `BUILD_CLEAN` variable (or its default if unset).
- `true` / `false` — force the value for this run only, ignoring the variable.

Priority: **`workflow_dispatch` input → `BUILD_CLEAN` variable → default
(`false`)**. The resolver emits both `clean-build` (`true`/`false`) and
`clean-build-source` (`workflow_dispatch` | `variable` | `default`).

**Recommended defaults:** leave `develop`, `staging`, and `release` all
incremental (`false`). Only force `true` (via the variable or the dispatch
input) when:

- the Library cache is suspected corrupted,
- stale build outputs are suspected,
- you just upgraded the Unity version,
- you changed scripting backend (Mono/IL2CPP) or a build pipeline setting, or
- you're debugging CI caching behavior.

**Performance impact:** clean builds skip the Library/Gradle/Addressables
caches and re-import/re-compile everything, which is significantly slower
(often several times longer) than an incremental build. Reserve `true` for
the cases above rather than as a default.

## TEST

| Variable | Default | Applies to | Notes |
|---|---|---|---|
| `TEST_DEVELOP_ENABLED` | `true` | `push/PR → develop` | Legacy: `DEVELOP_RUN_TESTS`. |
| `TEST_STAGING_ENABLED` | `true` | `push/PR → staging` | Legacy: `STAGING_RUN_TESTS`. |
| `TEST_RELEASE_ENABLED` | `true` | `push/PR → release-*` | Legacy: `RELEASE_RUN_TESTS`. |
| `TEST_EDITMODE_ENABLED` | `true` | all test runs | Toggles EditMode suite. |
| `TEST_PLAYMODE_ENABLED` | `true` | all test runs | Toggles PlayMode suite. |
| `TEST_FAIL_FAST` | `false` | all test runs | Stop on first failure instead of running the full suite. |

Values must be exactly `true` or `false`; anything else fails the workflow.

`test-mode` is derived from the EditMode/PlayMode toggles: both enabled →
`All`, EditMode only → `EditMode`, PlayMode only → `PlayMode`, neither →
`None`. If the branch's `TEST_*_ENABLED` resolves to `false`, `test-mode` is
forced to `None` regardless of the EditMode/PlayMode toggles.

```
TEST_DEVELOP_ENABLED=true
TEST_STAGING_ENABLED=true
TEST_RELEASE_ENABLED=true
TEST_EDITMODE_ENABLED=true
TEST_PLAYMODE_ENABLED=true
TEST_FAIL_FAST=false
```

## ADDRESSABLES

| Variable | Default | Applies to | Notes |
|---|---|---|---|
| `ADDRESSABLES_DEVELOP_ENABLED` | `false` | `push/PR → develop` | Legacy: `DEVELOP_BUILD_ADDRESSABLES`. |
| `ADDRESSABLES_STAGING_ENABLED` | `false` | `push/PR → staging` | Legacy: `STAGING_BUILD_ADDRESSABLES`. |
| `ADDRESSABLES_RELEASE_ENABLED` | `true` | `push/PR → release-*` | Legacy: `RELEASE_BUILD_ADDRESSABLES`. |

Values must be exactly `true` or `false`. Resolver output: `build-addressables`.

```
ADDRESSABLES_DEVELOP_ENABLED=false
ADDRESSABLES_STAGING_ENABLED=false
ADDRESSABLES_RELEASE_ENABLED=true
```

## RUNNER

| Variable | Default | Applies to | Notes |
|---|---|---|---|
| `RUNNER_DEFAULT_MODE` | `docker` | all flows | Legacy: `DEFAULT_RUNNER_MODE`. Allowed: `docker`, `self-hosted-windows`, `self-hosted-macos`, `auto`. |
| `RUNNER_WINDOWS_LABEL` | `self-hosted-windows` | self-hosted Windows builds | GitHub Actions runner label to target. |
| `RUNNER_MACOS_LABEL` | `self-hosted-macos` | self-hosted macOS builds | GitHub Actions runner label to target. |
| `RUNNER_LINUX_LABEL` | `ubuntu-latest` | docker/Linux builds | GitHub Actions runner label to target. |

```
RUNNER_DEFAULT_MODE=docker
RUNNER_WINDOWS_LABEL=self-hosted-windows
RUNNER_MACOS_LABEL=self-hosted-macos
RUNNER_LINUX_LABEL=ubuntu-latest
```

## CACHE

All cache toggles default to `true`. Disable a cache only to debug a cache
corruption issue or to force a fully cold run.

| Variable | Default | Notes |
|---|---|---|
| `CACHE_LIBRARY_ENABLED` | `true` | Caches Unity's `Library/` folder between runs. |
| `CACHE_GRADLE_ENABLED` | `true` | Caches Gradle dependencies for Android builds. |
| `CACHE_ADDRESSABLES_ENABLED` | `true` | Caches built Addressables content. |
| `CACHE_NUGET_ENABLED` | `true` | Caches NuGet packages. |

```
CACHE_LIBRARY_ENABLED=true
CACHE_GRADLE_ENABLED=true
CACHE_ADDRESSABLES_ENABLED=true
CACHE_NUGET_ENABLED=true
```

## ARTIFACT

| Variable | Default | Notes |
|---|---|---|
| `ARTIFACT_RETENTION_DAYS` | `30` | Positive integer; days GitHub Actions retains build artifacts. |
| `ARTIFACT_COMPRESSION` | `zip` | See [Known limitations](#known-limitations) — only `zip` is supported today. |

```
ARTIFACT_RETENTION_DAYS=30
ARTIFACT_COMPRESSION=zip
```

## Migration guide: legacy → new variables

Legacy (ungrouped) variables **still work** — they are read whenever the
corresponding new variable is unset, so no existing consumer needs to change
anything. New variables take priority when both are set. Migrate at your own
pace; the resolver logs a deprecation note pointing at the new name whenever
it falls back to a legacy variable.

| Legacy variable | New variable |
|---|---|
| `DEVELOP_BUILD_PLATFORMS` | `BUILD_DEVELOP_PLATFORMS` |
| `STAGING_BUILD_PLATFORMS` | `BUILD_STAGING_PLATFORMS` |
| `RELEASE_BUILD_PLATFORMS` | `BUILD_RELEASE_PLATFORMS` |
| `DEVELOP_RUN_TESTS` | `TEST_DEVELOP_ENABLED` |
| `STAGING_RUN_TESTS` | `TEST_STAGING_ENABLED` |
| `RELEASE_RUN_TESTS` | `TEST_RELEASE_ENABLED` |
| `DEVELOP_BUILD_ADDRESSABLES` | `ADDRESSABLES_DEVELOP_ENABLED` |
| `STAGING_BUILD_ADDRESSABLES` | `ADDRESSABLES_STAGING_ENABLED` |
| `RELEASE_BUILD_ADDRESSABLES` | `ADDRESSABLES_RELEASE_ENABLED` |
| `DEFAULT_RUNNER_MODE` | `RUNNER_DEFAULT_MODE` |
| `DEVELOP_DEFINE_SYMBOLS` | `UNITY_DEVELOP_DEFINE_SYMBOLS` |
| `STAGING_DEFINE_SYMBOLS` | `UNITY_STAGING_DEFINE_SYMBOLS` |
| `RELEASE_DEFINE_SYMBOLS` | `UNITY_RELEASE_DEFINE_SYMBOLS` |

Everything in the BUILD_CLEAN, RUNNER label, CACHE, and ARTIFACT groups is
new — there is no legacy equivalent, so those simply default until you set
them.

## GitHub configuration examples

**Settings → Secrets and variables → Actions → Variables:**

```
# UNITY
UNITY_VERSION=2022.3.45f1
UNITY_PROJECT_PATH=.

# BUILD
BUILD_DEVELOP_PLATFORMS=Android,WebGL
BUILD_STAGING_PLATFORMS=Android,WebGL,Linux64,LinuxServer,Windows64
BUILD_RELEASE_PLATFORMS=Android,WebGL,Linux64,LinuxServer,Windows64
BUILD_TIMEOUT_MINUTES=120
BUILD_CLEAN=false

# TEST
TEST_DEVELOP_ENABLED=true
TEST_STAGING_ENABLED=true
TEST_RELEASE_ENABLED=true
TEST_EDITMODE_ENABLED=true
TEST_PLAYMODE_ENABLED=true
TEST_FAIL_FAST=false

# ADDRESSABLES
ADDRESSABLES_DEVELOP_ENABLED=false
ADDRESSABLES_STAGING_ENABLED=false
ADDRESSABLES_RELEASE_ENABLED=true

# RUNNER
RUNNER_DEFAULT_MODE=docker
RUNNER_WINDOWS_LABEL=self-hosted-windows
RUNNER_MACOS_LABEL=self-hosted-macos
RUNNER_LINUX_LABEL=ubuntu-latest

# CACHE
CACHE_LIBRARY_ENABLED=true
CACHE_GRADLE_ENABLED=true
CACHE_ADDRESSABLES_ENABLED=true
CACHE_NUGET_ENABLED=true

# ARTIFACT
ARTIFACT_RETENTION_DAYS=30
ARTIFACT_COMPRESSION=zip
```

**Settings → Secrets and variables → Actions → Secrets** (never variables):

| Secret | Purpose |
|---|---|
| `UNITY_LICENSE` | Unity license file content (`.ulf`) |
| `UNITY_EMAIL` | Unity account email |
| `UNITY_PASSWORD` | Unity account password |
| Keystore secrets | Android signing keystore and passwords |
| Apple signing | iOS distribution certificates and provisioning profiles |

## Best practices

### Unity Personal license

- `UNITY_SERIAL` is not required and should not be used.
- `UNITY_LICENSE` is optional — the activation strategy system handles this.
- If Docker activation is blocked for a Personal/Free license, fall back to a
  self-hosted Windows runner: set `RUNNER_DEFAULT_MODE=self-hosted-windows`,
  or select `self-hosted-windows` in the `workflow_dispatch` `runner-mode`
  input. See
  [UNITY_PERSONAL_DOCKER_LICENSE.md](UNITY_PERSONAL_DOCKER_LICENSE.md).

### Docker lane

- Keep `RUNNER_DEFAULT_MODE=docker` for the default CI path — it's the only
  runner mode CI itself verifies end-to-end.
- `CACHE_LIBRARY_ENABLED` / `CACHE_GRADLE_ENABLED` matter most here since
  Docker jobs run on ephemeral GitHub-hosted runners with no persistent disk
  between separate machines.
- Leave `BUILD_CLEAN=false` in Docker unless you're troubleshooting — clean
  builds are considerably more expensive on shared runners.

### Self-hosted Windows runner

- Set `RUNNER_DEFAULT_MODE=self-hosted-windows` and confirm
  `RUNNER_WINDOWS_LABEL` matches the label of your provisioned runner(s).
- Required for IL2CPP Windows64 builds (the Docker lane only supports Mono
  scripting backend for Windows64).
- See
  [SELF_HOSTED_WINDOWS_RUNNER.md](SELF_HOSTED_WINDOWS_RUNNER.md) for
  provisioning steps.

## Known limitations

- **`ARTIFACT_COMPRESSION`** only supports `zip` today (maps directly to
  `actions/upload-artifact`'s zip packaging). Other formats are not
  implemented; setting anything else fails validation.
- **Self-hosted runner modes** (`self-hosted-windows`, `self-hosted-macos`)
  require you to provision and register the runner(s) yourself. CI for this
  toolkit only verifies the `docker` / `ubuntu-latest` lane end-to-end.
- **iOS is manual-dispatch only** — iOS in any `BUILD_*_PLATFORMS` variable
  is silently ignored for automatic branch flows; there is no automatic path
  to a macOS runner. Trigger iOS via `workflow_dispatch` with `platform=iOS`.
- **`RUNNER_*_LABEL` customization** for self-hosted runners is best-effort:
  the toolkit passes the label through to the job's `runs-on`, but it cannot
  validate that a runner with that label is actually online or configured
  correctly.

## Validation summary

- Platform names: case-sensitive, one of `Android`, `WebGL`, `Linux64`,
  `LinuxServer`, `Windows64`, `iOS`.
- Runner mode: one of `docker`, `self-hosted-windows`, `self-hosted-macos`,
  `auto`.
- Booleans (`*_ENABLED`, `TEST_FAIL_FAST`, `BUILD_CLEAN` when not `auto`):
  exactly `true` or `false`.
- `BUILD_TIMEOUT_MINUTES` / `ARTIFACT_RETENTION_DAYS`: positive integers.
- `ARTIFACT_COMPRESSION`: `zip` only.
- Invalid values fail the workflow fast with a clear error message; whitespace
  around CSV platform entries is trimmed automatically.

See [BRANCH_FLOW_CONTRACT.md](BRANCH_FLOW_CONTRACT.md) for the full resolver
input/output contract and per-flow behavior.
