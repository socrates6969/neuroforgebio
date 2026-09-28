// Every case of spec/test-vectors/*.json through the C# wrappers, inside the Unity editor (Mono).
using System;
using System.Linq;
using Newtonsoft.Json.Linq;
using NUnit.Framework;
using static NeuroForge.Tests.Editor.TestPaths;

namespace NeuroForge.Tests.Editor
{
    public class VectorTests
    {
        private static string ArrayOf(JObject doc, string k, string member) =>
            "[" + string.Join(",", doc[k].Select(c => Json(c[member]))) + "]";

        [Test]
        public void AbiIsCompatible()
        {
            Assert.IsTrue(NeuroForgeCore.IsCompatible, $"library ABI {NeuroForgeCore.AbiVersion}");
            Assert.IsFalse(string.IsNullOrEmpty(NeuroForgeCore.Version));
        }

        [Test]
        public void CanonicalJsonAndNumbers()
        {
            var doc = Vectors("canonical-json.json");
            foreach (var c in doc["cases"])
                Assert.AreEqual((string)c["canonical"], Hashing.Canonicalize((string)c["input"]), (string)c["name"]);
            foreach (var e in doc["errors"])
            {
                var ex = Assert.Throws<NeuroForgeException>(() => Hashing.Canonicalize((string)e["input"]));
                Assert.AreEqual(Status.Canonical, ex.Status, (string)e["name"]);
            }
            var nums = Vectors("numbers.json");
            foreach (var c in nums["cases"])
            {
                double x = BitConverter.Int64BitsToDouble((long)Convert.ToUInt64((string)c["ieee754"], 16));
                Assert.AreEqual((string)c["canonical"], Hashing.FormatNumber(x));
            }
            foreach (var e in nums["errors"])
            {
                double x = BitConverter.Int64BitsToDouble((long)Convert.ToUInt64((string)e["ieee754"], 16));
                Assert.AreEqual(Status.Canonical, Assert.Throws<NeuroForgeException>(() => Hashing.FormatNumber(x)).Status);
            }
        }

        [Test]
        public void IdsV1()
        {
            var doc = Vectors("ids.json");
            foreach (var b in doc["blob"])
            {
                string id = Hashing.BlobId(Hex((string)b["data_hex"]));
                Assert.AreEqual((string)b["id"], id);
                Assert.IsTrue(Hashing.IsValidId(id));
            }
            foreach (var p in doc["pipeline_version"])
                Assert.AreEqual((string)p["id"], Hashing.PipelineVersionId(Json(p["spec"])), (string)p["name"]);
            foreach (var ch in doc["chunk"])
            {
                Dtype dt = NeuroForgeCore.ParseDtype((string)ch["dtype"]);
                ulong[] shape = ch["shape"].Select(v => (ulong)v).ToArray();
                Assert.AreEqual((string)ch["id"], Hashing.ChunkId(dt, shape, Hex((string)ch["data_hex"])));
            }
            foreach (var e in doc["prov_batch_chain"])
                Assert.AreEqual((string)e["id"], Hashing.ProvBatchId(Json(e["batch"])));
            CollectionAssert.AreEqual(doc["prov_batch_chain"].Select(e => (string)e["id"]).ToArray(),
                                      Hashing.VerifyProvChain(ArrayOf(doc, "prov_batch_chain", "batch")).ToArray());
            string broken = "[" + string.Join(",", doc["prov_batch_chain"].Skip(1).Select(e => Json(e["batch"]))) + "]";
            Assert.AreEqual(Status.Verify, Assert.Throws<NeuroForgeException>(() => Hashing.VerifyProvChain(broken)).Status);
        }

