using System.Collections.Generic;
using Newtonsoft.Json;

namespace Company.BuildPipeline.Editor
{
    /// <summary>
    /// Represents the full merged build configuration loaded from layered JSON files and CLI overrides.
    /// Field JSON property names match unity-build-config.schema.json keys exactly.
    /// C# property names are kept stable for intra-package usage.
    /// </summary>
    public class BuildConfiguration
    {
        // ── Project identity ──────────────────────────────────────────────────

        /// <summary>Internal project identifier used in artifact names and job names.</summary>
        [JsonProperty("projectName")]
        public string ProjectName { get; set; } = string.Empty;

        [JsonProperty("productName")]
        public string ProductName { get; set; } = string.Empty;

        [JsonProperty("companyName")]
        public string CompanyName { get; set; } = string.Empty;

        [JsonProperty("bundleVersion")]
        public string BundleVersion { get; set; } = "0.0.1";

        /// <summary>
        /// Legacy flat app identifier (reverse-DNS bundle ID).
        /// Prefer platform-specific blocks: <see cref="Android"/>.<see cref="AndroidBuildConfig.ApplicationId"/>
        /// or <see cref="iOS"/>.<see cref="IosBuildConfig.BundleIdentifier"/> for new configs.
        /// </summary>
        [JsonProperty("appIdentifier")]
        public string AppIdentifier { get; set; } = string.Empty;

        // ── Environment / target ──────────────────────────────────────────────

        /// <summary>development | staging | production</summary>
        [JsonProperty("environment")]
        public string Environment { get; set; } = "development";

        [JsonProperty("targetPlatform")]
        public string TargetPlatform { get; set; } = string.Empty;

        /// <summary>
        /// Output directory for build artifacts (relative to project root).
        /// JSON key: "outputDirectory" — matches schema canonical name.
        /// </summary>
        [JsonProperty("outputDirectory")]
        public string OutputPath { get; set; } = "Builds/output";

        /// <summary>Root workspace directory used for path containment checks (BUILD007).</summary>
        [JsonProperty("workspace")]
        public string Workspace { get; set; } = string.Empty;

        // ── Build number strategy ─────────────────────────────────────────────

        /// <summary>github_run_number | timestamp | manual</summary>
        [JsonProperty("buildNumberStrategy")]
        public string BuildNumberStrategy { get; set; } = "github_run_number";

        // ── Build flags ───────────────────────────────────────────────────────

        /// <summary>
        /// Enable Unity development build flag.
        /// JSON key: "developmentBuild" — matches schema canonical name.
        /// </summary>
        [JsonProperty("developmentBuild")]
        public bool IsDevelopmentBuild { get; set; } = false;

        /// <summary>
        /// Attach script debugger. Only valid when <see cref="IsDevelopmentBuild"/> is true.
        /// JSON key: "allowDebugging" — matches schema canonical name.
        /// </summary>
        [JsonProperty("allowDebugging")]
        public bool IsDebuggingEnabled { get; set; } = false;

        [JsonProperty("connectProfiler")]
        public bool ConnectProfiler { get; set; } = false;

        [JsonProperty("deepProfiling")]
        public bool DeepProfiling { get; set; } = false;

        /// <summary>Delete Unity Library/ cache before building. Slower but avoids stale-cache issues.</summary>
        [JsonProperty("cleanBuildCache")]
        public bool CleanBuildCache { get; set; } = false;

        /// <summary>Whether to run Unity Test Runner before the build step.</summary>
        [JsonProperty("runTests")]
        public bool RunTests { get; set; } = true;

        /// <summary>IL2CPP | Mono</summary>
        [JsonProperty("scriptingBackend")]
        public string ScriptingBackend { get; set; } = "IL2CPP";

        /// <summary>NET_Standard_2_0 | NET_4_6 | NET_Standard_2_1</summary>
        [JsonProperty("apiCompatibilityLevel")]
        public string ApiCompatibilityLevel { get; set; } = "NET_Standard_2_1";

