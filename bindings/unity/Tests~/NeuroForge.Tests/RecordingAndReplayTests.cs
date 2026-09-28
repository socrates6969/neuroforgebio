// Recording reads and the replay round trip against the shared C/C++ fixture
// (bindings/c/tests/fixture/mod.rs): 3 channels Fz/Cz/Pz, 250 Hz, 1000 int16 samples with
// sample(i, c) = (i*3 + c) % 2000 - 1000 and timestamp(i) = 100 + i/250.
using System;
using System.Diagnostics;
using System.IO;
using NeuroForge.Replay;
using Xunit;

namespace NeuroForge.Tests
{
    public class RecordingAndReplayTests
    {
        private static Recording Open() => Recording.Open(TestEnv.FixtureDir, TestEnv.RecordingId);

        [Fact]
        public void InfoMatchesFixture()
        {
            using var r = Open();
            Assert.Equal(TestEnv.NSamples, r.SampleCount);
            Assert.Equal(3, r.ChannelCount);
            Assert.Equal(TestEnv.Sfreq, r.SampleRate);
            Assert.Equal(Dtype.Int16, r.Dtype);
            Assert.True(r.HasTimestamps);
            Assert.Equal(TestEnv.Channels, r.ChannelNames);
            Assert.All(r.ChannelUnits, u => Assert.Equal("uV", u));
        }

        [Fact]
        public void ReadsEveryValueExactly()
        {
            using var r = Open();
            var raw = new byte[(int)TestEnv.NSamples * 3 * 2];
            Assert.Equal((int)TestEnv.NSamples, r.ReadRaw(0, (int)TestEnv.NSamples, raw));
            var d = new double[(int)TestEnv.NSamples * 3];
            Assert.Equal((int)TestEnv.NSamples, r.Read(0, (int)TestEnv.NSamples, d));
            var f = new float[d.Length];
            r.Read(0, (int)TestEnv.NSamples, f);
            for (long i = 0; i < TestEnv.NSamples; i++)
                for (int c = 0; c < 3; c++)
                {
                    short want = TestEnv.Sample(i, c);
                    int k = (int)i * 3 + c;
                    Assert.Equal(want, BitConverter.ToInt16(raw, k * 2));
                    Assert.Equal(want, d[k]);
                    Assert.Equal(want, f[k]);
                }
            var ts = new double[(int)TestEnv.NSamples];
            Assert.Equal((int)TestEnv.NSamples, r.ReadTimestamps(0, (int)TestEnv.NSamples, ts));
            for (int i = 0; i < ts.Length; i++) Assert.Equal(TestEnv.Timestamp(i), ts[i]);
        }

        [Fact]
        public void ReadsAreClampedAndChecked()
        {
            using var r = Open();
            var d = new double[100 * 3];
            Assert.Equal(10, r.Read(990, 100, d));            // clamped to the end
            Assert.Equal(TestEnv.Sample(999, 2), d[9 * 3 + 2]);
            Assert.Equal(0, r.Read(1000, 10, d));              // empty range: no native call
            Assert.Equal(0, r.Read(5000, 10, d));
            Assert.Throws<ArgumentException>(() => r.Read(0, 100, new double[10]));
            Assert.Throws<ArgumentOutOfRangeException>(() => r.Read(-1, 1, d));
            r.Dispose();
            Assert.True(r.IsDisposed);
            Assert.Throws<ObjectDisposedException>(() => r.ReadRaw(0, 1, new byte[6]));
        }

        // Lossless unpaced replay: every block arrives in order and every value matches the fixture.
        [Fact]
        public void ReplayRoundTripIsExact()
        {
            using var w = new ReplayWorker(Open(), speed: double.PositiveInfinity, blockSamples: 37,
                                           maxQueuedBlocks: 4, backpressure: Backpressure.Block, ownsRecording: true);
            w.Start();
            long next = 0;
            var sw = Stopwatch.StartNew();
            while (next < TestEnv.NSamples && sw.Elapsed < TimeSpan.FromSeconds(30))
            {
                if (!w.TryDequeue(out SampleBlock b)) { Assert.Null(w.Error); System.Threading.Thread.Sleep(1); continue; }
                Assert.Equal(next, b.FirstSample);
                Assert.Equal(3, b.Channels);
                Assert.Equal(b.FirstSample / TestEnv.Sfreq, b.TimeSeconds);
                for (int row = 0; row < b.Rows; row++)
                    for (int c = 0; c < 3; c++)
                        Assert.Equal(TestEnv.Sample(b.FirstSample + row, c), b[row, c]);
                next += b.Rows;
            }
            Assert.Equal(TestEnv.NSamples, next);
            w.Stop();
            Assert.True(w.Completed);
            Assert.Null(w.Error);
            Assert.Equal(0, w.DroppedBlocks);
            Assert.False(w.TryDequeue(out _));
        }