        [Test]
        public void IdsV2HashesAndSignatures()
        {
            var doc = Vectors("ids-v2.json");
            foreach (var c in doc["audit_batch_chain"])
            {
                string id = Hashing.AuditBatchId(Json(c["batch"]));
                Assert.AreEqual((string)c["id"], id);
                Assert.IsTrue(Hashing.IsValidIdV2(id));
                Assert.IsFalse(Hashing.IsValidId(id));
            }
            foreach (var c in doc["prov_node"])
                Assert.AreEqual((string)c["hash"], Hashing.ProvNodeHash(Json(c["record"])));
            foreach (var c in doc["consent_record_chain"])
                Assert.AreEqual((string)c["hash"], Hashing.ConsentRecordHash(Json(c["record"])));
            CollectionAssert.AreEqual(doc["consent_record_chain"].Select(c => (string)c["hash"]).ToArray(),
                                      Hashing.VerifyConsentChain(ArrayOf(doc, "consent_record_chain", "record")).ToArray());
            Assert.AreEqual((string)doc["ruleset"]["content_sha256"], Hashing.RulesetContentSha256(Json(doc["ruleset"]["rules"])));
            foreach (var c in doc["sweep_variant"])
                Assert.AreEqual((string)c["label"], Hashing.SweepVariantLabel((string)c["base"], Json(c["params"])), (string)c["name"]);
            foreach (var c in doc["training_subject"])
                Assert.AreEqual((string)c["hash"], Hashing.TrainingSubjectHash((string)c["tenant_id"], (string)c["subject_id"]));
            // ABI 1.1.1 / spec: weights_source cases included. A silently shorter list would hide a regression.
            Assert.AreEqual(5, doc["training_manifest"].Count(), "training_manifest vector count");
            foreach (var c in doc["training_manifest"])
            {
                Assert.AreEqual((string)c["payload"], Hashing.TrainingManifestBuild(Json(c["args"])), (string)c["name"]);
                Assert.AreEqual((string)c["digest"], Hashing.TrainingManifestDigest(Json(c["manifest"])));
            }

            byte[] pk = Hex((string)doc["test_key"]["public_hex"]);
            var sc = doc["stream_chunk_signature"];
            var ch = sc["chunk"];
            double[] ts = ch["lsl_timestamps"].Select(x => (double)x).ToArray();
            double[] off = ch["clock_offsets"].SelectMany(p => p.Select(x => (double)x)).ToArray();
            double[] loc = ch["local_clock"].SelectMany(p => p.Select(x => (double)x)).ToArray();
            Assert.AreEqual((string)sc["timing_sha256"], Hashing.TimingSha256(ts, off, loc));
            var f = new StreamChunkFields
            {
                StreamId = (string)ch["stream_id"], Seq = (ulong)ch["seq"], NSamples = (uint)ch["n_samples"],
                NChannels = (uint)ch["n_channels"], ChunkId = (string)ch["chunk_id"],
                LslTimestamps = ts, ClockOffsetPairs = off, LocalClockPairs = loc,
            };
            byte[] sig = Hex((string)sc["signature_hex"]);
            Assert.IsTrue(Verification.VerifyStreamChunk(f, sig, pk));
            f.Seq++;
            Assert.IsFalse(Verification.VerifyStreamChunk(f, sig, pk));

            var dt = doc["device_token"];
            long iat = (long)dt["claims"]["iat"], exp = (long)dt["claims"]["exp"];
            Assert.AreEqual(Hashing.Canonicalize(Json(dt["claims"])), Verification.VerifyDeviceToken((string)dt["token"], pk, iat));
            Assert.AreEqual(Status.Verify, Assert.Throws<NeuroForgeException>(() => Verification.VerifyDeviceToken((string)dt["token"], pk, exp + 31)).Status);
            Assert.IsTrue(Verification.VerifyProvbSignature((string)doc["provb_signature"]["batch_id"], Hex((string)doc["provb_signature"]["signature_hex"]), pk));
            Assert.IsTrue(Verification.VerifyAnchor(Json(doc["prov_anchor"]["document"]), pk));
            Assert.IsTrue(Verification.VerifyCertificate(Json(doc["deletion_certificate"]["document"]), pk));
            Assert.IsFalse(Verification.VerifyCertificate(Json(doc["deletion_certificate"]["document"]), Enumerable.Repeat((byte)7, 32).ToArray()));
        }
    }
}
