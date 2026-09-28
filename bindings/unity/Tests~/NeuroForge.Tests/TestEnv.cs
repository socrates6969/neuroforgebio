using System;
using System.IO;
using System.Reflection;
using System.Runtime.CompilerServices;
using System.Runtime.InteropServices;
using System.Text.Json;

[assembly: Xunit.CollectionBehavior(DisableTestParallelization = true)]

namespace NeuroForge.Tests
{
    internal static class TestEnv
    {
        // Resolve "neuroforge" for the runtime assembly from NF_NATIVE_DIR (or <repo>/target/debug),
        // so the test loads exactly the DLL nfb-cabi's build produced; no copy, no PATH changes.
        [ModuleInitializer]
        internal static void Init()
        {
            NativeLibrary.SetDllImportResolver(typeof(Hashing).Assembly, (name, asm, path) =>
            {
                if (name != "neuroforge") return IntPtr.Zero;
                string file = Path.Combine(NativeDir, OperatingSystem.IsWindows() ? "neuroforge.dll"
                    : OperatingSystem.IsMacOS() ? "libneuroforge.dylib" : "libneuroforge.so");
                if (!File.Exists(file)) throw new DllNotFoundException($"{file} not found: build bindings/c or set NF_NATIVE_DIR");
                return NativeLibrary.Load(file);
            });
        }

        internal static string RepoRoot
        {
            get
            {
                var d = new DirectoryInfo(AppContext.BaseDirectory);
                while (d != null && !File.Exists(Path.Combine(d.FullName, "Cargo.lock"))) d = d.Parent;
                return d?.FullName ?? throw new InvalidOperationException("repository root (Cargo.lock) not found above " + AppContext.BaseDirectory);
            }
        }

        internal static string NativeDir =>
            Environment.GetEnvironmentVariable("NF_NATIVE_DIR") is { Length: > 0 } d ? d : Path.Combine(RepoRoot, "target", "debug");

        internal static string FixtureDir =>
            Environment.GetEnvironmentVariable("NF_FIXTURE_DIR") is { Length: > 0 } d ? d
            : throw new InvalidOperationException("set NF_FIXTURE_DIR to the output of `cargo run -p neuroforge-c --example make_fixture -- <dir>`");

        internal static JsonElement Vectors(string file)
        {
            string p = Path.Combine(RepoRoot, "spec", "test-vectors", file);
            return JsonDocument.Parse(File.ReadAllText(p)).RootElement;
        }

        internal static byte[] Hex(string h) => Convert.FromHexString(h);

        // Fixture formulas, copied from bindings/c/tests/fixture/mod.rs.
        internal const string RecordingId = "rec-001";
        internal const long NSamples = 1000;
        internal static readonly string[] Channels = { "Fz", "Cz", "Pz" };
        internal const double Sfreq = 250.0;
        internal static short Sample(long i, long c) => (short)((i * 3 + c) % 2000 - 1000);
        internal static double Timestamp(long i) => 100.0 + i / Sfreq;
    }
}
