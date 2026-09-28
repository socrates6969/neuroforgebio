// Capture-side streaming (writer -> encrypted WAL) and the offline provenance recorder.
using System;
using System.IO;
using System.Linq;
using Xunit;

namespace NeuroForge.Tests
{
    public sealed class TempDir : IDisposable
    {
        public TempDir() { Path = System.IO.Path.Combine(System.IO.Path.GetTempPath(), "nf-unity-test-" + Guid.NewGuid().ToString("N")); Directory.CreateDirectory(Path); }
        public string Path { get; }
        public void Dispose() { try { Directory.Delete(Path, true); } catch (IOException) { } }
    }

    public class StreamingAndProvenanceTests
    {
        // Replay the fixture into a StreamWriter (the path a game takes when it re-streams captured
        // data): chunk and sample counts must add up, and the WAL must hold every chunk.
        [Fact]
        public void FixtureToWriterRoundTrip()
        {
            using var dir = new TempDir();
            using var rec = Recording.Open(TestEnv.FixtureDir, TestEnv.RecordingId);
            using var key = DeviceKey.Generate();
            using var wal = Wal.Open(dir.Path, "stream-1", Enumerable.Range(0, 32).Select(i => (byte)i).ToArray(), null, fsync: false);
            using var w = new StreamWriter("stream-1", Dtype.Int16, 3, 100, key, wal);

            var raw = new byte[64 * 3 * 2];
            var ts = new double[64];
            int chunks = 0;
            for (long pos = 0; pos < rec.SampleCount; pos += 64)
            {
                int rows = rec.ReadRaw(pos, 64, raw);
                rec.ReadTimestamps(pos, rows, ts);
                chunks += w.Push<short>(System.Runtime.InteropServices.MemoryMarshal.Cast<byte, short>(raw.AsSpan(0, rows * 6)), ts.AsSpan(0, rows));
            }
            Assert.Equal(10, chunks);                  // 1000 samples / 100 per chunk
            Assert.Equal(0, w.BufferedSamples);
            Assert.False(w.Flush());                    // nothing partial left
            Assert.Equal(10UL, w.NextSeq);
            var st = w.Stats;
            Assert.Equal(10UL, st.Chunks);
            Assert.Equal(1000UL, st.Samples);
            Assert.Equal(10, wal.Count);
        }

        [Fact]
        public void WriterRejectsMismatchedInput()
        {
            using var dir = new TempDir();
            using var key = DeviceKey.Generate();
            using var wal = Wal.OpenEphemeralForTesting(dir.Path, "s");
            using var w = new StreamWriter("s", Dtype.Float32, 2, 10, key, wal);
            Assert.Throws<ArgumentException>(() => w.Push<float>(new float[3], new double[2]));   // not n x channels
            Assert.Throws<ArgumentException>(() => w.Push<double>(new double[4], new double[2])); // wrong element size
            Assert.Equal(0, w.Push<float>(new float[4], new[] { 1.0, 1.001 }));
            Assert.Equal(2, w.BufferedSamples);
            Assert.True(w.Flush());
            Assert.Equal(1, wal.Count);
        }

        [Fact]
        public void DeviceTokenVerifiesWithItsPublicKey()
        {
            using var key = DeviceKey.Generate();
            string token = key.Token("tenant-a", "device-1", "stream-1", 300);
            long now = DateTimeOffset.UtcNow.ToUnixTimeSeconds();
            string claims = Verification.VerifyDeviceToken(token, key.PublicKey, now);
            Assert.Contains("\"device-1\"", claims);
            using var other = DeviceKey.Generate();
            Assert.Equal(Status.Verify, Assert.Throws<NeuroForgeException>(() => Verification.VerifyDeviceToken(token, other.PublicKey, now)).Status);
        }

        [Fact]
        public void SeededKeysAreDeterministic()
        {
            byte[] seed = Enumerable.Repeat((byte)42, 32).ToArray();
            using var a = DeviceKey.FromSeed(seed);
            using var b = DeviceKey.FromSeed(seed);
            Assert.Equal(a.PublicKey, b.PublicKey);
            Assert.Throws<NeuroForgeException>(() => DeviceKey.FromSeed(new byte[5]));
        }

        [Fact]
        public void ProvRecorderChainsAndSyncs()
        {
            using var dir = new TempDir();
            const string rec1 = "[{\"type\":\"entity\",\"id\":\"ent-1\",\"label\":\"recording\"}]";
            const string rec2 = "[{\"type\":\"activity\",\"id\":\"act-1\",\"label\":\"replay\"},{\"type\":\"edge\",\"rel\":\"used\",\"from\":\"act-1\",\"to\":\"ent-1\"}]";
            ProvBatch b1, b2;
            using (var p = ProvRecorder.Open(dir.Path, "game-session"))
            {
                Assert.Null(p.Head);
                b1 = p.Record(rec1);
                b2 = p.Record(rec2);
                Assert.Equal(2, p.Count);
                Assert.True(Hashing.IsValidId(b1.Id));
                Assert.Equal(b2.Id, p.Head.Value.Id);
                var pending = p.Pending();
                Assert.Equal(new[] { b1.Id, b2.Id }, pending.Select(x => x.Id));
                // The upload bytes hash to the batch ID, and the chain verifies.
                Assert.Equal(b1.Id, Hashing.ProvBatchId(System.Text.Encoding.UTF8.GetString(pending[0].Canonical)));
                string chain = "[" + string.Join(",", pending.Select(x => System.Text.Encoding.UTF8.GetString(x.Canonical))) + "]";
                Assert.Equal(new[] { b1.Id, b2.Id }, Hashing.VerifyProvChain(chain));
                p.MarkSynced(b1.Seq);
                Assert.Single(p.Pending());
            }
            // Reopening verifies the chain on disk and keeps the sync mark.
            using (var p = ProvRecorder.Open(dir.Path, "game-session"))
            {
                Assert.Equal(2, p.Count);
                Assert.Equal(b2.Id, p.Pending().Single().Id);
            }
        }
    }
}
