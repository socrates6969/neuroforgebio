// Error mapping, disposal rules and leak checks (repeated create/free loops, measured as process
// private bytes after a forced GC).
using System;
using System.Diagnostics;
using System.IO;
using System.Text;
using Xunit;

namespace NeuroForge.Tests
{
    public class HandleAndErrorTests
    {
        [Fact]
        public void ErrorsCarryStatusAndMessage()
        {
            var ex = Assert.Throws<NeuroForgeException>(() => Hashing.Canonicalize("{\"a\":1,\"a\":2}"));
            Assert.Equal(Status.Canonical, ex.Status);
            Assert.StartsWith("NF_ERR_CANONICAL: ", ex.Message);
            Assert.False(string.IsNullOrEmpty(ex.NativeMessage));
            Assert.Equal("", ex.Detail);

            var nf = Assert.Throws<NeuroForgeException>(() => Recording.Open(Path.GetTempPath(), "no-such-recording-" + Guid.NewGuid()));
            Assert.NotEqual(Status.Ok, nf.Status);

            Assert.Equal(Status.InvalidArg, Assert.Throws<NeuroForgeException>(() => NeuroForgeCore.ParseDtype("int12")).Status);
            Assert.Equal("NF_OK", NeuroForgeException.StatusName(Status.Ok));
            Assert.Equal("NF_ERR_UNKNOWN", NeuroForgeException.StatusName(9999));
        }

        [Fact]
        public void ManagedArgumentChecksRunBeforeNative()
        {
            Assert.Throws<ArgumentException>(() => Hashing.Canonicalize("\"\ud800\"")); // lone surrogate: not UTF-8
            Assert.Throws<ArgumentException>(() => Wal.OpenEphemeralForTesting(Path.GetTempPath(), "embedded\0nul")); // would truncate the C string
            Assert.Throws<ArgumentException>(() => Wal.Open(Path.GetTempPath(), "s", null, null)); // ABI 1.2: a persistent key is required
            Assert.False(Hashing.IsValidId("blob\0x"));
            Assert.False(Hashing.IsValidId(null));
            Assert.False(Hashing.IsValidId("blob:sha256:xyz"));
            Assert.Throws<ArgumentException>(() => Wal.Open(Path.GetTempPath(), "s", new byte[31], null));
        }

        [Fact]
        public void DisposeIsIdempotentAndUseAfterDisposeThrows()
        {
            var key = DeviceKey.Generate();
            Assert.Equal(32, key.PublicKey.Length);
            key.Dispose();
            key.Dispose();
            Assert.Throws<ObjectDisposedException>(() => key.PublicKey);
            Assert.Throws<ObjectDisposedException>(() => key.Token("t", "d", "s"));
        }

        [Fact]
        public void DtypeHelpers()
        {
            Assert.Equal("float32", NeuroForgeCore.DtypeName(Dtype.Float32));
            Assert.Equal(2, NeuroForgeCore.ItemSize(Dtype.Int16));
            Assert.Equal(Dtype.Float64, NeuroForgeCore.ParseDtype("float64"));
            Assert.Null(NeuroForgeCore.DtypeName((Dtype)99));
            Assert.Equal(0, NeuroForgeCore.ItemSize((Dtype)99));
        }

        private static long PrivateBytesAfterGc()
        {
            for (int i = 0; i < 3; i++) { GC.Collect(); GC.WaitForPendingFinalizers(); }
            using var p = Process.GetCurrentProcess();
            p.Refresh();
            return p.PrivateMemorySize64;
        }

        // Growth allowed over a loop: generous against allocator noise, far below what a leak of
        // even a few dozen bytes per iteration would add over 100k iterations.
        private const long MaxGrowth = 8L << 20;

        private static void AssertNoLeak(string what, int n, Action body)
        {
            for (int i = 0; i < Math.Min(n, 2000); i++) body(); // warm up pools and caches
            long before = PrivateBytesAfterGc();
            for (int i = 0; i < n; i++) body();
            long growth = PrivateBytesAfterGc() - before;
            Assert.True(growth < MaxGrowth, $"{what}: private bytes grew {growth / 1024} KiB over {n} iterations");
        }

        [Fact]
        public void NoLeakInBufferResults()
        {
            byte[] data = Encoding.UTF8.GetBytes(new string('x', 4096));
            AssertNoLeak("BlobId", 100_000, () => Hashing.BlobId(data));
            AssertNoLeak("Canonicalize", 100_000, () => Hashing.Canonicalize("{\"b\":[1,2,3],\"a\":\"text\"}"));
            AssertNoLeak("error path", 100_000, () =>
            {
                try { Hashing.Canonicalize("{\"a\":1,\"a\":2}"); } catch (NeuroForgeException) { }
            });
        }

        [Fact]
        public void NoLeakInHandleCreateFree()
        {
            AssertNoLeak("DeviceKey Dispose", 100_000, () => { using var k = DeviceKey.Generate(); });
            // Finalizer path: never disposed, released by the SafeHandle finalizer.
            AssertNoLeak("DeviceKey finalizer", 100_000, () => DeviceKey.Generate());
            AssertNoLeak("DeviceKey token", 20_000, () =>
            {
                using var k = DeviceKey.Generate();
                k.Token("tenant", "device", "stream", 60);
            });
        }

        [Fact]
        public void NoLeakInRecordingOpenReadFree()
        {
            string root = TestEnv.FixtureDir;
            var buf = new double[64 * 3];
            AssertNoLeak("Recording", 5_000, () =>
            {
                using var r = Recording.Open(root, TestEnv.RecordingId);
                r.Read(0, 64, buf);
            });
        }
    }
}
