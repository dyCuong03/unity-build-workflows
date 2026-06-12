namespace Company.BuildPipeline.Editor.Validation.Rules
{
    /// <summary>
    /// Ensures a bootstrapScene is configured and that it appears as the first entry in the scenes list.
    /// </summary>
    public class BUILD001_BootstrapSceneMissing : IBuildValidationRule
    {
        public string Id => "BUILD001";
        public ValidationSeverity Severity => ValidationSeverity.Error;

        public ValidationResult Validate(BuildContext context)
        {
            var cfg = context.Configuration;

            if (string.IsNullOrWhiteSpace(cfg.BootstrapScene))
                return ValidationResult.Fail(Id, Severity, "bootstrapScene is not configured.");

            if (cfg.Scenes == null || cfg.Scenes.Count == 0)
                return ValidationResult.Fail(Id, Severity, "No scenes are configured; bootstrapScene cannot be verified.");

            if (cfg.Scenes[0] != cfg.BootstrapScene)
                return ValidationResult.Fail(Id, Severity,
                    $"bootstrapScene '{cfg.BootstrapScene}' must be the first entry in the scenes list, but found '{cfg.Scenes[0]}'.");

            return ValidationResult.Pass(Id, Severity, $"bootstrapScene '{cfg.BootstrapScene}' is the first scene.");
        }
    }
}
