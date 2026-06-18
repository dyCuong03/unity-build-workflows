using System;
using System.Collections.Generic;
using System.Linq;
using UnityEditor;
using UnityEngine;

namespace Company.BuildPipeline.Editor
{
    /// <summary>
    /// Main entry point for the build pipeline.
    /// Invoked from the Unity CLI: -executeMethod Company.BuildPipeline.Editor.BuildCommand.Execute
    ///
    /// STABLE NEUTRAL IDENTITY — DO NOT RENAME
    /// ----------------------------------------
    /// The namespace <c>Company.BuildPipeline</c>, the package ID
    /// <c>com.company.build-pipeline</c>, and the execute-method
    /// <c>Company.BuildPipeline.Editor.BuildCommand.Execute</c> are intentionally
    /// generic placeholders.  They serve as a stable, org-neutral contract
    /// between this toolkit and any consumer Unity project.
    ///
    /// The workflow toolkit hardcodes this execute-method in entrypoint.sh and
    /// run_unity_ios.sh.  Renaming it would silently break all builds.  If you
    /// fork this package for your organisation, keep this exact class and method
    /// name, or update the execute-method in all workflow entry points atomically.
    ///
    /// Supported command-line arguments:
    ///   -buildConfig    Path to the build config directory (contains base.json).
    ///   -environment    Environment name: development | staging | production
    ///   -targetPlatform android | ios | windows | webgl
    ///   -outputPath     Where build artefacts are written.
    ///   -releaseTag     Optional VCS tag (e.g. v1.2.3) stamped into metadata.
    /// </summary>
    public static class BuildCommand
    {
        // ── Platform builder registry ─────────────────────────────────────────

        private static readonly List<IPlatformBuilder> PlatformBuilders = new List<IPlatformBuilder>
        {
            new AndroidBuilder(),
            new IOSBuilder(),
            new WindowsBuilder(),
            new WebGLBuilder()
        };

        // ── Entry point ───────────────────────────────────────────────────────

        public static void Execute()
        {
            Log("Stage", "START");

            BuildContext context = null;

            try
            {
                // ── 1. Parse CLI arguments ─────────────────────────────────────
                Log("Stage", "ParseArgs");
                var args = ParseCliArgs();

                // ── 2. Load + merge config ─────────────────────────────────────
                Log("Stage", "LoadConfig");
                var loader = new BuildConfigurationLoader();
                var config = loader.Load(
                    buildConfigDir: RequireArg(args, "-buildConfig"),
                    environment:    GetArg(args, "-environment", "development"),
                    cliOverrides:   BuildCliOverrides(args)
                );

                // CLI direct overrides (higher priority than JSON hierarchy).
                ApplyDirectCliOverrides(config, args);

                // ── 3. Resolve platform builder ────────────────────────────────
                Log("Stage", "ResolvePlatform");
                var builder = ResolvePlatformBuilder(config.TargetPlatform);
                context = new BuildContext
                {
                    Configuration = config,
                    Target = builder.Target
                };

                // ── 4. Create hook registry and store it for BUILD014 ──────────
                Log("Stage", "LoadHooks");
                var hookRegistry = new BuildHookRegistry();
                context.Metadata["hookRegistry"] = hookRegistry;

                // ── 5. BeforeValidation hooks ──────────────────────────────────
                Log("Stage", "HooksBeforeValidation");
                hookRegistry.RunBeforeValidation(context);

                // ── 6. Validate ────────────────────────────────────────────────
                Log("Stage", "Validate");
                var validator = new BuildValidator();
                bool validationPassed = validator.Validate(context);

                if (!validationPassed)
                {
                    Log("Stage", "FAIL — validation errors present");
                    EditorApplication.Exit(1);
                    return;
                }

                // ── 7. Configure platform ──────────────────────────────────────
                Log("Stage", "Configure");
                builder.Configure(context);

                // ── 8. BeforeBuild hooks ───────────────────────────────────────
                Log("Stage", "HooksBeforeBuild");
                hookRegistry.RunBeforeBuild(context);

                // ── 9. Build ───────────────────────────────────────────────────
                Log("Stage", "Build");
                var result = builder.Build(context);
                context.ExecutionResult = result;

                // ── 10. AfterBuild hooks ───────────────────────────────────────
                Log("Stage", "HooksAfterBuild");
                hookRegistry.RunAfterBuild(context, result);

                // ── 11. Reports + metadata ─────────────────────────────────────
                Log("Stage", "Reports");
                new BuildReportExporter().Export(context);
                new BuildMetadataWriter().Write(context);

                // ── 12. Exit ───────────────────────────────────────────────────
                if (!result.Success)
                {
                    Debug.LogError($"[BuildPipeline:Stage] BUILD FAILED — {result.ErrorMessage}");
                    EditorApplication.Exit(1);
                }
                else
                {
                    Log("Stage", $"SUCCESS — output: {result.OutputPath} ({result.OutputSizeBytes} bytes)");
                    EditorApplication.Exit(0);
                }
            }
            catch (Exception ex)
            {
                Debug.LogError($"[BuildPipeline:Stage] UNHANDLED EXCEPTION — {ex.GetType().Name}: {ex.Message}\n{ex.StackTrace}");

                // Attempt to write reports even on failure so CI has something to collect.
                if (context != null)
                {
                    try { new BuildReportExporter().Export(context); } catch { }
                    try { new BuildMetadataWriter().Write(context); }  catch { }
                }

                EditorApplication.Exit(1);
            }
        }

