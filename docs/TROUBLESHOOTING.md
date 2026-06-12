# Troubleshooting

Common errors and their fixes for `unity-build-workflows`.

---

## Unity License Issues

### "License activation failed: No serial number provided"

**Cause:** `UNITY_LICENSE` secret is empty or malformed.

**Fix:**
1. On your local machine, activate Unity and locate the `.ulf` file:
   - macOS: `~/Library/Application Support/Unity/Unity_lic.ulf`
   - Windows: `C:\ProgramData\Unity\Unity_lic.ulf`
   - Linux: `~/.local/share/unity3d/Unity/Unity_lic.ulf`
2. Base64-encode without line breaks: `base64 -w 0 Unity_lic.ulf`
3. Paste the output as the `UNITY_LICENSE` secret value.

### "License activation failed: Machine count exceeded"

**Cause:** Unity's concurrent activation limit reached.

**Fix:** Return licenses from unused machines via Unity Hub (Preferences → Licenses → Return), or upgrade to Unity Build Server for CI.

### "License file is not valid for this version"

**Cause:** The `.ulf` was generated for a different Unity version.

**Fix:** Activate Unity with the exact version used in the workflow (`unity-version` input) and export a new `.ulf`.

---

## Schema Validation Errors

### "AJV validation failed: scenes: must NOT have fewer than 1 items"

**Cause:** `scenes` array is empty in the config.

**Fix:** Add at least one scene path to the `scenes` array.

### "AJV validation failed: bundleVersion: must match pattern"

**Cause:** `bundleVersion` is not in `MAJOR.MINOR.PATCH` format.

**Fix:** Change to a valid semver string, e.g. `"1.0.0"` not `"1.0"`.

### "AJV validation failed: android.applicationId: must match pattern"

**Cause:** The application ID is not in reverse-DNS format.

**Fix:** Use format `com.company.game`. Must start with a letter, contain at least two dot-separated segments, no hyphens (Android) or hyphens OK (iOS).

### "developmentBuild must be false for production"

**Cause:** A production-environment config has `developmentBuild: true`.

**Fix:** Set `developmentBuild: false` in `BuildConfig.production.json`.

---

## Android Build Errors

### "Gradle build failed: Could not find keystore file"

**Cause:** `ANDROID_KEYSTORE_BASE64` secret is empty or incorrectly encoded.

**Fix:** Re-encode the keystore: `base64 -w 0 my.keystore` and update the secret.

### "Error: wrong password in keystore"

**Cause:** `ANDROID_KEYSTORE_PASSWORD` does not match the keystore.

**Fix:** Verify the password locally: `keytool -list -keystore my.keystore` and enter the password when prompted.

### "This app bundle targeting API 33 must comply with…"

**Cause:** Google Play's API level requirements have increased.

**Fix:** Increase `android.targetSdkVersion` to 34 or the level currently required by Google Play (check the Play Console for the current deadline).

### "NDK not found" (IL2CPP builds)

**Cause:** The NDK module is not installed for the Unity version on the runner.

**Fix:** Install via Unity Hub (Add Modules → Android Build Support → NDK) or set `ANDROID_NDK_HOME` environment variable on self-hosted runners.

---

## iOS Build Errors

### "No signing certificate 'iOS Distribution' found"

**Cause:** The certificate was not imported into the keychain, or `IOS_CERTIFICATE_BASE64` is empty.

**Fix:**
1. Confirm the secret is set and non-empty.
2. Verify the base64 decodes to a valid .p12: `echo "$IOS_CERTIFICATE_BASE64" | base64 -d > test.p12 && openssl pkcs12 -info -in test.p12 -noout -passin pass:"$IOS_CERTIFICATE_PASSWORD"`

### "The provisioning profile ... doesn't include signing certificate"

**Cause:** The distribution certificate used for signing is not included in the provisioning profile.

**Fix:** Download a new provisioning profile from the Apple Developer portal that includes the current distribution certificate.

### "Xcode build failed: No matching provisioning profiles found for application identifier"

**Cause:** The provisioning profile's App ID does not match `ios.bundleIdentifier` in the config.

**Fix:** Confirm the bundle identifier matches exactly (case-sensitive). Download a provisioning profile for the correct App ID.

### "altool: Error: Unable to upload archive. Failed to get authorization for team"

**Cause:** `APPLE_CONNECT_API_KEY_ID`, `APPLE_CONNECT_API_ISSUER_ID`, or `APPLE_CONNECT_API_KEY_P8_BASE64` is invalid or the key has been revoked.

**Fix:** Generate a new API key in App Store Connect (Users and Access → Keys) and update the secrets.

---

## Unity Build Errors

### "Build failed: 'Assets/...' is not a valid scene path"

**Cause:** A scene listed in `scenes` does not exist at the specified path.

**Fix:** Verify paths are correct relative to the project root (not the Unity project folder), and that they end in `.unity`.

### "Build failed: Scripts have compile errors"

**Cause:** The Unity project has script compilation errors.

**Fix:** This is a code issue, not a CI issue. Pull the branch locally, open the project in Unity, and fix the errors in the Console window. Common causes: missing package references, API changes between Unity versions, conditional compilation errors.

### "Build failed: 'BuildTarget' is not supported on this platform"

**Cause:** The Unity Editor does not have the required platform module installed.

**Fix:** Install the module via Unity Hub (Add Modules for the specific Unity version).

### "Build log shows timeout after 6 hours"

**Cause:** Shader compilation or asset import took too long.

**Fix:**
1. Enable `cleanBuildCache: false` to benefit from incremental builds.
2. Investigate large shader libraries in the project.
3. Consider splitting the build into smaller jobs if the project is genuinely very large.

---

## GitHub Actions Issues

### "Workflow is not triggered by tag push"

**Cause:** The workflow's `on:` trigger doesn't include the tag pattern.

**Fix:** Ensure the consumer workflow includes:
```yaml
on:
  push:
    tags: ['v*']
```

### "Reusable workflow not found"

**Cause:** The `@v1` tag doesn't exist yet in `unity-build-workflows`.

**Fix:** Pin to a specific SHA or the `main` branch while testing: `@main`. Once the first release tag is created, switch to `@v1`.

### "Environment secrets not available to workflow"

**Cause:** The `environment:` key is not set on the job calling the reusable workflow, or the branch doesn't match the environment's deployment branch rule.

**Fix:** Add `environment: production` to the calling job and ensure the branch/tag satisfies the environment's branch restriction.

---

## Quality Gate Failures

### "Build size exceeds maxBuildSizeMB"

**Cause:** Build artifact is larger than the configured limit.

**Fix:**
1. Profile asset sizes using Unity's Build Report tool (Window → Build Report).
2. Compress textures more aggressively.
3. Enable `buildAppBundle: true` for Android to reduce delivery size.
4. If the limit is too strict, increase `maxBuildSizeMB` in the production config.

### "Validation rule 'no_missing_scripts' failed"

**Cause:** One or more GameObjects in the build scenes have missing MonoBehaviour components.

**Fix:** Open each scene in Unity, use the `Edit → Find Missing Scripts` tool (or a custom editor script) to locate and fix broken references.

---

## Still Stuck?

1. Download the full Unity build log artifact from the failed workflow run.
2. Search for `Error` in the log (case-sensitive; Unity uses capital-E).
3. Open an issue at the repository with the relevant log lines, your `BuildConfig` (redact secret values), and the workflow run URL.
