namespace Company.BuildPipeline.Editor
{
    public enum ValidationSeverity
    {
        Info,
        Warning,
        Error
    }

    /// <summary>
    /// Outcome of a single <see cref="IBuildValidationRule"/> evaluation.
    /// </summary>
    public class ValidationResult
    {
        public string RuleId { get; }
        public ValidationSeverity Severity { get; }
        public bool Passed { get; }
        public string Message { get; }

        public ValidationResult(string ruleId, ValidationSeverity severity, bool passed, string message)
        {
            RuleId = ruleId;
            Severity = severity;
            Passed = passed;
            Message = message;
        }

        public static ValidationResult Pass(string ruleId, ValidationSeverity severity, string message = "OK")
            => new ValidationResult(ruleId, severity, true, message);

        public static ValidationResult Fail(string ruleId, ValidationSeverity severity, string message)
            => new ValidationResult(ruleId, severity, false, message);
    }
}
