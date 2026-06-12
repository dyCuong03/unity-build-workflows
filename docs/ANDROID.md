# Android Builds

This document covers Android-specific configuration, signing, and distribution for `unity-build-workflows`.

---

## Runner Requirements

Android builds run on **Ubuntu** runners (GitHub-hosted `ubuntu-latest` or self-hosted).

Required tools on the runner:
- Unity Editor with Android Build Support module
- Android SDK (API level matching `targetSdkVersion`)
- Android NDK (for IL2CPP builds)
- Java 11 or 17 (for `bundletool` if needed)

GitHub-hosted runners include the Android SDK. If using self-hosted runners, install Unity with the Android module and set `ANDROID_SDK_ROOT`.

---

## BuildConfig Fields

See [BUILD_CONFIG.md](BUILD_CONFIG.md#android-object) for the full `android` object reference. Key fields for Android:

| Field | Notes |
|---|---|
| `applicationId` | Must match your Play Console application ID exactly |
| `buildAppBundle` | Set `true` for Play Store, `false` for sideloading/Firebase |
| `architecture` | Use `ARM64` for modern devices; `All` only if needed for x86 emulators |
| `keystoreMode` | `custom` for production signing, `debug` for dev/test |
| `symbolExport` | Enable `public` or `debugging` if using Crashlytics |

---

## Signing

### Debug Signing (development)

When `keystoreMode` is `debug`, Unity uses the Android debug keystore from the SDK. No secrets are required. The resulting APK/AAB is not suitable for Play Store submission.

### Custom Signing (staging and production)

When `keystoreMode` is `custom`, the workflow expects these secrets:

```
ANDROID_KEYSTORE_BASE64      # base64-encoded .jks or .keystore file
ANDROID_KEYSTORE_PASSWORD    # keystore password
ANDROID_KEY_ALIAS            # key alias
ANDROID_KEY_PASSWORD         # key password (may equal keystore password)
```

The workflow decodes the keystore to a temporary file, injects it into Unity's PlayerSettings at build time, and deletes the file after signing. The keystore is never persisted in the workspace or artifact.

### Generating a Keystore

```bash
keytool -genkey -v \
  -keystore my-release-key.keystore \
  -alias my-key-alias \
  -keyalg RSA \
  -keysize 2048 \
  -validity 10000
```

Encode it for use as a GitHub secret:

```bash
base64 -w 0 my-release-key.keystore
```

**Keep the keystore file and passwords secure.** A lost keystore cannot be recovered and prevents Play Store updates.

---

## Build Output

| `buildAppBundle` | Output File | Use Case |
|---|---|---|
| `true` | `*.aab` | Google Play Store |
| `false` | `*.apk` | Sideloading, Firebase App Distribution, direct distribution |

Output is uploaded as a GitHub Actions artifact named `{projectName}-android-{environment}-{buildNumber}`.

---

## Symbol Files

Enable `symbolExport` to upload symbol files to crash reporting services:

- `none` — No symbol files exported (smallest artifact)
- `public` — Exports stripped symbol files (sufficient for Firebase Crashlytics)
- `debugging` — Exports full unstripped symbols (large; use for deep crash analysis)

Symbol archives are uploaded as a separate artifact: `{projectName}-android-symbols-{buildNumber}`.

---

## Minimum SDK Version Guidelines

| `minSdkVersion` | Android Version | Approx. Market Share (2024) |
|---|---|---|
| 22 | Android 5.1 | >99% |
| 24 | Android 7.0 | >98% |
| 26 | Android 8.0 | >96% |

Google Play requires `targetSdkVersion` ≥ 34 for new apps/updates (check Play Console for current requirement).

---

## Addressables with Android

When `addressables.buildRemoteCatalog` is `true`, the remote catalog and bundles are built during the Android build step and must be uploaded to your CDN before the build is distributed. The `postBuild` hook is the appropriate place to trigger the CDN upload:

```json
"hooks": {
  "postBuild": ["upload-addressables-cdn"]
}
```

---

## Local Android Build

Run a local build without CI:

```bash
# From the unity-build-workflows directory
./scripts/build.sh \
  --platform Android \
  --config ci/BuildConfig.development.json \
  --unity-path /Applications/Unity/Hub/Editor/2022.3.45f1/Unity.app/Contents/MacOS/Unity
```

---

## Troubleshooting

**"Keystore was tampered with, or password was incorrect"**
The `ANDROID_KEYSTORE_PASSWORD` secret does not match the keystore. Verify by decoding `ANDROID_KEYSTORE_BASE64` locally and running `keytool -list -v -keystore decoded.keystore`.

**"Gradle build failed: SDK location not found"**
The Android SDK is not installed on the runner or `ANDROID_SDK_ROOT` is not set. For self-hosted runners, set the environment variable in the runner service configuration.

**"IL2CPP build failed: NDK not found"**
Install the NDK via Unity Hub (Add Modules → Android Build Support → Android NDK) or set `ANDROID_NDK_HOME`.

**"minSdkVersion X is lower than NDK's minimum"**
Upgrade `minSdkVersion` to match the NDK minimum (usually 21).
