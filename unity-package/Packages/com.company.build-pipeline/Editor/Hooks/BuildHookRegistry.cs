using System;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;

namespace Company.BuildPipeline.Editor
{
    /// <summary>
    /// Discovers all <see cref="IBuildHook"/> implementations via reflection, orders them,
    /// and dispatches lifecycle events.
    /// </summary>
    public class BuildHookRegistry
    {
        private readonly List<IBuildHook> _hooks;

        public IReadOnlyList<IBuildHook> Hooks => _hooks;

        public BuildHookRegistry()
        {
            _hooks = DiscoverHooks();
        }

        /// <summary>Allows explicit registration (useful in tests or when auto-discovery is skipped).</summary>
        public BuildHookRegistry(IEnumerable<IBuildHook> hooks)
        {
            _hooks = hooks.OrderBy(h => h.Order).ToList();
        }

        public void RunBeforeValidation(BuildContext context)
        {
            foreach (var hook in _hooks)
            {
                try
                {
                    Debug.Log($"[BuildPipeline:Hook] BeforeValidation → {hook.GetType().Name}");
                    hook.BeforeValidation(context);
                }
                catch (Exception ex)
                {
                    Debug.LogError($"[BuildPipeline:Hook] BeforeValidation FAILED in {hook.GetType().Name}: {ex.Message}");
                    throw;
                }
            }
        }

        public void RunBeforeBuild(BuildContext context)
        {
            foreach (var hook in _hooks)
            {
                try
                {
                    Debug.Log($"[BuildPipeline:Hook] BeforeBuild → {hook.GetType().Name}");
                    hook.BeforeBuild(context);
                }
                catch (Exception ex)
                {
                    Debug.LogError($"[BuildPipeline:Hook] BeforeBuild FAILED in {hook.GetType().Name}: {ex.Message}");
                    throw;
                }
            }
        }

        public void RunAfterBuild(BuildContext context, BuildExecutionResult result)
        {
            foreach (var hook in _hooks)
            {
                try
                {
                    Debug.Log($"[BuildPipeline:Hook] AfterBuild → {hook.GetType().Name}");
                    hook.AfterBuild(context, result);
                }
                catch (Exception ex)
                {
                    // Post-build hooks should not abort the pipeline; log and continue.
                    Debug.LogError($"[BuildPipeline:Hook] AfterBuild FAILED in {hook.GetType().Name}: {ex.Message}");
                }
            }
        }

        /// <summary>Returns the type names of all registered hooks (used by BUILD014).</summary>
        public IEnumerable<string> RegisteredTypeNames()
            => _hooks.Select(h => h.GetType().Name);

        private static List<IBuildHook> DiscoverHooks()
        {
            var hookType = typeof(IBuildHook);
            var instances = new List<IBuildHook>();

            foreach (var assembly in AppDomain.CurrentDomain.GetAssemblies())
            {
                try
                {
                    foreach (var type in assembly.GetTypes())
                    {
                        if (type.IsInterface || type.IsAbstract) continue;
                        if (!hookType.IsAssignableFrom(type)) continue;
                        if (type == hookType) continue;

                        try
                        {
                            var instance = (IBuildHook)Activator.CreateInstance(type);
                            instances.Add(instance);
                        }
                        catch (Exception ex)
                        {
                            Debug.LogWarning($"[BuildPipeline:Hook] Could not instantiate {type.FullName}: {ex.Message}");
                        }
                    }
                }
                catch
                {
                    // Some assemblies are not reflectable; skip them.
                }
            }

            return instances.OrderBy(h => h.Order).ToList();
        }
    }
}
