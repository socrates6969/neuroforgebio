// Recordings, replay, capture, provenance, handle disposal and leak loops, inside the Unity editor.
using System;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Text;
using System.Threading;
using NeuroForge.Replay;
using NUnit.Framework;
using static NeuroForge.Tests.Editor.TestPaths;

namespace NeuroForge.Tests.Editor
{
    public class RecordingAndReplayTests
    {
        private static Recording Open() => Recording.Open(FixtureDir, RecordingId);

        [Test]
        public void InfoAndExactValues()
        {
            using var r = Open();
            Assert.AreEqual(NSamples, r.SampleCount);
            Assert.AreEqual(3, r.ChannelCount);
            Assert.AreEqual(Sfreq, r.SampleRate);
            Assert.AreEqual(Dtype.Int16, r.Dtype);
            CollectionAssert.AreEqual(Channels, r.ChannelNames.ToArray());
            var d = new double[NSamples * 3];
            var s = new double[NSamples * 3];
            var f = new float[NSamples * 3];
            Assert.AreEqual((int)NSamples, r.Read(0, (int)NSamples, d));
            r.ReadStored(0, (int)NSamples, s);
            r.Read(0, (int)NSamples, f);
            for (long i = 0; i < NSamples; i++)
                for (int c = 0; c < 3; c++)
                {
                    double want = Sample(i, c); // unit scale in the fixture: physical == stored
                    Assert.AreEqual(want, d[i * 3 + c]);
                    Assert.AreEqual(want, s[i * 3 + c]);
                    Assert.AreEqual((float)want, f[i * 3 + c]);
                }
            var ts = new double[NSamples];
            r.ReadTimestamps(0, (int)NSamples, ts);
            for (int i = 0; i < ts.Length; i++) Assert.AreEqual(Timestamp(i), ts[i]);
            Assert.AreEqual(10, r.Read(990, 100, d));
            Assert.AreEqual(0, r.Read(1000, 10, d));

            // Split reads (ABI 1.2 caps one native read at 1 GiB): force 7-row pieces and compare.
            r.MaxStoredBytesPerCall = 42; // 7 rows x 3 ch x 2 B
            var d2 = new double[NSamples * 3];
            var raw1 = new byte[NSamples * 6];
            var ts2 = new double[NSamples];
            Assert.AreEqual((int)NSamples - 5, r.Read(5, (int)NSamples, d2));
            for (long i = 5; i < NSamples; i++)
                for (int c = 0; c < 3; c++) Assert.AreEqual((double)Sample(i, c), d2[(i - 5) * 3 + c]);
            r.MaxStoredBytesPerCall = 1; // below one row: one row per call
            r.ReadRaw(0, (int)NSamples, raw1);
            for (long i = 0; i < NSamples; i++) Assert.AreEqual(Sample(i, 2), BitConverter.ToInt16(raw1, (int)(i * 6 + 4)));
            r.ReadTimestamps(0, (int)NSamples, ts2);
            CollectionAssert.AreEqual(ts, ts2);
            Assert.Throws<ArgumentOutOfRangeException>(() => r.MaxStoredBytesPerCall = 0);
        }

        [Test]
        public void ReplayRoundTripIsExact()
        {
            using var w = new ReplayWorker(Open(), double.PositiveInfinity, blockSamples: 37, maxQueuedBlocks: 4,
                                           backpressure: Backpressure.Block, ownsRecording: true);
            w.Start();
            long next = 0;
            var sw = Stopwatch.StartNew();
            while (next < NSamples && sw.Elapsed < TimeSpan.FromSeconds(30))
            {
                if (!w.TryDequeue(out SampleBlock b)) { Assert.IsNull(w.Error); Thread.Sleep(1); continue; }
                Assert.AreEqual(next, b.FirstSample);
                for (int row = 0; row < b.Rows; row++)
                    for (int c = 0; c < 3; c++)
                        Assert.AreEqual((float)Sample(b.FirstSample + row, c), b[row, c]);
                next += b.Rows;
            }
            Assert.AreEqual(NSamples, next);
            w.Stop();
            Assert.IsTrue(w.Completed);
            Assert.AreEqual(0, w.DroppedBlocks);
        }

