using UnityEditor;

namespace Company.BuildPipeline.Editor
{
    /// <summary>
    /// Encapsulates all platform-specific PlayerSettings configuration and build invocation.
    /// </summary>
    public interface IPlatformBuilder
    {
        BuildTarget Target { get; }

        /// <summary>Returns true when this builder can handle the given context.</summary>
        bool Supports(BuildContext context);

        /// <summary>Applies PlayerSettings and any platform-specific options.</summary>
        void Configure(BuildContext context);

        /// <summary>Invokes BuildPipeline.BuildPlayer and returns a structured result.</summary>
        BuildExecutionResult Build(BuildContext context);
    }
}
