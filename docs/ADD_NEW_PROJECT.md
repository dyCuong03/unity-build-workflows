# Adding a New Project

This guide walks through integrating a new Unity project with `unity-build-workflows` from scratch.

---

## Prerequisites

- GitHub repository for your Unity project
- Unity project using Unity 2021.3 LTS or later
- GitHub Actions enabled on your repository
- Access to the `BuzzelStudio/unity-build-workflows` repository (public or granted)

---

## Step 1: Set Up GitHub Secrets

Navigate to your repository's **Settings → Secrets and variables → Actions** and add the following secrets. See [templates/build-secrets.example.md](../templates/build-secrets.example.md) for the full list with descriptions.

**Minimum required secrets:**

```
UNITY_LICENSE        # base64-encoded .ulf file
```

**For Android production builds, also add:**
```
ANDROID_KEYSTORE_BASE64
ANDROID_KEYSTORE_PASSWORD
ANDROID_KEY_ALIAS
ANDROID_KEY_PASSWORD
```

**For iOS builds, also add:**
```
IOS_CERTIFICATE_BASE64
IOS_CERTIFICATE_PASSWORD
IOS_PROVISIONING_PROFILE_BASE64
APPLE_CONNECT_API_KEY_ID
APPLE_CONNECT_API_ISSUER_ID
APPLE_CONNECT_API_KEY_P8_BASE64
```

---

## Step 2: Create Your BuildConfig Files

Create a `ci/` directory in your repository root:

```bash
mkdir -p ci
```

Copy and adapt the example templates:

```bash
cp path/to/unity-build-workflows/templates/BuildConfig.base.example.json ci/BuildConfig.base.json
cp path/to/unity-build-workflows/templates/BuildConfig.development.example.json ci/BuildConfig.development.json
cp path/to/unity-build-workflows/templates/BuildConfig.staging.example.json ci/BuildConfig.staging.json
cp path/to/unity-build-workflows/templates/BuildConfig.production.example.json ci/BuildConfig.production.json
```

At minimum, edit `ci/BuildConfig.base.json` and change:

| Field | Change To |
|---|---|
| `projectName` | Your project identifier |
| `companyName` | Your company name |
| `productName` | Display name of your game |
| `android.applicationId` | Your Android package name |
| `ios.bundleIdentifier` | Your iOS bundle ID |
| `ios.developmentTeam` | Your Apple Developer Team ID |
| `scenes` | Paths to your scenes in the correct load order |

---

## Step 3: Create Your GitHub Actions Workflow

Create `.github/workflows/build.yml` in your project repository:

```yaml
name: Build

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]
  workflow_dispatch:
    inputs:
      environment:
        description: 'Build environment'
        required: true
        default: 'development'
        type: choice
        options: [development, staging, production]

jobs:
  determine-env:
    runs-on: ubuntu-latest
    outputs:
      environment: ${{ steps.env.outputs.environment }}
      build-config: ${{ steps.merge.outputs.config }}
    steps:
      - uses: actions/checkout@v4

      - name: Determine environment
        id: env
        run: |
          if [[ "${{ github.event_name }}" == "workflow_dispatch" ]]; then
            echo "environment=${{ inputs.environment }}" >> $GITHUB_OUTPUT
          elif [[ "${{ github.ref }}" == "refs/heads/main" ]]; then
            echo "environment=staging" >> $GITHUB_OUTPUT
          else
            echo "environment=development" >> $GITHUB_OUTPUT
          fi

      - name: Merge build configs
        id: merge
        run: |
          BASE=$(cat ci/BuildConfig.base.json)
          ENV_CONFIG=$(cat ci/BuildConfig.${{ steps.env.outputs.environment }}.json)
          MERGED=$(echo "$BASE $ENV_CONFIG" | jq -s '.[0] * .[1]')
          echo "config=$MERGED" >> $GITHUB_OUTPUT

  build-android:
    needs: determine-env
    uses: BuzzelStudio/unity-build-workflows/.github/workflows/android.yml@v1
    with:
      build-config: ${{ needs.determine-env.outputs.build-config }}
      unity-version: '2022.3.45f1'
      environment: ${{ needs.determine-env.outputs.environment }}
    secrets: inherit

  build-ios:
    needs: determine-env
    uses: BuzzelStudio/unity-build-workflows/.github/workflows/ios.yml@v1
    with:
      build-config: ${{ needs.determine-env.outputs.build-config }}
      unity-version: '2022.3.45f1'
      environment: ${{ needs.determine-env.outputs.environment }}
    secrets: inherit

  build-windows:
    needs: determine-env
    uses: BuzzelStudio/unity-build-workflows/.github/workflows/windows.yml@v1
    with:
      build-config: ${{ needs.determine-env.outputs.build-config }}
      unity-version: '2022.3.45f1'
      environment: ${{ needs.determine-env.outputs.environment }}
    secrets: inherit
```

---

## Step 4: Configure GitHub Environments

For staging and production builds, create GitHub Environments:

1. Go to **Settings → Environments → New environment**
2. Create `staging` environment:
   - Add deployment branch rule: `main`
3. Create `production` environment:
   - Add required reviewers (at least one person)
   - Add deployment branch rule: tags matching `v*`
   - Move production secrets to this environment scope

---

## Step 5: Test a Development Build

Push to a feature branch or trigger manually:

```bash
git push origin feature/ci-setup
```

Or use the GitHub UI: **Actions → Build → Run workflow → development**.

Verify:
- [ ] Schema validation passes
- [ ] Unity license activates successfully
- [ ] Build completes without errors
- [ ] Artifact is uploaded and downloadable
- [ ] Any configured hooks run in the correct order

---

## Step 6: Configure Self-Hosted Runners (Optional)

If you need macOS runners for iOS builds or want faster build times with larger machines, see [SELF_HOSTED_RUNNER.md](SELF_HOSTED_RUNNER.md) for setup instructions.

---

## Step 7: Configure Notifications (Optional)

Add a `SLACK_WEBHOOK_URL` secret and update your `hooks.postBuild` in the relevant BuildConfig files:

```json
"hooks": {
  "postBuild": ["notify-slack"]
}
```

Create `scripts/hooks/notify-slack.sh` in your project repository with your notification logic.

---

## Troubleshooting First-Time Setup

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for common first-time setup errors.

Common issues:

- **"Unity license activation failed"** — Check that `UNITY_LICENSE` contains the full `.ulf` file content, base64-encoded without line breaks.
- **"Schema validation failed"** — Run `npx ajv-cli validate -s schemas/unity-build-config.schema.json -d ci/BuildConfig.base.json` locally to see the exact field causing the error.
- **"No scenes found"** — Verify scene paths in your config match the actual file paths under `Assets/` and end with `.unity`.
