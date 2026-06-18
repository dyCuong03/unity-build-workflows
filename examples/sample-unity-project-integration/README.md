# Sample Unity Project Integration

This example shows the minimal setup required to consume `unity-build-workflows` from a Unity project repository.

## Directory structure

```
your-unity-project/
├── .github/
│   └── workflows/
│       └── unity-ci.yml        # Caller workflow (copy from here)
├── BuildConfig/
│   ├── base.json               # Shared settings for all environments
│   ├── development.json        # Development overrides
│   └── production.json         # Production overrides
└── Assets/                     # Your Unity project assets
```

## Prerequisites

Add the following secrets to your GitHub repository:

| Secret | Required | Description |
|--------|----------|-------------|
| `UNITY_LICENSE` | Yes | Unity license file content (`.ulf`) |
| `UNITY_EMAIL` | No | Unity account email (for activation) |
| `UNITY_PASSWORD` | No | Unity account password (for activation) |
| `ANDROID_KEYSTORE_BASE64` | For Android release | Base64-encoded keystore file |
| `ANDROID_KEYSTORE_PASS` | For Android release | Keystore password |
| `ANDROID_KEY_ALIAS` | For Android release | Key alias |
| `ANDROID_KEY_PASS` | For Android release | Key password |

## Quick start

1. Copy `BuildConfig/` to your project root and edit the JSON files.
2. Copy `.github/workflows/unity-ci.yml` to your project.
3. Replace `unity-version` with your project's Unity version.
4. Push — the workflow runs automatically.

## Environment merging

The pipeline merges `base.json` with the selected environment config at runtime. Environment-specific values take precedence over base values.

```
final_config = deep_merge(base.json, <environment>.json)
```

## Upgrading

Pin a specific release tag to control upgrades:

```yaml
uses: OWNER/unity-build-workflows/.github/workflows/unity-build.yml@v1.2.0
```