        // Real-time pacing: at speed 4 the 4 s fixture takes about 1 s.
        [Fact]
        public void ReplayIsPacedInRealTime()
        {
            using var w = new ReplayWorker(Open(), speed: 4.0, blockSamples: 25, ownsRecording: true);
            var sw = Stopwatch.StartNew();
            w.Start();
            long rows = 0;
            while (!(w.Completed && w.QueuedBlocks == 0) && sw.Elapsed < TimeSpan.FromSeconds(10))
            {
                while (w.TryDequeue(out SampleBlock b)) rows += b.Rows;
                System.Threading.Thread.Sleep(5);
            }
            while (w.TryDequeue(out SampleBlock b)) rows += b.Rows;
            double s = sw.Elapsed.TotalSeconds;
            Assert.Equal(TestEnv.NSamples, rows);
            Assert.InRange(s, 0.9, 2.0);
        }

        [Fact]
        public void LoopingReplayWrapsAndStopsPromptly()
        {
            using var w = new ReplayWorker(Open(), speed: double.PositiveInfinity, loop: true, blockSamples: 100,
                                           maxQueuedBlocks: 8, backpressure: Backpressure.Block, ownsRecording: true);
            w.Start();
            int maxLoop = 0;
            var sw = Stopwatch.StartNew();
            while (maxLoop < 2 && sw.Elapsed < TimeSpan.FromSeconds(10))
                if (w.TryDequeue(out SampleBlock b)) maxLoop = Math.Max(maxLoop, b.Loop);
            Assert.Equal(2, maxLoop);
            var stop = Stopwatch.StartNew();
            w.Stop();
            Assert.True(stop.Elapsed < TimeSpan.FromSeconds(1), "Stop() should return promptly");
            Assert.False(w.IsRunning);
        }

        [Fact]
        public void DropOldestKeepsMemoryBounded()
        {
            using var w = new ReplayWorker(Open(), speed: double.PositiveInfinity, blockSamples: 10,
                                           maxQueuedBlocks: 5, backpressure: Backpressure.DropOldest, ownsRecording: true);
            w.Start();
            var sw = Stopwatch.StartNew();
            while (!w.Completed && sw.Elapsed < TimeSpan.FromSeconds(10)) System.Threading.Thread.Sleep(5);
            Assert.True(w.Completed);
            Assert.True(w.QueuedBlocks <= 5);
            Assert.Equal(100 - w.QueuedBlocks, w.DroppedBlocks);
            Assert.True(w.TryDequeue(out SampleBlock last));
            Assert.True(last.FirstSample >= 950); // the newest blocks survived
        }

        [Fact]
        public void MissingRecordingFailsOnOpenNotOnTheWorker()
        {
            Assert.Throws<NeuroForgeException>(() => Recording.Open(Path.Combine(Path.GetTempPath(), "nf-missing-" + Guid.NewGuid()), "rec-001"));
        }

        [Fact]
        public void ChunkCacheReturnsVerifiedFixtureChunk()
        {
            using var cache = ChunkCache.Open(Path.Combine(TestEnv.FixtureDir, "cache"));
            // The fixture's chunk: float32 [2, 3] = 0.5, 1.5, ..., 5.5
            var values = new float[] { 0.5f, 1.5f, 2.5f, 3.5f, 4.5f, 5.5f };
            string id = Hashing.ChunkId<float>(Dtype.Float32, new ulong[] { 2, 3 }, values);
            Chunk c = cache.TryGet(id);
            Assert.NotNull(c);
            Assert.Equal(Dtype.Float32, c.Dtype);
            Assert.Equal(new ulong[] { 2, 3 }, c.Shape);
            Assert.Equal(id, Hashing.ChunkId(c.Dtype, c.Shape, c.Data));
            Assert.True(cache.Size > 0);
            Assert.Null(cache.TryGet(Hashing.BlobId(new byte[] { 1 }).Replace("blob:", "chunk:")));
        }
    }
}
