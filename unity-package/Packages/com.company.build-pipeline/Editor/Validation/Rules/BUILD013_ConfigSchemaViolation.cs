using System;
using System.Collections.Generic;

namespace Company.BuildPipeline.Editor.Validation.Rules
{
    /// <summary>
    /// Checks that the config declares a recognised schemaVersion and that mandatory
    /// top-level fields are non-empty.
    /// </summary>
    public class BUILD013_ConfigSchemaViolation : IBuildValidationRule
    {
        public string Id => "BUILD013";
        public ValidationSeverity Severity => ValidationSeverity.Error;

        private static readonly HashSet<string> KnownSchemaVersions =
            new HashSet<string>(StringComparer.OrdinalIgnoreCase) { "1.0", "1.0.0", "1", "" };

        private static readonly string[] RequiredFields =
        {
            nameof(BuildConfiguration.ProductName),
            nameof(BuildConfiguration.AppIdentifier),
            nameof(BuildConfiguration.BundleVersion),
            nameof(BuildConfiguration.TargetPlatform)
        };

        public ValidationResult Validate(BuildContext context)
        {
            var cfg = context.Configuration;

            // Schema version check (empty is allowed — means "unversioned").
            if (!string.IsNullOrWhiteSpace(cfg.SchemaVersion) && !KnownSchemaVersions.Contains(cfg.SchemaVersion))
                return ValidationResult.Fail(Id, Severity,
                    $"Unrecognised schemaVersion '{cfg.SchemaVersion}'. Known versions: {string.Join(", ", KnownSchemaVersions)}.");

            // Required fields.
            var missing = new List<string>();
            if (string.IsNullOrWhiteSpace(cfg.ProductName))   missing.Add("productName");
            if (string.IsNullOrWhiteSpace(cfg.AppIdentifier)) missing.Add("appIdentifier");
            if (string.IsNullOrWhiteSpace(cfg.BundleVersion)) missing.Add("bundleVersion");
            if (string.IsNullOrWhiteSpace(cfg.TargetPlatform)) missing.Add("targetPlatform");

            if (missing.Count > 0)
                return ValidationResult.Fail(Id, Severity,
                    $"Missing required config field(s): {string.Join(", ", missing)}.");

            return ValidationResult.Pass(Id, Severity, "Config schema is valid.");
        }
    }
}
