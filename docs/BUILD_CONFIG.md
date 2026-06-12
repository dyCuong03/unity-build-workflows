# BuildConfig Reference

Full reference for every field in the `BuildConfig` JSON schema. Validate your config against `schemas/unity-build-config.schema.json`.

---

## Root Fields

### `projectName`
- **Type:** string (1–64 chars)
- **Required:** Yes
- Used in artifact names, Slack notifications, and workflow job names. Should be a stable identifier (no spaces recommended, use dashes or underscores).

### `companyName`
- **Type:** string (1–64 chars)
- **Required:** Yes
- Maps to `PlayerSettings.companyName` in Unity.

### `productName`
- **Type:** string (1–64 chars)
- **Required:** Yes
- Maps to `PlayerSettings.productName`. Shown as the app name on-device.

### `bundleVersion`
- **Type:** string matching `MAJOR.MINOR.PATCH`
- **Required:** Yes
- Player-facing version string. Maps to `PlayerSettings.bundleVersion`.

### `buildNumberStrategy`
- **Type:** enum: `github_run_number` | `timestamp` | `manual`
- **Default:** `github_run_number`
- Controls how the internal build number (not the version) is derived:
  - `github_run_number` — uses `$GITHUB_RUN_NUMBER` (monotonically increasing)
  - `timestamp` — uses `YYYYMMDDHHmm` format
  - `manual` — reads `BUILD_NUMBER` environment variable (you must set it)

### `outputDirectory`
- **Type:** string
- **Required:** Yes
- Relative path inside the Unity project workspace where build output is written. Example: `"Builds"`.

### `scenes`
- **Type:** array of strings (minimum 1 item)
- **Required:** Yes
- Ordered list of scene paths (relative to the project root) included in the build. Paths must start with `Assets/` and end with `.unity`.
- Example: `["Assets/Scenes/Boot.unity", "Assets/Scenes/Main.unity"]`

### `scriptingBackend`
- **Type:** enum: `IL2CPP` | `Mono`
- **Default:** `IL2CPP`
- `IL2CPP` is required for iOS. Strongly recommended for Android and Windows release builds for performance and security. `Mono` builds faster and enables script debugging.

### `apiCompatibilityLevel`
- **Type:** enum: `NET_Standard_2_0` | `NET_4_6` | `NET_Standard_2_1`
- **Default:** `NET_Standard_2_1`
- .NET API compatibility level used by the scripting runtime.

### `developmentBuild`
- **Type:** boolean
- **Default:** `false`
- Enables the Unity development build flag. Must be `false` for production environments.

### `allowDebugging`
- **Type:** boolean
- **Default:** `false`
- Allow script debugger attachment. Requires `developmentBuild: true`. Must be `false` for production.

### `connectProfiler`
- **Type:** boolean
- **Default:** `false`
- Allow Unity Profiler to connect. Adds runtime overhead; use for development and staging only.

### `deepProfiling`
- **Type:** boolean
- **Default:** `false`
- Enable deep profiling (full call stack profiling). Very high memory/CPU overhead; development only.

### `cleanBuildCache`
- **Type:** boolean
- **Default:** `false`
- Delete the Unity `Library/` folder before building. Ensures a fully clean build at the cost of longer build time. Recommended for production builds.

### `runTests`
- **Type:** boolean
- **Default:** `true`
- Run Unity Test Runner (EditMode and PlayMode suites) before the build step. Build is skipped if tests fail.

---

## `addressables` Object

### `addressables.enabled`
- **Type:** boolean
- **Required:** Yes
- Set to `false` if the project does not use Addressable Assets. When `false`, the Addressables build step is skipped entirely.

### `addressables.profile`
- **Type:** string
- Name of the Addressables build profile. Must exactly match a profile name defined in `AddressableAssetSettings` within the Unity project.

### `addressables.buildRemoteCatalog`
- **Type:** boolean
- **Default:** `false`
- Whether to build and upload the remote content catalog. Enable for staging/production when you host content remotely.

---

## `android` Object

### `android.applicationId`
- **Type:** string (reverse-DNS format)
- **Required:** Yes
- Android package name. Must match the pattern `com.company.game`. Validated by regex.

### `android.buildAppBundle`
- **Type:** boolean
- **Default:** `true`
- Build `.aab` (Android App Bundle) instead of `.apk`. Required for Google Play distribution.

### `android.minSdkVersion`
- **Type:** integer (21–35)
- **Default:** `22`
- Minimum Android API level. Android 5.1 (API 22) is the current reasonable minimum.

### `android.targetSdkVersion`
- **Type:** integer (29–35)
- **Default:** `34`
- Target Android API level. Google Play requires targeting a recent API level.

### `android.architecture`
- **Type:** enum: `ARM64` | `ARMv7` | `x86_64` | `All`
- **Default:** `ARM64`
- CPU architectures included. `ARM64` covers nearly all modern Android devices. `All` increases build size significantly.

### `android.keystoreMode`
- **Type:** enum: `debug` | `custom`
- **Default:** `custom`
- Signing mode. `debug` uses the Android SDK debug keystore (for development only). `custom` requires `ANDROID_KEYSTORE_*` secrets.

