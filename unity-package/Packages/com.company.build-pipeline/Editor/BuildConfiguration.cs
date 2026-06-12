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

        // iOS
        [JsonProperty("provisioningProfileId")]
        public string ProvisioningProfileId { get; set; } = string.Empty;

        [JsonProperty("teamId")]
        public string TeamId { get; set; } = string.Empty;

        [JsonProperty("codeSignIdentity")]
        public string CodeSignIdentity { get; set; } = string.Empty;
    }
}