        // ── Helpers ───────────────────────────────────────────────────────────

        private static void Log(string category, string message)
            => Debug.Log($"[BuildPipeline:{category}] {message}");

        private static Dictionary<string, string> ParseCliArgs()
        {
            var result = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
            var args = Environment.GetCommandLineArgs();

            for (int i = 0; i < args.Length - 1; i++)
            {
                if (args[i].StartsWith("-"))
                    result[args[i]] = args[i + 1];
            }
            return result;
        }

        private static string GetArg(Dictionary<string, string> args, string key, string fallback = null)
            => args.TryGetValue(key, out var val) ? val : fallback;

        private static string RequireArg(Dictionary<string, string> args, string key)
        {
            if (!args.TryGetValue(key, out var val) || string.IsNullOrWhiteSpace(val))
                throw new ArgumentException($"Required CLI argument '{key}' is missing.");
            return val;
        }

        /// <summary>
        /// Builds a dictionary of config-path overrides from explicit named CLI args.
        /// These are merged as top-level JSON keys (not dot-notation).
        /// </summary>
        private static Dictionary<string, string> BuildCliOverrides(Dictionary<string, string> args)
        {
            var overrides = new Dictionary<string, string>();

            if (args.TryGetValue("-outputPath", out var outputPath))
                overrides["outputPath"] = outputPath;

            if (args.TryGetValue("-targetPlatform", out var platform))
                overrides["targetPlatform"] = platform;

            if (args.TryGetValue("-releaseTag", out var tag))
                overrides["releaseTag"] = tag;

            return overrides;
        }

        private static void ApplyDirectCliOverrides(BuildConfiguration config, Dictionary<string, string> args)
        {
            if (args.TryGetValue("-outputPath", out var outputPath) && !string.IsNullOrWhiteSpace(outputPath))
                config.OutputPath = outputPath;

            if (args.TryGetValue("-targetPlatform", out var platform) && !string.IsNullOrWhiteSpace(platform))
                config.TargetPlatform = platform;

            if (args.TryGetValue("-releaseTag", out var tag) && !string.IsNullOrWhiteSpace(tag))
                config.ReleaseTag = tag;
        }

        private static IPlatformBuilder ResolvePlatformBuilder(string targetPlatform)
        {
            if (string.IsNullOrWhiteSpace(targetPlatform))
                throw new ArgumentException("targetPlatform is not set in configuration.");

            var builder = PlatformBuilders.FirstOrDefault(b =>
                b.Target.ToString().Equals(targetPlatform, StringComparison.OrdinalIgnoreCase) ||
                MatchesPlatformAlias(b, targetPlatform));

            if (builder == null)
                throw new NotSupportedException($"No platform builder found for targetPlatform '{targetPlatform}'. " +
                    $"Available: {string.Join(", ", PlatformBuilders.Select(b => b.Target))}");

            return builder;
        }

        private static bool MatchesPlatformAlias(IPlatformBuilder builder, string name)
        {
            // Create a temporary context stub to call Supports().
            var stubCtx = new BuildContext
            {
                Configuration = new BuildConfiguration { TargetPlatform = name },
                Target = builder.Target
            };
            return builder.Supports(stubCtx);
        }
    }
}
