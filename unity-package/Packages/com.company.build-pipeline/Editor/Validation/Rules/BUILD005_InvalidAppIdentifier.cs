using System.Text.RegularExpressions;

namespace Company.BuildPipeline.Editor.Validation.Rules
{
    /// <summary>
    /// Validates the application identifier is a well-formed reverse-DNS bundle ID.
    /// Pattern: at least two dot-separated segments of lowercase alphanumeric / underscore / hyphen.
    /// </summary>
    public class BUILD005_InvalidAppIdentifier : IBuildValidationRule
    {
        public string Id => "BUILD005";
        public ValidationSeverity Severity => ValidationSeverity.Error;

        // Must start with a letter, segments separated by dots, at least two segments.
        private static readonly Regex ValidPattern =
            new Regex(@"^[a-zA-Z][a-zA-Z0-9_-]*(\.[a-zA-Z][a-zA-Z0-9_-]*)+$", RegexOptions.Compiled);

        public ValidationResult Validate(BuildContext context)
        {
            var cfg = context.Configuration;

            // Prefer platform-specific identifier; fall back to legacy flat appIdentifier.
            // Platform builders (IOSBuilder, AndroidBuilder) also resolve this at configure time.
            var platform = cfg.TargetPlatform?.ToLowerInvariant();
            string identifier;
            if (platform == "ios" && cfg.iOS != null && !string.IsNullOrWhiteSpace(cfg.iOS.BundleIdentifier))
                identifier = cfg.iOS.BundleIdentifier;
            else if (platform == "android" && cfg.Android != null && !string.IsNullOrWhiteSpace(cfg.Android.ApplicationId))
                identifier = cfg.Android.ApplicationId;
            else
                identifier = cfg.AppIdentifier;

            // If no identifier is resolvable, skip (e.g. platform block not yet added to config).
            if (string.IsNullOrWhiteSpace(identifier))
                return ValidationResult.Pass(Id, Severity,
                    "No appIdentifier or platform-specific identifier found — skipping. " +
                    "Add 'appIdentifier' or a platform block (android.applicationId / iOS.bundleIdentifier).");

            if (!ValidPattern.IsMatch(identifier))
                return ValidationResult.Fail(Id, Severity,
                    $"App identifier '{identifier}' is not a valid reverse-DNS identifier (e.g. com.company.game).");

            return ValidationResult.Pass(Id, Severity, $"App identifier '{identifier}' is valid.");
        }
    }
}
