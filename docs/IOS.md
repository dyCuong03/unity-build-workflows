# iOS Builds

This document covers iOS-specific configuration, code signing, and App Store submission for `unity-build-workflows`.

---

## Runner Requirements

iOS builds **must** run on **macOS** runners. GitHub-hosted `macos-14` (Apple Silicon) or `macos-13` (Intel) runners work. For faster builds, use a self-hosted macOS runner (see [SELF_HOSTED_RUNNER.md](SELF_HOSTED_RUNNER.md)).

Required tools:
- Unity Editor with iOS Build Support module (installs Xcode command line tools dependency)
- Xcode 14.0 or later (installed from App Store or `xcode-select`)
- `fastlane` (optional, used by the sign/upload action)

---

## Build Pipeline Overview

iOS builds follow a two-step process:

```
Unity (headless) → Xcode project  →  xcodebuild  →  IPA  →  (optional) App Store Connect
```

Unity generates a fresh Xcode project on each build (or updates an existing one). The workflow then invokes `xcodebuild archive` and `xcodebuild -exportArchive` to produce the IPA.

---

## BuildConfig Fields

Key `ios` fields (full reference in [BUILD_CONFIG.md](BUILD_CONFIG.md#ios-object)):

| Field | Notes |
|---|---|
| `bundleIdentifier` | Must match the provisioning profile exactly |
| `developmentTeam` | 10-character Team ID from Apple Developer portal |
| `exportMethod` | `app-store` for TestFlight/release; `ad-hoc` for internal distribution |
| `automaticSigning` | `false` recommended in CI; requires matching manual profile |
| `generateXcodeProjectOnly` | Set `true` to skip Xcode build (for manual Xcode testing) |

---

## Code Signing

### Manual Signing (recommended for CI)

Set `automaticSigning: false` and provide these secrets:

```
IOS_CERTIFICATE_BASE64              # .p12 certificate (Distribution or Development)
IOS_CERTIFICATE_PASSWORD            # .p12 password
IOS_PROVISIONING_PROFILE_BASE64     # .mobileprovision file, base64-encoded
```

The workflow installs the certificate into a temporary macOS keychain and copies the provisioning profile to `~/Library/MobileDevice/Provisioning Profiles/`. Both are cleaned up after the build.

### Automatic Signing

Set `automaticSigning: true`. Xcode will manage signing automatically using the `developmentTeam` value. This requires the Apple Developer account to be logged into Xcode on the runner machine — practical only for dedicated self-hosted runners, not GitHub-hosted runners.

---

## Provisioning Profile Types

| `exportMethod` | Certificate Type | Profile Type |
|---|---|---|
| `development` | iOS Development | Development |
| `ad-hoc` | iOS Distribution | Ad Hoc |
| `enterprise` | iOS Distribution (Enterprise) | In-House |
| `app-store` | iOS Distribution | App Store |

Ensure the provisioning profile you encode as `IOS_PROVISIONING_PROFILE_BASE64` matches the `exportMethod` and `bundleIdentifier`.

---

## App Store Connect Upload

When `exportMethod` is `app-store`, the workflow optionally uploads the IPA to App Store Connect using the API key:

```
APPLE_CONNECT_API_KEY_ID
APPLE_CONNECT_API_ISSUER_ID
APPLE_CONNECT_API_KEY_P8_BASE64
```

Upload uses `xcrun altool` or `fastlane deliver` depending on Xcode version. The IPA is submitted to TestFlight automatically after processing.

To disable the upload and only produce the IPA artifact, remove the App Store Connect secrets or set `generateXcodeProjectOnly: true`.

---

## Preparing Signing Artifacts

### Export Certificate as .p12

In Keychain Access on macOS:
1. Select your **Apple Distribution** certificate
2. Right-click → **Export** → choose `.p12` format
3. Set a strong password

Encode for secret storage:
```bash
base64 -i MyDistributionCert.p12 | pbcopy
```

### Export Provisioning Profile

Download from [Apple Developer portal](https://developer.apple.com/account/resources/profiles/list):
```bash
base64 -i MyApp_AppStore.mobileprovision | pbcopy
```

---

## Build Output

The workflow uploads two artifacts:

| Artifact | Contents |
|---|---|
| `{projectName}-ios-{environment}-{buildNumber}` | The `.ipa` file |
| `{projectName}-ios-xcproject-{buildNumber}` | The generated Xcode project (for debugging) |

---

## Bitcode

Unity 2022.1+ no longer generates Bitcode. Bitcode submission to App Store Connect is also deprecated by Apple as of Xcode 14. No special configuration is needed.

---

## dSYM Files

Xcode generates `.dSYM` (debug symbol) files during archive. The `upload-dsyms` post-build hook uploads these to Firebase Crashlytics or your crash reporter. Add it to `hooks.postBuild`:

```json
"hooks": {
  "postBuild": ["upload-dsyms"]
}
```

---

## Local Xcode Project Generation

To inspect the Xcode project locally before CI:

```bash
./scripts/build.sh \
  --platform iOS \
  --config ci/BuildConfig.development.json \
  --unity-path /Applications/Unity/Hub/Editor/2022.3.45f1/Unity.app/Contents/MacOS/Unity
```

Then open `Builds/iOS/Unity-iPhone.xcodeproj` in Xcode.

---

## Troubleshooting

**"No provisioning profiles found for... application identifier"**
The provisioning profile's App ID does not match `bundleIdentifier` in the config. Download a matching profile from the developer portal.

**"Code signing is required for product type 'Application' in SDK 'iOS'"**
`automaticSigning` is `false` but no certificate/profile was provided, or the keychain import failed. Check that all `IOS_*` secrets are set and non-empty.

**"xcode-select: error: tool 'xcodebuild' requires Xcode"**
Xcode is not installed or the active developer directory is pointing to Command Line Tools only. Run: `sudo xcode-select -s /Applications/Xcode.app/Contents/Developer`

**Build hangs during Xcode compilation**
This is typically a metal shader compilation step. It can take 20–40 minutes on first build. Use `cleanBuildCache: false` to benefit from incremental compilation.

**"The certificate used to sign ... is not valid"**
Certificate has expired or been revoked. Renew in Apple Developer portal and update `IOS_CERTIFICATE_BASE64` secret.
