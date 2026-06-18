using System.Collections.Generic;
using Newtonsoft.Json;

namespace Company.BuildPipeline.Editor
{
    /// <summary>
    /// Represents the full merged build configuration loaded from layered JSON files and CLI overrides.
    /// Field names match the JSON schema keys exactly.
    /// </summary>
    public class BuildConfiguration
    {
        // ── Identity ──────────────────────────────────────────────────────────

        [JsonProperty("productName")]
        public string ProductName { get; set; } = string.Empty;

        [JsonProperty("companyName")]
        public string CompanyName { get; set; } = string.Empty;

        [JsonProperty("bundleVersion")]
        public string BundleVersion { get; set; } = "0.0.1";

        [JsonProperty("appIdentifier")]
        public string AppIdentifier { get; set; } = string.Empty;

        // ── Environment / target ──────────────────────────────────────────────

        /// <summary>development | staging | production</summary>
        [JsonProperty("environment")]
        public string Environment { get; set; } = "development";

        [JsonProperty("targetPlatform")]
        public string TargetPlatform { get; set; } = string.Empty;

        [JsonProperty("outputPath")]
        public string OutputPath { get; set; } = "Builds/output";

        /// <summary>Root workspace directory used for path containment checks.</summary>
        [JsonProperty("workspace")]
        public string Workspace { get; set; } = string.Empty;

        // ── Build flags ───────────────────────────────────────────────────────

        [JsonProperty("isDevelopmentBuild")]
        public bool IsDevelopmentBuild { get; set; } = false;

        [JsonProperty("isDebuggingEnabled")]
        public bool IsDebuggingEnabled { get; set; } = false;

        [JsonProperty("scriptingBackend")]
        public string ScriptingBackend { get; set; } = "Mono2x";

        // ── Scenes ────────────────────────────────────────────────────────────

        /// <summary>Ordered list of scene paths to include in the build.</summary>
        [JsonProperty("scenes")]
        public List<string> Scenes { get; set; } = new List<string>();

        /// <summary>Scene that must be the first (index 0) entry.</summary>
        [JsonProperty("bootstrapScene")]
        public string BootstrapScene { get; set; } = string.Empty;

        // ── Addressables ──────────────────────────────────────────────────────

        [JsonProperty("addressablesProfile")]
        public string AddressablesProfile { get; set; } = string.Empty;

        // ── Versioning / release ──────────────────────────────────────────────

        [JsonProperty("releaseTag")]
        public string ReleaseTag { get; set; } = string.Empty;

        // ── iOS platform block ────────────────────────────────────────────────

        /// <summary>
        /// iOS-specific settings block (JSON key "iOS").
        /// When present, takes precedence over the shared <see cref="SigningConfig"/> for iOS signing fields.
        /// </summary>
        [JsonProperty("ios")]
        public IosBuildConfig iOS { get; set; } = null;

        // ── Signing (Android / iOS) ───────────────────────────────────────────

        [JsonProperty("signingConfig")]
        public SigningConfiguration SigningConfig { get; set; } = null;

        // ── Endpoints ─────────────────────────────────────────────────────────

        /// <summary>Named service endpoints, e.g. { "api": "https://api.prod.example.com" }.</summary>
        [JsonProperty("endpoints")]
        public Dictionary<string, string> Endpoints { get; set; } = new Dictionary<string, string>();

        // ── Hooks ─────────────────────────────────────────────────────────────

        /// <summary>Hook type names that are mandatory; BUILD014 fires if any are absent.</summary>
        [JsonProperty("requiredHooks")]
        public List<string> RequiredHooks { get; set; } = new List<string>();

        // ── Unity version ─────────────────────────────────────────────────────

        [JsonProperty("unityVersion")]
        public string UnityVersion { get; set; } = string.Empty;

        // ── Schema validation ─────────────────────────────────────────────────

        /// <summary>Schema version string; BUILD013 checks for recognised values.</summary>
        [JsonProperty("$schema")]
        public string Schema { get; set; } = string.Empty;

        [JsonProperty("schemaVersion")]
        public string SchemaVersion { get; set; } = string.Empty;
    }

    public class SigningConfiguration
    {
        [JsonProperty("keystorePath")]
        public string KeystorePath { get; set; } = string.Empty;

        /// <summary>Env-var name that holds the keystore password (never the password itself).</summary>
        [JsonProperty("keystorePasswordEnvVar")]
        public string KeystorePasswordEnvVar { get; set; } = string.Empty;

        [JsonProperty("keyAlias")]
        public string KeyAlias { get; set; } = string.Empty;

        [JsonProperty("keyAliasPasswordEnvVar")]
        public string KeyAliasPasswordEnvVar { get; set; } = string.Empty;

        // iOS (legacy — prefer the top-level iOS block for new configs)
        [JsonProperty("provisioningProfileId")]
        public string ProvisioningProfileId { get; set; } = string.Empty;

        [JsonProperty("teamId")]
        public string TeamId { get; set; } = string.Empty;

        [JsonProperty("codeSignIdentity")]
        public string CodeSignIdentity { get; set; } = string.Empty;
    }

