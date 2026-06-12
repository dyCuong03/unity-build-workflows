namespace Company.BuildPipeline.Editor.Validation.Rules
{
    /// <summary>
    /// Prevents shipping a development build to production.
    /// </summary>
    public class BUILD003_ProductionDevBuild : IBuildValidationRule
    {
        public string Id => "BUILD003";
        public ValidationSeverity Severity => ValidationSeverity.Error;

        public ValidationResult Validate(BuildContext context)
        {
            var cfg = context.Configuration;

            bool isProduction = cfg.Environment?.Equals("production", System.StringComparison.OrdinalIgnoreCase) == true;
            if (isProduction && cfg.IsDevelopmentBuild)
                return ValidationResult.Fail(Id, Severity,
                    "isDevelopmentBuild is true for a production environment. This is not allowed.");

            return ValidationResult.Pass(Id, Severity);
        }
    }
}
