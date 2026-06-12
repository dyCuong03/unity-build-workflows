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

            // If no profile is set, skip (some projects don't use Addressables).
            if (string.IsNullOrWhiteSpace(cfg.AddressablesProfile))
                return ValidationResult.Pass(Id, Severity, "No addressablesProfile configured — skipping.");

            if (string.IsNullOrWhiteSpace(cfg.Environment))
                return ValidationResult.Pass(Id, Severity, "No environment set — skipping addressables profile check.");

            bool profileContainsEnv = cfg.AddressablesProfile
                .IndexOf(cfg.Environment, System.StringComparison.OrdinalIgnoreCase) >= 0;

            if (!profileContainsEnv)
                return ValidationResult.Fail(Id, Severity,
                    $"Addressables profile '{cfg.AddressablesProfile}' does not contain the environment name '{cfg.Environment}'. " +
                    "Verify that the correct CDN profile is selected.");

            return ValidationResult.Pass(Id, Severity,
                $"Addressables profile '{cfg.AddressablesProfile}' matches environment '{cfg.Environment}'.");
        }
    }
}
