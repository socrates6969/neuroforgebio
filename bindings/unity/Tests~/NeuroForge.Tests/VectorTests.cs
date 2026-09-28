// Every case of spec/test-vectors/*.json, recomputed through the C# wrappers (the same vectors that
// bindings/c/tests/vectors.rs runs through the raw ABI).
using System;
using System.Linq;
using System.Text.Json;
using Xunit;

namespace NeuroForge.Tests
{
    public class VectorTests
    {
        private static string S(JsonElement e, string k) => e.GetProperty(k).GetString();
        private static string Raw(JsonElement e, string k) => e.GetProperty(k).GetRawText();
        private static JsonElement.ArrayEnumerator A(JsonElement e, string k) => e.GetProperty(k).EnumerateArray();
        private static string ArrayOf(JsonElement e, string k, string member) =>
            "[" + string.Join(",", A(e, k).Select(c => Raw(c, member))) + "]";

        [Fact]
        public void AbiIsCompatible()
        {
            Assert.True(NeuroForgeCore.IsCompatible, $"library ABI {NeuroForgeCore.AbiVersion}");
            Assert.False(string.IsNullOrEmpty(NeuroForgeCore.Version));
        }

        [Fact]
        public void CanonicalJson()
        {
            var doc = TestEnv.Vectors("canonical-json.json");
            foreach (var c in A(doc, "cases"))
                Assert.Equal(S(c, "canonical"), Hashing.Canonicalize(S(c, "input")));
            foreach (var e in A(doc, "errors"))
            {
                var ex = Assert.Throws<NeuroForgeException>(() => Hashing.Canonicalize(S(e, "input")));
                Assert.Equal(Status.Canonical, ex.Status);
                Assert.False(string.IsNullOrEmpty(ex.NativeMessage), S(e, "name"));
            }
        }

        [Fact]
        public void Numbers()
        {
            var doc = TestEnv.Vectors("numbers.json");
            foreach (var c in A(doc, "cases"))
            {
                double x = BitConverter.Int64BitsToDouble((long)Convert.ToUInt64(S(c, "ieee754"), 16));
                Assert.Equal(S(c, "canonical"), Hashing.FormatNumber(x));
            }
            foreach (var e in A(doc, "errors"))
            {
                double x = BitConverter.Int64BitsToDouble((long)Convert.ToUInt64(S(e, "ieee754"), 16));
                Assert.Equal(Status.Canonical, Assert.Throws<NeuroForgeException>(() => Hashing.FormatNumber(x)).Status);
            }
        }

        [Fact]
        public void IdsV1()
        {
            var doc = TestEnv.Vectors("ids.json");
            foreach (var b in A(doc, "blob"))
            {
                string id = Hashing.BlobId(TestEnv.Hex(S(b, "data_hex")));
                Assert.Equal(S(b, "id"), id);
                Assert.True(Hashing.IsValidId(id));
            }
            foreach (var p in A(doc, "pipeline_version"))
                Assert.Equal(S(p, "id"), Hashing.PipelineVersionId(Raw(p, "spec")));
            foreach (var ch in A(doc, "chunk"))
            {
                Dtype dt = NeuroForgeCore.ParseDtype(S(ch, "dtype"));
                ulong[] shape = ch.GetProperty("shape").EnumerateArray().Select(v => v.GetUInt64()).ToArray();
                Assert.Equal(S(ch, "id"), Hashing.ChunkId(dt, shape, TestEnv.Hex(S(ch, "data_hex"))));
            }
            foreach (var e in A(doc, "prov_batch_chain"))
                Assert.Equal(S(e, "id"), Hashing.ProvBatchId(Raw(e, "batch")));

            var want = A(doc, "prov_batch_chain").Select(e => S(e, "id")).ToArray();
            Assert.Equal(want, Hashing.VerifyProvChain(ArrayOf(doc, "prov_batch_chain", "batch")));
            // broken chain: drop the first batch
            string broken = "[" + string.Join(",", A(doc, "prov_batch_chain").Skip(1).Select(e => Raw(e, "batch"))) + "]";
            Assert.Equal(Status.Verify, Assert.Throws<NeuroForgeException>(() => Hashing.VerifyProvChain(broken)).Status);
        }

        [Fact]
        public void TypedChunkIdMatchesBytes()
        {
            // int16 [2, 2] = 0, 1, -1, 32767 is data_hex 00000100ffffff7f in ids.json
            short[] v = { 0, 1, -1, 32767 };
            string typed = Hashing.ChunkId<short>(Dtype.Int16, new ulong[] { 2, 2 }, v);
            Assert.Equal(Hashing.ChunkId(Dtype.Int16, new ulong[] { 2, 2 }, TestEnv.Hex("00000100ffffff7f")), typed);
            Assert.Throws<ArgumentException>(() => Hashing.ChunkId<float>(Dtype.Int16, new ulong[] { 2 }, new float[2]));
        }

