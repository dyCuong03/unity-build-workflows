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
            var identifier = context.Configuration.AppIdentifier;

            if (string.IsNullOrWhiteSpace(identifier))
                return ValidationResult.Fail(Id, Severity, "appIdentifier is empty.");

            if (!ValidPattern.IsMatch(identifier))
                return ValidationResult.Fail(Id, Severity,
                    $"appIdentifier '{identifier}' is not a valid reverse-DNS identifier (e.g. com.company.game).");

            return ValidationResult.Pass(Id, Severity, $"appIdentifier '{identifier}' is valid.");
        }
    }
}
