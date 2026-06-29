# Repository Variables — Configuration Guide

GitHub Repository Variables allow you to customize which platforms are built,
whether tests run, and whether addressables are pre-built — per branch flow —
without editing workflow files.

> **Variables vs Secrets:** Variables are for non-sensitive configuration values
> (platform lists, boolean flags). Secrets are for sensitive values like
> `UNITY_LICENSE`, `UNITY_EMAIL`, `UNITY_PASSWORD`, keystore passwords, and
> Apple signing credentials. Never put secrets in variables.

## How to configure

1. Go to your repository on GitHub
2. Navigate to **Settings → Secrets and variables → Actions → Variables**
3. Click **New repository variable**
4. Enter the variable name and value
5. Click **Add variable**

Variables take effect on the next workflow run — no code changes needed.

## Available variables

### Platform build lists

Control which platforms are built when code is pushed to each branch.
Values are comma-separated platform names (case-sensitive).

| Variable | Default | Applies to |
|---|---|---|
| `DEVELOP_BUILD_PLATFORMS` | `Android,WebGL` | `push → develop` |
| `STAGING_BUILD_PLATFORMS` | `Android,WebGL,Linux64,LinuxServer` | `push → staging` |
| `RELEASE_BUILD_PLATFORMS` | `Android,WebGL,Linux64,LinuxServer` | `push → release-*` |

**Allowed platform names:** `Android`, `WebGL`, `Linux64`, `LinuxServer`, `iOS`

> **iOS note:** iOS in a platform variable is silently ignored for branch flows
> because iOS requires a self-hosted macOS runner. Use `workflow_dispatch` with
> `platform=iOS` for iOS builds.

**Examples:**
```
DEVELOP_BUILD_PLATFORMS=Android,WebGL
STAGING_BUILD_PLATFORMS=Android,WebGL,Linux64,LinuxServer
RELEASE_BUILD_PLATFORMS=Android,WebGL,Linux64,LinuxServer
```

Build only Android on develop:
```
DEVELOP_BUILD_PLATFORMS=Android
```

Build all four platforms on every branch:
```
DEVELOP_BUILD_PLATFORMS=Android,WebGL,Linux64,LinuxServer
STAGING_BUILD_PLATFORMS=Android,WebGL,Linux64,LinuxServer
RELEASE_BUILD_PLATFORMS=Android,WebGL,Linux64,LinuxServer
```

### Test configuration

| Variable | Default | Applies to |
|---|---|---|
| `DEVELOP_RUN_TESTS` | `true` | `push/PR → develop` |
| `STAGING_RUN_TESTS` | `true` | `push/PR → staging` |
| `RELEASE_RUN_TESTS` | `true` | `push/PR → release-*` |

Values must be exactly `true` or `false`. Any other value causes the workflow to fail.

### Addressables configuration

| Variable | Default | Applies to |
|---|---|---|
| `DEVELOP_BUILD_ADDRESSABLES` | `false` | `push/PR → develop` |
| `STAGING_BUILD_ADDRESSABLES` | `false` | `push/PR → staging` |
| `RELEASE_BUILD_ADDRESSABLES` | `true` | `push/PR → release-*` |

Values must be exactly `true` or `false`.

### Runner mode

| Variable | Default |
|---|---|
| `DEFAULT_RUNNER_MODE` | `docker` |

Allowed values: `docker`, `self-hosted-windows`, `auto`.

## Branch flow examples

### PR → develop
- Runs tests (configurable via `DEVELOP_RUN_TESTS`)
- No binary builds (PRs are validation-only)
- Environment: `development`

### push → develop (merge PR into develop)
- Runs tests (configurable via `DEVELOP_RUN_TESTS`)
- Builds platforms from `DEVELOP_BUILD_PLATFORMS` (default: Android, WebGL)
- Environment: `development`

### PR → staging
- Runs tests (configurable via `STAGING_RUN_TESTS`)
- No binary builds
- Environment: `staging`

### push → staging (merge PR into staging)
- Runs tests (configurable via `STAGING_RUN_TESTS`)
- Builds platforms from `STAGING_BUILD_PLATFORMS` (default: Android, WebGL, Linux64, LinuxServer)
- Environment: `staging`

### PR → release-*
- Runs tests (configurable via `RELEASE_RUN_TESTS`)
- Runs addressables build check (configurable via `RELEASE_BUILD_ADDRESSABLES`)
- No binary builds
- Environment: `production`

### push → release-* (merge PR into release branch)
- Runs tests (configurable via `RELEASE_RUN_TESTS`)
- Pre-builds addressables (configurable via `RELEASE_BUILD_ADDRESSABLES`)
- Builds platforms from `RELEASE_BUILD_PLATFORMS` (default: all four)
- Android release signing enabled
- Environment: `production`

### workflow_dispatch (manual)
- **Always uses dispatch inputs — repository variables are ignored**
- User selects platform, environment, test mode, addressables flag
- Only way to trigger iOS builds

## How manual dispatch overrides repo variables

When you trigger a build via **Actions → Run workflow**, the dispatch inputs
(platform, environment, run-tests, etc.) take full precedence. Repository
variables are not consulted for `workflow_dispatch` events. This ensures manual
overrides are always respected.

The `platform-source` output in the final report shows `dispatch` for manual
runs, `variable` when repo variables were used, and `default` when hardcoded
defaults applied.

## Validation

- Platform names are case-sensitive. `android` (lowercase) is invalid and will
  cause the workflow to fail with a clear error message.
- Boolean variables (`*_RUN_TESTS`, `*_BUILD_ADDRESSABLES`) must be exactly
  `true` or `false`. Values like `yes`, `1`, `TRUE` are rejected.
- Whitespace around platform names in CSV values is trimmed automatically.

## Unity Personal / Free license note

- `UNITY_SERIAL` is not required and should not be used.
- `UNITY_LICENSE` is optional — the activation strategy system handles this.
- For Unity Personal/Free users, if Docker activation is blocked, use a
  self-hosted Windows runner as the recommended fallback. Set
  `DEFAULT_RUNNER_MODE=self-hosted-windows` or select `self-hosted-windows`
  in the workflow dispatch `runner-mode` input.
- See [UNITY_PERSONAL_DOCKER_LICENSE.md](UNITY_PERSONAL_DOCKER_LICENSE.md)
  for activation strategy details.

## Secrets (not variables)

These belong in **Settings → Secrets and variables → Actions → Secrets**:

| Secret | Purpose |
|---|---|
| `UNITY_LICENSE` | Unity license file content (`.ulf`) |
| `UNITY_EMAIL` | Unity account email |
| `UNITY_PASSWORD` | Unity account password |
| Keystore secrets | Android signing keystore and passwords |
| Apple signing | iOS distribution certificates and provisioning profiles |

Never put these values in repository variables.