        [Test]
        public void ReplayIsPacedAndStopsPromptly()
        {
            using (var w = new ReplayWorker(Open(), 4.0, blockSamples: 25, ownsRecording: true))
            {
                var sw = Stopwatch.StartNew();
                w.Start();
                long rows = 0;
                while (!(w.Completed && w.QueuedBlocks == 0) && sw.Elapsed < TimeSpan.FromSeconds(10))
                {
                    while (w.TryDequeue(out SampleBlock b)) rows += b.Rows;
                    Thread.Sleep(5);
                }
                Assert.AreEqual(NSamples, rows);
                Assert.That(sw.Elapsed.TotalSeconds, Is.InRange(0.9, 2.0));
            }
            using (var w = new ReplayWorker(Open(), double.PositiveInfinity, loop: true, blockSamples: 100, maxQueuedBlocks: 8,
                                            backpressure: Backpressure.Block, ownsRecording: true))
            {
                w.Start();
                int maxLoop = 0;
                var sw = Stopwatch.StartNew();
                while (maxLoop < 2 && sw.Elapsed < TimeSpan.FromSeconds(10))
                    if (w.TryDequeue(out SampleBlock b)) maxLoop = Math.Max(maxLoop, b.Loop);
                Assert.AreEqual(2, maxLoop);
                var stop = Stopwatch.StartNew();
                w.Stop();
                Assert.Less(stop.Elapsed.TotalSeconds, 1.0);
            }
        }

        [Test]
        public void DropOldestKeepsMemoryBounded()
        {
            using var w = new ReplayWorker(Open(), double.PositiveInfinity, blockSamples: 10, maxQueuedBlocks: 5,
                                           backpressure: Backpressure.DropOldest, ownsRecording: true);
            w.Start();
            var sw = Stopwatch.StartNew();
            while (!w.Completed && sw.Elapsed < TimeSpan.FromSeconds(10)) Thread.Sleep(5);
            Assert.IsTrue(w.Completed);
            Assert.AreEqual(5, w.QueuedBlocks);
            Assert.AreEqual(95, w.DroppedBlocks);
        }

        [Test]
        public void ChunkCacheReturnsVerifiedFixtureChunk()
        {
            using var cache = ChunkCache.Open(Path.Combine(FixtureDir, "cache"));
            string id = Hashing.ChunkId<float>(Dtype.Float32, new ulong[] { 2, 3 }, new float[] { 0.5f, 1.5f, 2.5f, 3.5f, 4.5f, 5.5f });
            Chunk c = cache.TryGet(id);
            Assert.IsNotNull(c);
            Assert.AreEqual(id, Hashing.ChunkId(c.Dtype, c.Shape, c.Data));
        }
    }

    public class CaptureAndProvenanceTests
    {
        [Test]
        public void FixtureToWriterRoundTrip()
        {
            string dir = TempDir();
            try
            {
                using var rec = Recording.Open(FixtureDir, RecordingId);
                using var key = DeviceKey.Generate();
                using var wal = Wal.Open(dir, "stream-1", Enumerable.Range(0, 32).Select(i => (byte)i).ToArray(), null, fsync: false);
                using var w = new StreamWriter("stream-1", Dtype.Int16, 3, 100, key, wal);
                var raw = new byte[64 * 6];
                var ts = new double[64];
                int chunks = 0;
                for (long pos = 0; pos < rec.SampleCount; pos += 64)
                {
                    int rows = rec.ReadRaw(pos, 64, raw);
                    rec.ReadTimestamps(pos, rows, ts);
                    chunks += w.Push<short>(System.Runtime.InteropServices.MemoryMarshal.Cast<byte, short>(raw.AsSpan(0, rows * 6)), ts.AsSpan(0, rows));
                }
                Assert.AreEqual(10, chunks);
                Assert.AreEqual(1000UL, w.Stats.Samples);
                Assert.AreEqual(10, wal.Count);
            }
            finally { Directory.Delete(dir, true); }
        }

        // ABI 1.2: a DPAPI-keyed WAL keeps its unsent records across close/reopen (the point of
        // requiring a persistent key); the ephemeral one is test-only and still opens.
        [Test]
        public void PersistentKeyedWalSurvivesReopen()
        {
            string dir = TempDir();
            try
            {
                string keyFile = Path.Combine(dir, "wal.key");
                using (var key = DeviceKey.Generate())
                using (var wal = Wal.Open(dir, "s", null, keyFile, fsync: true))
                using (var w = new StreamWriter("s", Dtype.Float32, 1, 2, key, wal))
                {
                    Assert.AreEqual(2, w.Push<float>(new[] { 1f, 2f, 3f, 4f }, new[] { 1.0, 1.1, 1.2, 1.3 }));
                    Assert.AreEqual(2, wal.Count);
                }
                Assert.IsTrue(File.Exists(keyFile), "DPAPI key file created on first use");
                using (var again = Wal.Open(dir, "s", null, keyFile))
                    Assert.AreEqual(2, again.Count);
                Directory.CreateDirectory(Path.Combine(dir, "eph"));
                using (var eph = Wal.OpenEphemeralForTesting(Path.Combine(dir, "eph"), "s"))
                    Assert.AreEqual(0, eph.Count);
            }
            finally { Directory.Delete(dir, true); }
        }