### `android.symbolExport`
- **Type:** enum: `none` | `public` | `debugging`
- **Default:** `none`
- Symbol export level for crash reporting (Firebase Crashlytics, etc.). `public` exports minified symbols; `debugging` exports full symbols.

---

## `ios` Object

### `ios.bundleIdentifier`
- **Type:** string (reverse-DNS format)
- **Required:** Yes
- iOS bundle identifier. Must match the provisioning profile. Validated by regex.

### `ios.buildNumber`
- **Type:** string (digits only)
- CFBundleVersion. If omitted, derived from `buildNumberStrategy`.

### `ios.targetOSVersion`
- **Type:** string matching `MAJOR.MINOR`
- **Default:** `"14.0"`
- Minimum iOS deployment target. Apple periodically raises the minimum for App Store submissions.

### `ios.automaticSigning`
- **Type:** boolean
- **Default:** `false`
- Use Xcode automatic code signing. When `true`, manual certificate/profile secrets are not used. Requires a registered device and Apple Developer account on the runner.

### `ios.developmentTeam`
- **Type:** string (10-character uppercase alphanumeric)
- Apple Developer Team ID. Found in the Apple Developer portal under Membership.

### `ios.exportMethod`
- **Type:** enum: `app-store` | `ad-hoc` | `enterprise` | `development`
- **Default:** `"app-store"`
- IPA export method. Determines which provisioning profile and certificate type are required.

### `ios.generateXcodeProjectOnly`
- **Type:** boolean
- **Default:** `false`
- Stop after Xcode project generation; do not compile or sign. Useful for local inspection of the generated project.

---

## `windows` Object

### `windows.architecture`
- **Type:** enum: `x86_64` | `x86`
- **Default:** `"x86_64"`
- Target CPU architecture for the Windows standalone build.

### `windows.outputName`
- **Type:** string
- Name of the output `.exe` (without extension). Defaults to `projectName` if omitted.

### `windows.compressOutput`
- **Type:** boolean
- **Default:** `false`
- Zip the entire output directory before upload as a GitHub Actions artifact. Reduces artifact storage consumption.

---

## `webgl` Object

### `webgl.compressionFormat`
- **Type:** enum: `Brotli` | `Gzip` | `Disabled`
- **Default:** `"Brotli"`
- WebGL build compression. `Brotli` gives the smallest files but requires server-side support. `Disabled` works on any static host but produces larger files.

### `webgl.decompressionFallback`
- **Type:** boolean
- **Default:** `true`
- Include Unity's JavaScript decompression fallback for servers that cannot set the `Content-Encoding` header correctly. Required for hosts like GitHub Pages without custom header support.

### `webgl.dataCaching`
- **Type:** boolean
- **Default:** `true`
- Enable IndexedDB caching of `.data` files in the browser. Reduces load time on repeat visits.

### `webgl.memorySize`
- **Type:** integer (32–2048)
- **Default:** `256`
- Initial WASM heap size in MB. Increase if you receive out-of-memory errors at runtime.

### `webgl.template`
- **Type:** enum: `Default` | `Minimal` | `PWA`
- **Default:** `"Default"`
- HTML template for the WebGL player. `Minimal` strips the Unity loading bar. `PWA` adds a service worker and Web App Manifest.

### `webgl.outputName`
- **Type:** string
- Name of the WebGL output folder.

---

## `gates` Object

### `gates.maxBuildSizeMB`
- **Type:** number (> 0)
- Hard size limit in MB. The pipeline fails if the artifact exceeds this value.

### `gates.warnBuildSizeIncreasePct`
- **Type:** number (0–100)
- Percentage increase vs. the baseline artifact size that triggers a warning annotation on the PR.

### `gates.failBuildSizeIncreasePct`
- **Type:** number (0–100)
- Percentage increase vs. baseline that fails the build. Must be ≥ `warnBuildSizeIncreasePct`.

### `gates.failOnWarnings`
- **Type:** boolean
- **Default:** `false`
- Treat Unity compiler warnings as errors. Equivalent to passing `-warningsAsErrors` to the Unity build method.

### `gates.requiredValidationRules`
- **Type:** array of enum strings
- Validation rules that must pass before the build proceeds. Available rules:
  - `no_missing_references` — No serialized field references are broken
  - `no_missing_scripts` — No GameObjects have missing MonoBehaviour scripts
  - `no_missing_prefabs` — No missing prefab references in scenes
  - `addressables_content_hash_stable` — Addressables content hash matches the last known-good hash
  - `bundle_identifier_matches_config` — The bundle ID in PlayerSettings matches `applicationId`/`bundleIdentifier` in the config

---

## `metadata` Object

Arbitrary string key-value pairs. Included verbatim in build manifests and notification messages. Example:

```json
"metadata": {
  "team": "mobile",
  "jira-ticket": "GAME-1234",
  "environment": "production"
}
```

---

## `hooks` Object

### `hooks.preBuild`
- **Type:** array of strings
- Script names to run before the build step. Scripts must exist at `scripts/hooks/<name>.sh` in the **consumer repository**.

### `hooks.postBuild`
- **Type:** array of strings
- Script names to run after a successful build.

Hooks are run in array order. If any hook exits with a non-zero code, the pipeline fails and subsequent hooks are not executed.