    /// <summary>
    /// iOS-specific build configuration block.
    /// JSON key: "iOS" (case-sensitive — matches the CI contract).
    /// Fields map directly to PlayerSettings.iOS and are consumed by IOSBuilder + IOSPostProcessBuild.
    /// </summary>
    public class IosBuildConfig
    {
        // ── App identity ─────────────────────────────────────────────────────

        /// <summary>iOS bundle identifier, e.g. com.company.game.</summary>
        [JsonProperty("bundleIdentifier")]
        public string BundleIdentifier { get; set; } = string.Empty;

        /// <summary>CFBundleVersion — integer build-counter string, e.g. "42".</summary>
        [JsonProperty("buildNumber")]
        public string BuildNumber { get; set; } = string.Empty;

        /// <summary>CFBundleShortVersionString — user-visible version, e.g. "1.2.3".</summary>
        [JsonProperty("marketingVersion")]
        public string MarketingVersion { get; set; } = string.Empty;

        // ── SDK / target ─────────────────────────────────────────────────────

        /// <summary>DeviceSDK (default) or SimulatorSDK.</summary>
        [JsonProperty("sdkVersion")]
        public string SdkVersion { get; set; } = "DeviceSDK";

        /// <summary>Minimum iOS deployment target, e.g. "14.0".</summary>
        [JsonProperty("targetOSVersion")]
        public string TargetOSVersion { get; set; } = "14.0";

        /// <summary>CPU architecture. Only ARM64 is valid for App Store distribution.</summary>
        [JsonProperty("architecture")]
        public string Architecture { get; set; } = "ARM64";

        /// <summary>
        /// Informational: Xcode version expected by the CI runner.
        /// C# does not configure the Xcode version; this value is consumed by the xcodebuild shell step.
        /// </summary>
        [JsonProperty("xcodeVersion")]
        public string XcodeVersion { get; set; } = string.Empty;

        // ── Signing ───────────────────────────────────────────────────────────

        /// <summary>Apple Developer Team ID (10-character alphanumeric string).</summary>
        [JsonProperty("developmentTeamId")]
        public string DevelopmentTeamId { get; set; } = string.Empty;

        /// <summary>automatic | manual. Certificate material never appears in C#.</summary>
        [JsonProperty("signingStyle")]
        public string SigningStyle { get; set; } = "manual";

        /// <summary>Provisioning profile UUID or specifier name. Used when signingStyle=manual.</summary>
        [JsonProperty("provisioningProfileSpecifier")]
        public string ProvisioningProfileSpecifier { get; set; } = string.Empty;

        /// <summary>
        /// Code signing identity string, e.g. "iPhone Distribution".
        /// Stored in metadata for the xcodebuild step; C# does not apply it directly.
        /// </summary>
        [JsonProperty("codeSignIdentity")]
        public string CodeSignIdentity { get; set; } = string.Empty;

        // ── Export / distribution ─────────────────────────────────────────────

        /// <summary>app-store | ad-hoc | enterprise | development</summary>
        [JsonProperty("exportMethod")]
        public string ExportMethod { get; set; } = "app-store";

        /// <summary>Whether to enable bitcode. Must be false for Xcode 14+ / Unity 2022+.</summary>
        [JsonProperty("enableBitcode")]
        public bool EnableBitcode { get; set; } = false;

        /// <summary>Whether the xcodebuild step should export dSYM symbol packages.</summary>
        [JsonProperty("generateSymbols")]
        public bool GenerateSymbols { get; set; } = false;

        /// <summary>Whether the xcodebuild step should upload symbols to Apple.</summary>
        [JsonProperty("uploadSymbols")]
        public bool UploadSymbols { get; set; } = false;

        /// <summary>Whether the altool / xcrun step should submit the IPA to TestFlight.</summary>
        [JsonProperty("uploadToTestFlight")]
        public bool UploadToTestFlight { get; set; } = false;

        // ── Xcode post-process (IOSPostProcessBuild) ──────────────────────────

        /// <summary>
        /// Associated domain identifiers to register in the app entitlements,
        /// e.g. ["applinks:example.com", "webcredentials:example.com"].
        /// </summary>
        [JsonProperty("associatedDomains")]
        public List<string> AssociatedDomains { get; set; } = new List<string>();

        /// <summary>
        /// Additional Apple system framework bundle names to link, e.g. ["StoreKit.framework"].
        /// These are added to the main target via PBXProject — not required for frameworks
        /// that Unity links automatically.
        /// </summary>
        [JsonProperty("additionalFrameworks")]
        public List<string> AdditionalFrameworks { get; set; } = new List<string>();

        /// <summary>
        /// Info.plist NSUsageDescription key overrides.
        /// Key = plist key (e.g. "NSCameraUsageDescription"), Value = user-facing string.
        /// When a key is absent the post-process hook applies a safe default.
        /// </summary>
        [JsonProperty("usageDescriptions")]
        public Dictionary<string, string> UsageDescriptions { get; set; } = new Dictionary<string, string>();
    }
}
