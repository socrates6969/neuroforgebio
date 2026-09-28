// Paths and fixture formulas for the EditMode tests (run by Samples~/SdkTestProject/run-tests.cmd).
using System;
using System.IO;
using Newtonsoft.Json.Linq;
using NUnit.Framework;

namespace NeuroForge.Tests.Editor
{
    internal static class TestPaths
    {
        // bindings/unity, wherever the package is referenced from.
        internal static string PackageRoot =>
            UnityEditor.PackageManager.PackageInfo.FindForAssembly(typeof(Hashing).Assembly)?.resolvedPath
            ?? throw new InvalidOperationException("com.neuroforge.sdk package not found");

        internal static string RepoRoot => Path.GetFullPath(Path.Combine(PackageRoot, "..", ".."));

        internal static string FixtureDir
        {
            get
            {
                string d = Environment.GetEnvironmentVariable("NF_FIXTURE_DIR");
                if (string.IsNullOrEmpty(d)) d = Path.Combine(RepoRoot, "target", "unity-tests", "fixture");
                if (!Directory.Exists(Path.Combine(d, RecordingId)))
                    Assert.Fail($"fixture not found at {d}: run Samples~/SdkTestProject/run-tests.cmd or set NF_FIXTURE_DIR");
                return d;
            }
        }

        // No date parsing: a date-like string must stay the exact string the vector holds.
        internal static JObject Vectors(string file)
        {
            string text = File.ReadAllText(Path.Combine(RepoRoot, "spec", "test-vectors", file));
            using var r = new Newtonsoft.Json.JsonTextReader(new StringReader(text))
            {
                DateParseHandling = Newtonsoft.Json.DateParseHandling.None,
                FloatParseHandling = Newtonsoft.Json.FloatParseHandling.Double,
            };
            return JObject.Load(r);
        }

        // Compact JSON text of a token. The core canonicalises its input, so re-serialisation
        // (whitespace, number spelling) does not change any ID.
        internal static string Json(JToken t) => t.ToString(Newtonsoft.Json.Formatting.None);

        internal static byte[] Hex(string h)
        {
            var b = new byte[h.Length / 2];
            for (int i = 0; i < b.Length; i++) b[i] = Convert.ToByte(h.Substring(i * 2, 2), 16);
            return b;
        }

        // Fixture formulas, copied from bindings/c/tests/fixture/mod.rs.
        internal const string RecordingId = "rec-001";
        internal const long NSamples = 1000;
        internal static readonly string[] Channels = { "Fz", "Cz", "Pz" };
        internal const double Sfreq = 250.0;
        internal static short Sample(long i, long c) => (short)((i * 3 + c) % 2000 - 1000);
        internal static double Timestamp(long i) => 100.0 + i / Sfreq;

        internal static string TempDir()
        {
            string p = Path.Combine(Path.GetTempPath(), "nf-unity-" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(p);
            return p;
        }
    }
}