        // ── Scenes ────────────────────────────────────────────────────────────

        /// <summary>Ordered list of scene paths to include in the build.</summary>
        [JsonProperty("scenes")]
        public List<string> Scenes { get; set; } = new List<string>();

        /// <summary>Scene that must be the first (index 0) entry in <see cref="Scenes"/>.</summary>
        [JsonProperty("bootstrapScene")]
        public string BootstrapScene { get; set; } = string.Empty;

        // ── Addressables ──────────────────────────────────────────────────────

        /// <summary>
        /// Addressables configuration block (JSON key "addressables").
        /// Takes precedence over <see cref="AddressablesProfile"/> for new configs.
        /// </summary>
        [JsonProperty("addressables")]
        public AddressablesConfig Addressables { get; set; } = null;

        /// <summary>
        /// Legacy flat Addressables profile name.
        /// Prefer <see cref="Addressables"/>.<see cref="AddressablesConfig.Profile"/> for new configs.
        /// </summary>
        [JsonProperty("addressablesProfile")]
        public string AddressablesProfile { get; set; } = string.Empty;

        // ── Versioning / release ──────────────────────────────────────────────

        [JsonProperty("releaseTag")]
        public string ReleaseTag { get; set; } = string.Empty;

        // ── Platform blocks ───────────────────────────────────────────────────

        /// <summary>Android-specific settings block (JSON key "android").</summary>
        [JsonProperty("android")]
        public AndroidBuildConfig Android { get; set; } = null;

        /// <summary>
        /// iOS-specific settings block (JSON key "iOS").
        /// Takes precedence over <see cref="SigningConfig"/> for iOS signing fields when present.
        /// </summary>
        [JsonProperty("iOS")]
        public IosBuildConfig iOS { get; set; } = null;

        // ── Signing (Android / iOS legacy) ────────────────────────────────────

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

    // ── Addressables config ───────────────────────────────────────────────────

    public class AddressablesConfig
    {
        [JsonProperty("enabled")]
        public bool Enabled { get; set; } = false;

        /// <summary>Addressables build profile name (must match a profile in AddressableAssetSettings).</summary>
        [JsonProperty("profile")]
        public string Profile { get; set; } = string.Empty;

        [JsonProperty("buildRemoteCatalog")]
        public bool BuildRemoteCatalog { get; set; } = false;
    }

    // ── Android config ────────────────────────────────────────────────────────

    public class AndroidBuildConfig
    {
        /// <summary>Android application ID (package name), e.g. com.company.game.</summary>
        [JsonProperty("applicationId")]
        public string ApplicationId { get; set; } = string.Empty;

        /// <summary>Build .aab instead of .apk. Required for Play Store distribution.</summary>
        [JsonProperty("buildAppBundle")]
        public bool BuildAppBundle { get; set; } = true;

        [JsonProperty("minSdkVersion")]
        public int MinSdkVersion { get; set; } = 22;

        [JsonProperty("targetSdkVersion")]
        public int TargetSdkVersion { get; set; } = 34;

        /// <summary>ARM64 | ARMv7 | x86_64 | All</summary>
        [JsonProperty("architecture")]
        public string Architecture { get; set; } = "ARM64";

        /// <summary>debug | custom</summary>
        [JsonProperty("keystoreMode")]
        public string KeystoreMode { get; set; } = "custom";

        /// <summary>none | public | debugging</summary>
        [JsonProperty("symbolExport")]
        public string SymbolExport { get; set; } = "none";
    }

    // ── Signing config ────────────────────────────────────────────────────────

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

    // ── iOS config ────────────────────────────────────────────────────────────

    /// <summary>
    /// iOS-specific build configuration block.
    /// JSON key: "iOS" (case-sensitive — matches the CI contract).
    /// Fields map directly to PlayerSettings.iOS and are consumed by IOSBuilder + IOSXcodePostProcessor.
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
        /// C# does not configure Xcode version; this value is consumed by the xcodebuild shell step.
        /// </summary>
        [JsonProperty("xcodeVersion")]
        public string XcodeVersion { get; set; } = string.Empty;

