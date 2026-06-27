namespace Company.BuildPipeline.Editor.Validation.Rules
{
    /// <summary>
    /// Ensures the Addressables profile name contains or matches the active environment name,
    /// preventing a staging build from accidentally using production CDN addresses.
    /// </summary>
    public class BUILD006_AddressablesProfileMismatch : IBuildValidationRule
    {
        public string Id => "BUILD006";
        public ValidationSeverity Severity => ValidationSeverity.Warning;

        public ValidationResult Validate(BuildContext context)
        {
            var cfg = context.Configuration;

            // Resolve profile from nested addressables block or legacy flat field.
            // Nested block takes precedence; skip entirely if addressables are disabled.
            if (cfg.Addressables != null && !cfg.Addressables.Enabled)
                return ValidationResult.Pass(Id, Severity, "addressables.enabled=false — skipping profile check.");

            var profile = cfg.Addressables?.Profile ?? cfg.AddressablesProfile;

            // If no profile is set, skip (some projects don't use Addressables).
            if (string.IsNullOrWhiteSpace(profile))
                return ValidationResult.Pass(Id, Severity, "No addressables profile configured — skipping.");

            if (string.IsNullOrWhiteSpace(cfg.Environment))
                return ValidationResult.Pass(Id, Severity, "No environment set — skipping addressables profile check.");

            bool profileContainsEnv = profile
                .IndexOf(cfg.Environment, System.StringComparison.OrdinalIgnoreCase) >= 0;

            if (!profileContainsEnv)
                return ValidationResult.Fail(Id, Severity,
                    $"Addressables profile '{profile}' does not contain the environment name '{cfg.Environment}'. " +
                    "Verify that the correct CDN profile is selected.");

            return ValidationResult.Pass(Id, Severity,
                $"Addressables profile '{profile}' matches environment '{cfg.Environment}'.");
        }
    }
}
