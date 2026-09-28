// Regression tests for the engine-SDK review (docs/hive/ENGINE-SDKS-REVIEW.md on review/engine-sdks):
// U2 strict dtype mapping, U4 ChunkCache on two threads, U6 dispose while blocked, ABI rule,
// and NeuroStream re-entrancy.
using System;
using System.Diagnostics;
using System.IO;
using System.Threading;
using System.Threading.Tasks;
using NeuroForge.Replay;
using NeuroForge.Unity;
using NUnit.Framework;
using UnityEngine;
using static NeuroForge.Tests.Editor.TestPaths;

namespace NeuroForge.Tests.Editor
{
    public class ReviewRegressionTests
    {
        [Test]
        public void DtypeMismatchIsRejectedNotReinterpreted()
        {
            string dir = TempDir();
            try
            {
                using var key = DeviceKey.Generate();
                using var wal = Wal.OpenEphemeralForTesting(dir, "s");
                using (var f32 = new StreamWriter("s", Dtype.Float32, 1, 10, key, wal))
                {
                    Assert.Throws<ArgumentException>(() => f32.Push<int>(new[] { 1 }, new[] { 1.0 }));    // same size, wrong type
                    Assert.Throws<ArgumentException>(() => f32.Push<uint>(new[] { 1u }, new[] { 1.0 }));
                    Assert.Throws<ArgumentException>(() => f32.Push<double>(new[] { 1.0 }, new[] { 1.0 }));
                    Assert.AreEqual(0, f32.Push<float>(new[] { 1f }, new[] { 1.0 }));
                }
                using (var i32 = new StreamWriter("s", Dtype.Int32, 1, 10, key, wal))
                    Assert.Throws<ArgumentException>(() => i32.Push<float>(new[] { 1f }, new[] { 1.0 }));
                using (var i16 = new StreamWriter("s", Dtype.Int16, 1, 10, key, wal))
                    Assert.Throws<ArgumentException>(() => i16.Push<ushort>(new ushort[] { 1 }, new[] { 1.0 }));
                Assert.AreEqual(0, wal.Count); // nothing reached the WAL
            }
            finally { Directory.Delete(dir, true); }

            Assert.Throws<ArgumentException>(() => Hashing.ChunkId<int>(Dtype.Float32, new ulong[] { 1 }, new[] { 1 }));
            Assert.Throws<ArgumentException>(() => Hashing.ChunkId<float>(Dtype.Int32, new ulong[] { 1 }, new[] { 1f }));
            Assert.Throws<ArgumentException>(() => NeuroForgeCore.DtypeOf<bool>());
            Assert.AreEqual(Dtype.Int16, NeuroForgeCore.DtypeOf<short>());
            Assert.AreEqual(Dtype.Float64, NeuroForgeCore.DtypeOf<double>());
        }

        [Test]
        public void ChunkCacheOnTwoThreads()
        {
            using var cache = ChunkCache.Open(Path.Combine(FixtureDir, "cache"));
            string id = Hashing.ChunkId<float>(Dtype.Float32, new ulong[] { 2, 3 }, new float[] { 0.5f, 1.5f, 2.5f, 3.5f, 4.5f, 5.5f });
            string miss = "chunk:sha256:" + new string('0', 64);
            int errors = 0;
            Action body = () =>
            {
                for (int i = 0; i < 2000; i++)
                {
                    if (cache.TryGet(id) == null) Interlocked.Increment(ref errors);
                    if (cache.TryGet(miss) != null) Interlocked.Increment(ref errors);
                    if (cache.Size == 0) Interlocked.Increment(ref errors);
                }
            };
            Task.WaitAll(Task.Run(body), Task.Run(body));
            Assert.AreEqual(0, errors);
        }

        [Test]
        public void DisposeWhileBlockWaitingAndUseAfterDispose()
        {
            var w = new ReplayWorker(Recording.Open(FixtureDir, RecordingId), double.PositiveInfinity, blockSamples: 10,
                                     maxQueuedBlocks: 2, backpressure: Backpressure.Block, ownsRecording: true);
            w.Start();
            var sw = Stopwatch.StartNew();
            while (w.QueuedBlocks < 2 && sw.Elapsed.TotalSeconds < 5) Thread.Sleep(1);
            Assert.AreEqual(2, w.QueuedBlocks); // the worker is now blocked on a full queue
            var t = Stopwatch.StartNew();
            w.Dispose();
            Assert.Less(t.Elapsed.TotalSeconds, 1.0);
            Assert.IsFalse(w.IsRunning);
            Assert.IsTrue(w.Recording.IsDisposed);
            // After Dispose: no throw from Stop/TryDequeue/Dispose, Start is refused.
            w.Stop();
            w.Dispose();
            Assert.DoesNotThrow(() => w.TryDequeue(out _));
            Assert.Throws<ObjectDisposedException>(() => w.Start());
            // Concurrent Dispose from two threads.
            var w2 = new ReplayWorker(Recording.Open(FixtureDir, RecordingId), double.PositiveInfinity, maxQueuedBlocks: 1,
                                      backpressure: Backpressure.Block, ownsRecording: true);
            w2.Start();
            Task.WaitAll(Task.Run(() => w2.Dispose()), Task.Run(() => w2.Dispose()));
            Assert.IsFalse(w2.IsRunning);
        }

        [Test]
        public void AbiRule()
        {
            Assert.IsTrue(NeuroForgeCore.IsAbiCompatible(1u << 16 | 1u << 8));
            Assert.IsTrue(NeuroForgeCore.IsAbiCompatible(1u << 16 | 7u << 8 | 2u));
            Assert.IsFalse(NeuroForgeCore.IsAbiCompatible(1u << 16 | 0u << 8 | 9u)); // older minor
            Assert.IsFalse(NeuroForgeCore.IsAbiCompatible(2u << 16 | 1u << 8));      // other major
            Assert.IsFalse(NeuroForgeCore.IsAbiCompatible(0u));
        }

        [Test]
        public void NeuroStreamSurvivesStopAndPlayFromHandlers()
        {
            var go = new GameObject("NeuroStreamReentrancy");
            try
            {
                var s = go.AddComponent<NeuroStream>();
                s.RecordingRoot = FixtureDir;
                s.RecordingId = RecordingId;
                s.Speed = 50f;
                int blocks = 0, restarts = 0;
                s.onSamples.AddListener(b =>
                {
                    blocks++;
                    if (blocks == 3 && restarts++ == 0) s.Play(); // restart from inside the handler
                    else if (blocks == 8) s.Stop();                 // stop from inside the handler
                });
                s.onError.AddListener(m => Assert.Fail(m));
                Assert.IsTrue(s.Play());
                var sw = Stopwatch.StartNew();
                while (blocks < 8 && sw.Elapsed.TotalSeconds < 10)
                {
                    go.SendMessage("Update");
                    Thread.Sleep(5);
                }
                go.SendMessage("Update"); // one more frame after Stop: must be a no-op
                Assert.GreaterOrEqual(blocks, 8);
                Assert.AreEqual(1, restarts);
                Assert.IsFalse(s.IsPlaying);
            }
            finally
            {
                go.GetComponent<NeuroStream>()?.Stop();
                UnityEngine.Object.DestroyImmediate(go);
            }
        }
    }
}
