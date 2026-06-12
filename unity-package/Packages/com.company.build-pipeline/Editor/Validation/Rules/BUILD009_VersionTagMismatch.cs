using System;

namespace Company.BuildPipeline.Editor.Validation.Rules
{
    /// <summary>
    /// Ensures that when a releaseTag is provided it is consistent with the configured bundleVersion.
    /// Expected tag format: v{bundleVersion}  (e.g. "v1.2.3" for bundleVersion "1.2.3").
    /// </summary>
    public class BUILD009_VersionTagMismatch : IBuildValidationRule
    {
        public string Id => "BUILD009";
        public ValidationSeverity Severity => ValidationSeverity.Warning;

        public ValidationResult Validate(BuildContext context)
        {
            var cfg = context.Configuration;

            if (string.IsNullOrWhiteSpace(cfg.ReleaseTag))
                return ValidationResult.Pass(Id, Severity, "No releaseTag provided — skipping version tag check.");

            if (string.IsNullOrWhiteSpace(cfg.BundleVersion))
                return ValidationResult.Pass(Id, Severity, "No bundleVersion configured — skipping version tag check.");

            // Normalise: strip leading 'v' from tag and compare.
            var tag = cfg.ReleaseTag.TrimStart('v', 'V').Trim();
            var version = cfg.BundleVersion.Trim();

            if (!string.Equals(tag, version, StringComparison.Ordinal))
                return ValidationResult.Fail(Id, Severity,
                    $"releaseTag '{cfg.ReleaseTag}' (normalised: '{tag}') does not match bundleVersion '{version}'.");

            return ValidationResult.Pass(Id, Severity,
                $"releaseTag '{cfg.ReleaseTag}' matches bundleVersion '{cfg.BundleVersion}'.");
        }
    }
}
