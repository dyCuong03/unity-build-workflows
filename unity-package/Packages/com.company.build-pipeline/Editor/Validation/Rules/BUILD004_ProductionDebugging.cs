namespace Company.BuildPipeline.Editor.Validation.Rules
{
    /// <summary>
    /// Prevents enabling script debugging in production builds.
    /// </summary>
    public class BUILD004_ProductionDebugging : IBuildValidationRule
    {
        public string Id => "BUILD004";
        public ValidationSeverity Severity => ValidationSeverity.Error;

        public ValidationResult Validate(BuildContext context)
        {
            var cfg = context.Configuration;

            bool isProduction = cfg.Environment?.Equals("production", System.StringComparison.OrdinalIgnoreCase) == true;
            if (isProduction && cfg.IsDebuggingEnabled)
                return ValidationResult.Fail(Id, Severity,
                    "isDebuggingEnabled is true for a production environment. Script debugging must be disabled for production releases.");

            return ValidationResult.Pass(Id, Severity);
        }
    }
}
