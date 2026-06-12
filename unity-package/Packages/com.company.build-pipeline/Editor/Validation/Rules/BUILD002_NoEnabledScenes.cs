namespace Company.BuildPipeline.Editor.Validation.Rules
{
    /// <summary>
    /// Ensures at least one scene is included in the build.
    /// </summary>
    public class BUILD002_NoEnabledScenes : IBuildValidationRule
    {
        public string Id => "BUILD002";
        public ValidationSeverity Severity => ValidationSeverity.Error;

        public ValidationResult Validate(BuildContext context)
        {
            var scenes = context.Configuration.Scenes;

            if (scenes == null || scenes.Count == 0)
                return ValidationResult.Fail(Id, Severity, "The scenes list is empty. At least one scene is required.");

            int nonEmpty = 0;
            foreach (var s in scenes)
                if (!string.IsNullOrWhiteSpace(s)) nonEmpty++;

            if (nonEmpty == 0)
                return ValidationResult.Fail(Id, Severity, "All scene entries are blank strings.");

            return ValidationResult.Pass(Id, Severity, $"{nonEmpty} scene(s) configured.");
        }
    }
}