        // ── Signing ───────────────────────────────────────────────────────────

        /// <summary>Apple Developer Team ID (10-character uppercase alphanumeric).</summary>
        [JsonProperty("developmentTeamId")]
        public string DevelopmentTeamId { get; set; } = string.Empty;

        /// <summary>
        /// Legacy alias for <see cref="DevelopmentTeamId"/>.
        /// Accepted for backward compatibility; prefer developmentTeamId in new configs.
        /// </summary>
        [JsonProperty("developmentTeam")]
        public string DevelopmentTeam { get; set; } = string.Empty;

        /// <summary>manual | automatic. Certificate material never appears in C#.</summary>
        [JsonProperty("signingStyle")]
        public string SigningStyle { get; set; } = "manual";

        /// <summary>Provisioning profile UUID or specifier name. Required when signingStyle=manual.</summary>
        [JsonProperty("provisioningProfileSpecifier")]
        public string ProvisioningProfileSpecifier { get; set; } = string.Empty;

        /// <summary>
        /// Code signing identity, e.g. "iPhone Distribution".
        /// Stored in metadata for the xcodebuild step; C# does not apply it directly.
        /// </summary>
        [JsonProperty("codeSignIdentity")]
        public string CodeSignIdentity { get; set; } = string.Empty;

        // ── Export / distribution ─────────────────────────────────────────────

        /// <summary>app-store | app-store-connect | ad-hoc | enterprise | development</summary>
        [JsonProperty("exportMethod")]
        public string ExportMethod { get; set; } = "app-store";

        /// <summary>Enable Bitcode. Must be false for Xcode 14+ / Unity 2022+.</summary>
        [JsonProperty("enableBitcode")]
        public bool EnableBitcode { get; set; } = false;

        /// <summary>Export dSYM symbol packages alongside the IPA.</summary>
        [JsonProperty("generateSymbols")]
        public bool GenerateSymbols { get; set; } = false;

        /// <summary>Upload dSYM files to App Store Connect.</summary>
        [JsonProperty("uploadSymbols")]
        public bool UploadSymbols { get; set; } = false;

        /// <summary>Submit IPA to TestFlight (gated by workflow deploy step).</summary>
        [JsonProperty("uploadToTestFlight")]
        public bool UploadToTestFlight { get; set; } = false;

        /// <summary>Stop after Xcode project generation without building IPA.</summary>
        [JsonProperty("generateXcodeProjectOnly")]
        public bool GenerateXcodeProjectOnly { get; set; } = false;

        // ── Xcode post-process (IOSXcodePostProcessor) ────────────────────────

        /// <summary>
        /// Associated domain identifiers, e.g. ["applinks:example.com"].
        /// </summary>
        [JsonProperty("associatedDomains")]
        public List<string> AssociatedDomains { get; set; } = new List<string>();

        /// <summary>
        /// Additional Apple system framework bundle names to link, e.g. ["StoreKit.framework"].
        /// </summary>
        [JsonProperty("additionalFrameworks")]
        public List<string> AdditionalFrameworks { get; set; } = new List<string>();

        /// <summary>
        /// Info.plist NSUsageDescription key overrides.
        /// Key = plist key, Value = user-facing string.
        /// </summary>
        [JsonProperty("usageDescriptions")]
        public Dictionary<string, string> UsageDescriptions { get; set; } = new Dictionary<string, string>();

        // ── Helpers ───────────────────────────────────────────────────────────

        /// <summary>
        /// Returns the effective Apple Developer Team ID.
        /// Prefers <see cref="DevelopmentTeamId"/> over legacy <see cref="DevelopmentTeam"/>.
        /// </summary>
        public string EffectiveTeamId =>
            !string.IsNullOrWhiteSpace(DevelopmentTeamId) ? DevelopmentTeamId : DevelopmentTeam;
    }
}
