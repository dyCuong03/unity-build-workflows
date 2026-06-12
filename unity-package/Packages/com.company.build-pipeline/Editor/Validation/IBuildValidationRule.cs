namespace Company.BuildPipeline.Editor
{
    /// <summary>
    /// A single named validation rule evaluated against the current <see cref="BuildContext"/>.
    /// </summary>
    public interface IBuildValidationRule
    {
        /// <summary>Stable rule identifier, e.g. "BUILD001".</summary>
        string Id { get; }

        /// <summary>Default severity; implementations may escalate on a per-result basis.</summary>
        ValidationSeverity Severity { get; }

        ValidationResult Validate(BuildContext context);
    }
}
