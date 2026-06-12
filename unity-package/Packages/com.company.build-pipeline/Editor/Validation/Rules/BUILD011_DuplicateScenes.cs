using System;
using System.Collections.Generic;

namespace Company.BuildPipeline.Editor.Validation.Rules
{
    /// <summary>
    /// Detects duplicate scene paths in the scenes list, which would cause Unity to include
    /// a scene multiple times or fail silently.
    /// </summary>
    public class BUILD011_DuplicateScenes : IBuildValidationRule
    {
        public string Id => "BUILD011";
        public ValidationSeverity Severity => ValidationSeverity.Error;

        public ValidationResult Validate(BuildContext context)
        {
            var scenes = context.Configuration.Scenes;
            if (scenes == null || scenes.Count == 0)
                return ValidationResult.Pass(Id, Severity, "No scenes to check.");

            var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            var duplicates = new List<string>();

            foreach (var scene in scenes)
            {
                if (string.IsNullOrWhiteSpace(scene)) continue;
                if (!seen.Add(scene))
                    duplicates.Add(scene);
            }

            if (duplicates.Count > 0)
                return ValidationResult.Fail(Id, Severity,
                    $"Duplicate scene path(s) detected: {string.Join(", ", duplicates)}.");

            return ValidationResult.Pass(Id, Severity, "No duplicate scenes.");
        }
    }
}