        [Fact]
        public void IdsV2Hashes()
        {
            var doc = TestEnv.Vectors("ids-v2.json");
            foreach (var c in A(doc, "audit_batch_chain"))
            {
                string id = Hashing.AuditBatchId(Raw(c, "batch"));
                Assert.Equal(S(c, "id"), id);
                Assert.True(Hashing.IsValidIdV2(id));
                Assert.False(Hashing.IsValidId(id)); // auditb is v2 only
            }
            Assert.Equal(A(doc, "audit_batch_chain").Select(c => S(c, "id")).ToArray(),
                         Hashing.VerifyAuditChain(ArrayOf(doc, "audit_batch_chain", "batch")));
            foreach (var c in A(doc, "prov_node"))
                Assert.Equal(S(c, "hash"), Hashing.ProvNodeHash(Raw(c, "record")));
            foreach (var c in A(doc, "consent_record_chain"))
                Assert.Equal(S(c, "hash"), Hashing.ConsentRecordHash(Raw(c, "record")));
            Assert.Equal(A(doc, "consent_record_chain").Select(c => S(c, "hash")).ToArray(),
                         Hashing.VerifyConsentChain(ArrayOf(doc, "consent_record_chain", "record")));
            var nc = doc.GetProperty("consent_record_noncanonical_scopes");
            Assert.Equal(S(nc, "hash"), Hashing.ConsentRecordHash(Raw(nc, "record")));
            var rs = doc.GetProperty("ruleset");
            Assert.Equal(S(rs, "content_sha256"), Hashing.RulesetContentSha256(Raw(rs, "rules")));
            foreach (var c in A(doc, "sweep_variant"))
                Assert.Equal(S(c, "label"), Hashing.SweepVariantLabel(S(c, "base"), Raw(c, "params")));
            foreach (var c in A(doc, "training_subject"))
                Assert.Equal(S(c, "hash"), Hashing.TrainingSubjectHash(S(c, "tenant_id"), S(c, "subject_id")));
            Assert.Equal(5, A(doc, "training_manifest").Count());
            foreach (var c in A(doc, "training_manifest"))
            {
                string built = Hashing.TrainingManifestBuild(Raw(c, "args"));
                Assert.Equal(Hashing.Canonicalize(Raw(c, "manifest")), built);
                Assert.Equal(S(c, "payload"), built);
                Assert.Equal(S(c, "digest"), Hashing.TrainingManifestDigest(Raw(c, "manifest")));
            }
        }

        private static double[] Flat(JsonElement e, string k) =>
            e.GetProperty(k).EnumerateArray().SelectMany(p => p.EnumerateArray().Select(x => x.GetDouble())).ToArray();

        [Fact]
        public void IdsV2Signatures()
        {
            var doc = TestEnv.Vectors("ids-v2.json");
            byte[] pk = TestEnv.Hex(S(doc.GetProperty("test_key"), "public_hex"));

            var sc = doc.GetProperty("stream_chunk_signature");
            var ch = sc.GetProperty("chunk");
            double[] ts = ch.GetProperty("lsl_timestamps").EnumerateArray().Select(x => x.GetDouble()).ToArray();
            double[] off = Flat(ch, "clock_offsets"), loc = Flat(ch, "local_clock");
            Assert.Equal(S(sc, "timing_sha256"), Hashing.TimingSha256(ts, off, loc));
            var f = new StreamChunkFields
            {
                StreamId = S(ch, "stream_id"),
                Seq = ch.GetProperty("seq").GetUInt64(),
                NSamples = ch.GetProperty("n_samples").GetUInt32(),
                NChannels = ch.GetProperty("n_channels").GetUInt32(),
                ChunkId = S(ch, "chunk_id"),
                LslTimestamps = ts,
                ClockOffsetPairs = off,
                LocalClockPairs = loc,
            };
            byte[] sig = TestEnv.Hex(S(sc, "signature_hex"));
            Assert.True(Verification.VerifyStreamChunk(f, sig, pk));
            byte[] bad = (byte[])sig.Clone();
            bad[0] ^= 1;
            Assert.False(Verification.VerifyStreamChunk(f, bad, pk));
            f.Seq++;
            Assert.False(Verification.VerifyStreamChunk(f, sig, pk));

            var dt = doc.GetProperty("device_token");
            long iat = dt.GetProperty("claims").GetProperty("iat").GetInt64();
            long exp = dt.GetProperty("claims").GetProperty("exp").GetInt64();
            Assert.Equal(Hashing.Canonicalize(Raw(dt, "claims")), Verification.VerifyDeviceToken(S(dt, "token"), pk, iat));
            Assert.Equal(Status.Verify, Assert.Throws<NeuroForgeException>(() => Verification.VerifyDeviceToken(S(dt, "token"), pk, exp + 31)).Status);

            var pb = doc.GetProperty("provb_signature");
            Assert.True(Verification.VerifyProvbSignature(S(pb, "batch_id"), TestEnv.Hex(S(pb, "signature_hex")), pk));

            Assert.True(Verification.VerifyAnchor(Raw(doc.GetProperty("prov_anchor"), "document"), pk));
            Assert.True(Verification.VerifyAnchor(Raw(doc.GetProperty("consent_anchor"), "document"), pk));
            string cert = Raw(doc.GetProperty("deletion_certificate"), "document");
            Assert.True(Verification.VerifyCertificate(cert, pk));
            byte[] other = Enumerable.Repeat((byte)7, 32).ToArray();
            Assert.False(Verification.VerifyCertificate(cert, other));
            Assert.Throws<ArgumentException>(() => Verification.VerifyCertificate(cert, new byte[31]));
        }
    }
}
