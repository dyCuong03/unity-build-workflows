# BuildConfig Reference

Full reference for every field in the `BuildConfig` JSON schema. Validate your config against `schemas/unity-build-config.schema.json`.

---

## Root Fields

### `projectName`
- **Type:** string (1–64 chars) — **Required**
- Internal identifier. Used in artifact names and workflow job names.

### `companyName`
- **Type:** string (1–64 chars) — **Required**
- Maps to `PlayerSettings.companyName`.

### `productName`
- **Type:** string (1–64 chars) — **Required**
- Maps to `PlayerSettings.productName`. App name on-device.

### `bundleVersion`
- **Type:** string matching `MAJOR.MINOR.PATCH` — **Required**
- Player-facing version string.

### `buildNumberStrategy`
- **Type:** enum: `github_run_number` | `timestamp` | `manual`
- **Default:** `github_run_number`

### `outputDirectory`
- **Type:** string — **Required**
- Relative path for build output. Inside Docker, this maps to bind-mounted `Builds/` directory.

### `scenes`
- **Type:** array of strings (min 1) — **Required**
- Scene paths starting with `Assets/` and ending with `.unity`.

### `scriptingBackend`
- **Type:** enum: `IL2CPP` | `Mono`
- **Default:** `IL2CPP`

### `apiCompatibilityLevel`
- **Type:** enum: `NET_Standard_2_0` | `NET_4_6` | `NET_Standard_2_1`
- **Default:** `NET_Standard_2_1`

### `developmentBuild`
- **Type:** boolean — **Default:** `false`
- Must be `false` for production.

### `allowDebugging`
- **Type:** boolean — **Default:** `false`
- Requires `developmentBuild: true`.

### `connectProfiler` / `deepProfiling`
- **Type:** boolean — **Default:** `false`

### `cleanBuildCache`
- **Type:** boolean — **Default:** `false`
- Deletes Unity Library/ cache before building. In Docker, this means not mounting the cache volume.

### `runTests`
- **Type:** boolean — **Default:** `true`

---

## `addressables` Object

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `enabled` | boolean | Yes | — | Whether Addressables are used |
| `profile` | string | No | — | Addressables build profile name |
| `buildRemoteCatalog` | boolean | No | `false` | Build remote content catalog |

---

## `android` Object

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `applicationId` | string | Yes | — | Android package name (reverse-DNS) |
| `buildAppBundle` | boolean | No | `true` | `.aab` for Play Store, `.apk` for sideloading |
| `minSdkVersion` | integer | No | `22` | Minimum Android API level (21–35) |
| `targetSdkVersion` | integer | No | `34` | Target Android API level (29–35) |
| `architecture` | enum | No | `ARM64` | `ARM64`, `ARMv7`, `x86_64`, `All` |
| `keystoreMode` | enum | No | `custom` | `debug` or `custom` |
| `symbolExport` | enum | No | `none` | `none`, `public`, `debugging` |

---

## `ios` Object

**Note:** iOS builds are unsupported by the Docker-only platform. The `ios` config section remains in the schema for projects using dedicated macOS pipelines alongside this repository.

| Field | Type | Required | Default |
|---|---|---|---|
| `bundleIdentifier` | string | Yes | — |
| `buildNumber` | string | No | derived |
| `targetOSVersion` | string | No | `14.0` |
| `automaticSigning` | boolean | No | `false` |
| `developmentTeam` | string | No | — |
| `exportMethod` | enum | No | `app-store` |
| `generateXcodeProjectOnly` | boolean | No | `false` |

---

## `windows` Object

**Note:** Windows builds are unsupported by the Docker-only platform. The `windows` config section remains in the schema for projects using dedicated Windows pipelines.

| Field | Type | Default |
|---|---|---|
| `architecture` | enum | `x86_64` |
| `outputName` | string | — |
| `compressOutput` | boolean | `false` |

---

## `webgl` Object

| Field | Type | Default | Description |
|---|---|---|---|
| `compressionFormat` | enum | `Brotli` | `Brotli`, `Gzip`, `Disabled` |
| `decompressionFallback` | boolean | `true` | JS decompression fallback |
| `dataCaching` | boolean | `true` | IndexedDB caching |
| `memorySize` | integer | `256` | Initial WASM heap (MB) |
| `template` | enum | `Default` | `Default`, `Minimal`, `PWA` |
| `outputName` | string | — | Output folder name |

---

## `gates` Object

| Field | Type | Description |
|---|---|---|
| `maxBuildSizeMB` | number | Hard size limit in MB |
| `warnBuildSizeIncreasePct` | number | Warning threshold (0–100) |
| `failBuildSizeIncreasePct` | number | Failure threshold (0–100) |
| `failOnWarnings` | boolean | Treat compiler warnings as errors |
| `requiredValidationRules` | array | Validation rules that must pass |

Available validation rules:
- `no_missing_references`
- `no_missing_scripts`
- `no_missing_prefabs`
- `addressables_content_hash_stable`
- `bundle_identifier_matches_config`

---

## `metadata` Object

Arbitrary string key-value pairs included in build manifests.

---

## `hooks` Object

| Field | Type | Description |
|---|---|---|
| `preBuild` | array of strings | Hook scripts to run before build |
| `postBuild` | array of strings | Hook scripts to run after successful build |

Hooks run inside the Unity build process via `IBuildHook` implementations.
