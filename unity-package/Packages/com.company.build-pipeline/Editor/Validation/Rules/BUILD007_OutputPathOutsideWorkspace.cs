using System;
using System.IO;

namespace Company.BuildPipeline.Editor.Validation.Rules
{
    /// <summary>
    /// Prevents output artefacts from being written outside the configured workspace root,
    /// which could overwrite system files or bypass CI artefact collection.
    /// </summary>
    public class BUILD007_OutputPathOutsideWorkspace : IBuildValidationRule
    {
        public string Id => "BUILD007";
        public ValidationSeverity Severity => ValidationSeverity.Error;

        public ValidationResult Validate(BuildContext context)
        {
            var cfg = context.Configuration;

            if (string.IsNullOrWhiteSpace(cfg.Workspace))
                return ValidationResult.Pass(Id, Severity, "No workspace defined — output path containment check skipped.");

            if (string.IsNullOrWhiteSpace(cfg.OutputPath))
                return ValidationResult.Fail(Id, Severity, "outputPath is empty.");

            var workspace = Path.GetFullPath(cfg.Workspace).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar) + Path.DirectorySeparatorChar;
            var outputPath = Path.GetFullPath(cfg.OutputPath).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar) + Path.DirectorySeparatorChar;

            if (!outputPath.StartsWith(workspace, StringComparison.OrdinalIgnoreCase))
                return ValidationResult.Fail(Id, Severity,
                    $"outputPath '{cfg.OutputPath}' resolves to '{outputPath.TrimEnd(Path.DirectorySeparatorChar)}' which is outside workspace '{cfg.Workspace}'.");

            return ValidationResult.Pass(Id, Severity, "outputPath is within workspace.");
        }
    }
}
