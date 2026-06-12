# unity-build-workflows

Reusable GitHub Actions workflows for building, testing, signing, and releasing Unity games across Android, iOS, Windows, and WebGL platforms.

---

## What This Repository Is

`unity-build-workflows` is a CI/CD platform library, not an application. Unity game repositories call its reusable workflows instead of maintaining their own build pipeline code. This means:

- **One place to update** — bug fixes and improvements to the build pipeline benefit all projects immediately (or on their next version pin update).
- **Consistent artifact naming, quality gates, and release flows** across all projects in your organization.
- **Secrets stay in the consumer repository** — this repository never has access to your signing keys or Unity license.

---

## Architecture

```
Your Game Repo
  .github/workflows/build.yml
       │ uses: BuzzelStudio/unity-build-workflows/.github/workflows/android.yml@v1
       │       (+ ios.yml, windows.yml, webgl.yml)
       │ secrets: inherit
       ▼
unity-build-workflows
  .github/workflows/    ← Reusable workflow definitions (one per platform)
  actions/              ← Composite actions (setup, build, sign, gate, upload)
  scripts/              ← Shell scripts invoked by actions
  schemas/              ← JSON Schema for BuildConfig validation
  templates/            ← Example BuildConfig files
  docs/                 ← This documentation
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the complete layer diagram and extension points.

---

## Supported Platforms

| Platform | Runner OS | Scripting Backend | Notes |
|---|---|---|---|
| Android | Ubuntu | Mono or IL2CPP | AAB and APK; debug or custom keystore signing |
| iOS | macOS | IL2CPP (required) | Xcode project generation + archive + IPA export |
| Windows Standalone | Windows | Mono or IL2CPP | x86_64 or x86; optional installer hook |
| WebGL | Ubuntu | IL2CPP | Brotli/Gzip/Disabled compression; optional PWA template |

---

## Minimal Integration

### 1. Copy a BuildConfig template

```bash
mkdir ci
cp templates/BuildConfig.base.example.json ci/BuildConfig.base.json
# Edit projectName, applicationId, bundleIdentifier, scenes, etc.
```

### 2. Add secrets to your repository

At minimum: `UNITY_LICENSE`. See [templates/build-secrets.example.md](templates/build-secrets.example.md).

### 3. Create `.github/workflows/build.yml`

```yaml
name: Build

on:
  push:
    branches: [main, develop]
  push:
    tags: ['v*']

jobs:
  config:
    runs-on: ubuntu-latest
    outputs:
      build-config: ${{ steps.merge.outputs.config }}
      environment: ${{ steps.env.outputs.environment }}
    steps:
      - uses: actions/checkout@v4
      - name: Determine environment
        id: env
        run: |
          if [[ "$GITHUB_REF" == refs/tags/v* ]]; then
            echo "environment=production" >> $GITHUB_OUTPUT
          elif [[ "$GITHUB_REF" == "refs/heads/main" ]]; then
            echo "environment=staging" >> $GITHUB_OUTPUT
          else
            echo "environment=development" >> $GITHUB_OUTPUT
          fi
      - name: Merge configs
        id: merge
        run: |
          ENV="${{ steps.env.outputs.environment }}"
          CONFIG=$(jq -s '.[0] * .[1]' ci/BuildConfig.base.json ci/BuildConfig.${ENV}.json)
          echo "config=$CONFIG" >> $GITHUB_OUTPUT

  build-android:
    needs: config
    uses: BuzzelStudio/unity-build-workflows/.github/workflows/android.yml@v1
    with:
      build-config: ${{ needs.config.outputs.build-config }}
      unity-version: '2022.3.45f1'
      environment: ${{ needs.config.outputs.environment }}
    secrets: inherit
```

That's it. See [docs/ADD_NEW_PROJECT.md](docs/ADD_NEW_PROJECT.md) for the full onboarding walkthrough.

---

## Common Workflows

### Build all platforms on push to main

```yaml
build-android:
  needs: config
  uses: BuzzelStudio/unity-build-workflows/.github/workflows/android.yml@v1
  with: { build-config: ${{ needs.config.outputs.build-config }}, unity-version: '2022.3.45f1', environment: staging }
  secrets: inherit

build-ios:
  needs: config
  uses: BuzzelStudio/unity-build-workflows/.github/workflows/ios.yml@v1
  with: { build-config: ${{ needs.config.outputs.build-config }}, unity-version: '2022.3.45f1', environment: staging }
  secrets: inherit
```

### Run tests only (no build)

```yaml
test:
  uses: BuzzelStudio/unity-build-workflows/.github/workflows/test.yml@v1
  with:
    build-config: ${{ needs.config.outputs.build-config }}
    unity-version: '2022.3.45f1'
  secrets: inherit
```

### Release to production via tag

```bash
git tag v1.2.3 -m "Release 1.2.3"
git push origin v1.2.3
```

See [docs/RELEASE_FLOW.md](docs/RELEASE_FLOW.md) for the complete release process.

---

## Local Build Command

To test builds locally without CI:

```bash
# Linux/macOS
./scripts/build.sh \
  --platform Android \
  --config ci/BuildConfig.development.json \
  --unity-path "/Applications/Unity/Hub/Editor/2022.3.45f1/Unity.app/Contents/MacOS/Unity"

# Windows (PowerShell)
.\scripts\build.ps1 `
  -Platform Windows `
  -Config .\ci\BuildConfig.development.json `
  -UnityPath "C:\Program Files\Unity\Hub\Editor\2022.3.45f1\Editor\Unity.exe"
```

---

## Versioning Policy

This repository uses semantic versioning. Consumer repositories reference a major version tag:

```yaml
uses: BuzzelStudio/unity-build-workflows/.github/workflows/android.yml@v1
```

- `@v1` always points to the latest `1.x.x` release — minor and patch updates are applied automatically.
- Major version increments (v2, v3...) indicate breaking changes to the workflow input interface.
- To pin to an exact version for reproducibility: `@v1.2.3`.

Current version: **1.0.0** — see [CHANGELOG.md](CHANGELOG.md).

---

## Documentation

| Document | Contents |
|---|---|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Layer diagram, extension points, error handling |
| [docs/ADD_NEW_PROJECT.md](docs/ADD_NEW_PROJECT.md) | Step-by-step onboarding guide |
| [docs/BUILD_CONFIG.md](docs/BUILD_CONFIG.md) | Every BuildConfig field documented |
| [docs/ANDROID.md](docs/ANDROID.md) | Android signing, AAB, symbol export |
| [docs/IOS.md](docs/IOS.md) | iOS code signing, Xcode, App Store Connect |
| [docs/WINDOWS.md](docs/WINDOWS.md) | Windows standalone, IL2CPP, code signing |
| [docs/WEBGL.md](docs/WEBGL.md) | WebGL compression, hosting, memory configuration |
| [docs/RELEASE_FLOW.md](docs/RELEASE_FLOW.md) | Tag-based release, environments, gates |
| [docs/SELF_HOSTED_RUNNER.md](docs/SELF_HOSTED_RUNNER.md) | Setting up and securing self-hosted runners |
| [docs/SECURITY.md](docs/SECURITY.md) | Secret handling, fork safety, threat model |
| [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) | Common errors and fixes |

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE) — © 2024 BuzzelStudio
