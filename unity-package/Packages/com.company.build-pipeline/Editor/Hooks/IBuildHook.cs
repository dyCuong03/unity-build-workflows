namespace Company.BuildPipeline.Editor
{
    /// <summary>
    /// Lifecycle hook called at defined points during the build pipeline.
    /// Implementations are discovered via <see cref="BuildHookRegistry"/>.
    /// </summary>
    public interface IBuildHook
    {
        /// <summary>Ascending execution order; lower runs first.</summary>
        int Order { get; }

        void BeforeValidation(BuildContext context);
        void BeforeBuild(BuildContext context);
        void AfterBuild(BuildContext context, BuildExecutionResult result);
    }
}