        [Test]
        public void ProvRecorderChainsAndSyncs()
        {
            string dir = TempDir();
            try
            {
                using var p = ProvRecorder.Open(dir, "game-session");
                Assert.IsNull(p.Head);
                ProvBatch b1 = p.Record("[{\"type\":\"entity\",\"id\":\"ent-1\",\"label\":\"recording\"}]");
                ProvBatch b2 = p.Record("[{\"type\":\"activity\",\"id\":\"act-1\",\"label\":\"replay\"}]");
                var pending = p.Pending();
                CollectionAssert.AreEqual(new[] { b1.Id, b2.Id }, pending.Select(x => x.Id).ToArray());
                string chain = "[" + string.Join(",", pending.Select(x => Encoding.UTF8.GetString(x.Canonical))) + "]";
                CollectionAssert.AreEqual(new[] { b1.Id, b2.Id }, Hashing.VerifyProvChain(chain).ToArray());
                p.MarkSynced(b1.Seq);
                Assert.AreEqual(1, p.Pending().Count);
            }
            finally { Directory.Delete(dir, true); }
        }

        [Test]
        public void DeviceTokenVerifies()
        {
            using var key = DeviceKey.Generate();
            string token = key.Token("tenant-a", "device-1", "stream-1", 300);
            Verification.VerifyDeviceToken(token, key.PublicKey, DateTimeOffset.UtcNow.ToUnixTimeSeconds());
        }
    }

    public class HandleAndLeakTests
    {
        [Test]
        public void ErrorsAndDisposal()
        {
            var ex = Assert.Throws<NeuroForgeException>(() => Hashing.Canonicalize("{\"a\":1,\"a\":2}"));
            Assert.AreEqual(Status.Canonical, ex.Status);
            StringAssert.StartsWith("NF_ERR_CANONICAL: ", ex.Message);
            Assert.Throws<ArgumentException>(() => Wal.OpenEphemeralForTesting(Path.GetTempPath(), "embedded\0nul"));
            // ABI 1.2: no persistent key is refused in managed code, before any native call.
            Assert.Throws<ArgumentException>(() => Wal.Open(Path.GetTempPath(), "s", null, null));
            Assert.Throws<ArgumentException>(() => Wal.Open(Path.GetTempPath(), "s", null, ""));
            var k = DeviceKey.Generate();
            k.Dispose();
            k.Dispose();
            Assert.Throws<ObjectDisposedException>(() => { var _ = k.PublicKey; });
        }

        private static long PrivateBytes()
        {
            for (int i = 0; i < 3; i++) { GC.Collect(); GC.WaitForPendingFinalizers(); }
            using var p = Process.GetCurrentProcess();
            p.Refresh();
            return p.PrivateMemorySize64;
        }

        private static void AssertNoLeak(string what, int n, Action body)
        {
            for (int i = 0; i < Math.Min(n, 2000); i++) body();
            long before = PrivateBytes();
            if (before == 0) Assert.Inconclusive("PrivateMemorySize64 is not available in this runtime");
            for (int i = 0; i < n; i++) body();
            long growth = PrivateBytes() - before;
            UnityEngine.Debug.Log($"leak check {what}: {n} iterations, private bytes {growth / 1024:+#;-#;0} KiB");
            Assert.Less(growth, 8L << 20, $"{what}: grew {growth / 1024} KiB");
        }

        [Test]
        public void NoLeaks()
        {
            byte[] data = new byte[4096];
            AssertNoLeak("BlobId", 100_000, () => Hashing.BlobId(data));
            AssertNoLeak("error path", 100_000, () => { try { Hashing.Canonicalize("{\"a\":1,\"a\":2}"); } catch (NeuroForgeException) { } });
            AssertNoLeak("DeviceKey Dispose", 100_000, () => { using var k = DeviceKey.Generate(); });
            AssertNoLeak("DeviceKey finalizer", 100_000, () => DeviceKey.Generate());
            var buf = new double[64 * 3];
            string root = FixtureDir;
            AssertNoLeak("Recording open/read/free", 5_000, () => { using var r = Recording.Open(root, RecordingId); r.Read(0, 64, buf); });
        }
    }
}
