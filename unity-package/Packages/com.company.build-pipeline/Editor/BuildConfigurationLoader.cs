using System;
using System.Collections.Generic;
using System.IO;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using UnityEngine;

namespace Company.BuildPipeline.Editor
{
    /// <summary>
    /// Loads and merges layered JSON configuration files.
    /// Merge precedence (highest wins): CLI overrides > environment.json > base.json > code defaults.
    /// </summary>
    public class BuildConfigurationLoader
    {
        /// <summary>
        /// Loads, merges, and returns the resolved <see cref="BuildConfiguration"/>.
        /// </summary>
        /// <param name="buildConfigDir">Directory that contains base.json and environment subdirectories.</param>
        /// <param name="environment">Active environment name (e.g. "production").</param>
        /// <param name="cliOverrides">Key/value pairs from CLI arguments (may be null).</param>
        public BuildConfiguration Load(string buildConfigDir, string environment, Dictionary<string, string> cliOverrides = null)
        {
            if (string.IsNullOrEmpty(buildConfigDir))
                throw new ArgumentNullException(nameof(buildConfigDir));

            // --- 1. base.json -------------------------------------------------
            var merged = LoadJsonFile(Path.Combine(buildConfigDir, "base.json")) ?? new JObject();

            // --- 2. environment.json ------------------------------------------
            if (!string.IsNullOrEmpty(environment))
            {
                // Support both flat layout (environments/production.json) and
                // nested layout (environments/production/config.json).
                var envFlat = Path.Combine(buildConfigDir, "environments", $"{environment}.json");
                var envNested = Path.Combine(buildConfigDir, "environments", environment, "config.json");

                JObject envJson = null;
                if (File.Exists(envFlat))
                    envJson = LoadJsonFile(envFlat);
                else if (File.Exists(envNested))
                    envJson = LoadJsonFile(envNested);

                if (envJson != null)
                    DeepMerge(merged, envJson);
            }

            // --- 3. CLI overrides (dot-notation keys) -------------------------
            if (cliOverrides != null && cliOverrides.Count > 0)
            {
                var cliJson = FlattenCliOverrides(cliOverrides);
                DeepMerge(merged, cliJson);
            }

            // --- 4. Stamp the active environment into the config --------------
            if (!string.IsNullOrEmpty(environment))
                merged["environment"] = environment;

            var config = merged.ToObject<BuildConfiguration>(JsonSerializer.Create(JsonSettings()));
            Debug.Log($"[BuildPipeline:Config] Loaded configuration for environment '{environment}'.");
            return config;
        }

        // ── Helpers ───────────────────────────────────────────────────────────

        private static JObject LoadJsonFile(string path)
        {
            if (!File.Exists(path))
            {
                Debug.LogWarning($"[BuildPipeline:Config] Config file not found: {path}");
                return null;
            }

            try
            {
                var text = File.ReadAllText(path);
                return JObject.Parse(text);
            }
            catch (Exception ex)
            {
                throw new InvalidOperationException($"Failed to parse config file '{path}': {ex.Message}", ex);
            }
        }

        /// <summary>
        /// Recursively merges <paramref name="patch"/> into <paramref name="target"/>.
        /// Arrays are replaced (not appended). Scalars are overwritten.
        /// </summary>
        internal static void DeepMerge(JObject target, JObject patch)
        {
            foreach (var property in patch.Properties())
            {
                if (target[property.Name] is JObject existingObj && property.Value is JObject patchObj)
                {
                    DeepMerge(existingObj, patchObj);
                }
                else
                {
                    target[property.Name] = property.Value.DeepClone();
                }
            }
        }

        /// <summary>
        /// Converts flat CLI key=value pairs (supporting dot notation) into a nested JObject.
        /// E.g. "signingConfig.keystorePath" = "foo.keystore" becomes { signingConfig: { keystorePath: "foo.keystore" } }.
        /// </summary>
        internal static JObject FlattenCliOverrides(Dictionary<string, string> overrides)
        {
            var root = new JObject();
            foreach (var kv in overrides)
            {
                if (string.IsNullOrEmpty(kv.Key)) continue;

                var parts = kv.Key.Split('.');
                JObject current = root;
                for (int i = 0; i < parts.Length - 1; i++)
                {
                    if (current[parts[i]] is not JObject child)
                    {
                        child = new JObject();
                        current[parts[i]] = child;
                    }
                    current = child;
                }
                current[parts[parts.Length - 1]] = JToken.FromObject(kv.Value);
            }
            return root;
        }

        private static JsonSerializerSettings JsonSettings() => new JsonSerializerSettings
        {
            MissingMemberHandling = MissingMemberHandling.Ignore,
            NullValueHandling = NullValueHandling.Ignore
        };
    }
}
