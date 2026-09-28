// Content IDs and canonical JSON (docs/spec/hashing.md), computed by nf-core. Names follow the
// Python SDK's neuroforge.canonical module. All functions are thread-safe.
using System;
using System.Collections.Generic;
using NeuroForge.Native;

namespace NeuroForge
{
    public static unsafe class Hashing
    {
        // ---- spec v1

        /// <summary>NF-CJSON v1 canonical form of a JSON document (hashing.md sec. 3).</summary>
        public static string Canonicalize(string json) => Doc(json, (byte* p, UIntPtr n, ref NfBuf o) => NativeMethods.nf_canonicalize(p, n, ref o));

        /// <summary>Canonical text of one number (hashing.md sec. 3.3). Non-finite values throw.</summary>
        public static string FormatNumber(double x) => Interop.Text((ref NfBuf o) => NativeMethods.nf_format_number(x, ref o));

        /// <summary><c>blob:sha256:&lt;hex&gt;</c> of raw bytes.</summary>
        public static string BlobId(ReadOnlySpan<byte> data)
        {
            fixed (byte* p = data)
            {
                byte* pp = p;
                UIntPtr n = Interop.Size(data.Length);
                return Interop.Text((ref NfBuf o) => NativeMethods.nf_blob_id(pp, n, ref o));
            }
        }

        public static string BlobId(byte[] data) => BlobId(new ReadOnlySpan<byte>(data ?? throw new ArgumentNullException(nameof(data))));

        /// <summary>Streaming blob ID of a file, and its size in bytes.</summary>
        public static (string Id, ulong Size) BlobIdOfFile(string path)
        {
            ulong size = 0;
            byte[] zp = Utf8.Z(path ?? throw new ArgumentNullException(nameof(path)));
            string id = Interop.Text((ref NfBuf o) => NativeMethods.nf_blob_id_file(zp, ref o, out size));
            return (id, size);
        }

        /// <summary><c>pv:sha256:&lt;hex&gt;</c> of a pipeline-version spec (JSON).</summary>
        public static string PipelineVersionId(string specJson) => Doc(specJson, (byte* p, UIntPtr n, ref NfBuf o) => NativeMethods.nf_pipeline_version_id(p, n, ref o));

        /// <summary><c>chunk:sha256:&lt;hex&gt;</c> of an array chunk: <paramref name="data"/> is
        /// itemsize * prod(shape) little-endian bytes in C order.</summary>
        public static string ChunkId(Dtype dtype, ulong[] shape, ReadOnlySpan<byte> data)
        {
            if (shape == null) throw new ArgumentNullException(nameof(shape));
            fixed (ulong* s = shape)
            fixed (byte* d = data)
            {
                ulong* ss = s; byte* dd = d;
                UIntPtr rank = Interop.Size(shape.Length), len = Interop.Size(data.Length);
                return Interop.Text((ref NfBuf o) => NativeMethods.nf_chunk_id((int)dtype, ss, rank, dd, len, ref o));
            }
        }

        /// <summary>ChunkId of typed values (the platform is little-endian on every supported target).</summary>
        public static string ChunkId<T>(Dtype dtype, ulong[] shape, ReadOnlySpan<T> values) where T : unmanaged
        {
            NeuroForgeCore.CheckElementType<T>(dtype);
            if (!BitConverter.IsLittleEndian) throw new PlatformNotSupportedException("big-endian host");
            return ChunkId(dtype, shape, System.Runtime.InteropServices.MemoryMarshal.AsBytes(values));
        }

        /// <summary><c>provb:sha256:&lt;hex&gt;</c> of one provenance batch (JSON).</summary>
        public static string ProvBatchId(string batchJson) => Doc(batchJson, (byte* p, UIntPtr n, ref NfBuf o) => NativeMethods.nf_prov_batch_id(p, n, ref o));

        /// <summary>Verify a provenance batch chain given as a JSON array; returns the batch IDs.
        /// A broken chain throws NeuroForgeException with Status.Verify.</summary>
        public static IReadOnlyList<string> VerifyProvChain(string batchesJsonArray) =>
            Interop.Lines(Doc(batchesJsonArray, (byte* p, UIntPtr n, ref NfBuf o) => NativeMethods.nf_verify_prov_chain(p, n, ref o)));

        /// <summary>Whether <paramref name="id"/> is a well-formed v1 content ID.</summary>
        public static bool IsValidId(string id)
        {
            if (id == null || id.IndexOf('\0') >= 0) return false;
            return NativeMethods.nf_is_valid_id(Utf8.Z(id));
        }

        // ---- spec v2

        public static bool IsValidIdV2(string id)
        {
            if (id == null || id.IndexOf('\0') >= 0) return false;
            return NativeMethods.nf_is_valid_id_v2(Utf8.Z(id));
        }

        public static string AuditBatchId(string batchJson) => Doc(batchJson, (byte* p, UIntPtr n, ref NfBuf o) => NativeMethods.nf_audit_batch_id(p, n, ref o));

        public static IReadOnlyList<string> VerifyAuditChain(string batchesJsonArray) =>
            Interop.Lines(Doc(batchesJsonArray, (byte* p, UIntPtr n, ref NfBuf o) => NativeMethods.nf_verify_audit_chain(p, n, ref o)));

        public static string ProvNodeHash(string recordJson) => Doc(recordJson, (byte* p, UIntPtr n, ref NfBuf o) => NativeMethods.nf_prov_node_hash(p, n, ref o));

        public static string ConsentRecordHash(string recordJson) => Doc(recordJson, (byte* p, UIntPtr n, ref NfBuf o) => NativeMethods.nf_consent_record_hash(p, n, ref o));

        public static IReadOnlyList<string> VerifyConsentChain(string recordsJsonArray) =>
            Interop.Lines(Doc(recordsJsonArray, (byte* p, UIntPtr n, ref NfBuf o) => NativeMethods.nf_verify_consent_chain(p, n, ref o)));

        public static string RulesetContentSha256(string rulesJson) => Doc(rulesJson, (byte* p, UIntPtr n, ref NfBuf o) => NativeMethods.nf_ruleset_content_sha256(p, n, ref o));

        public static string SweepVariantLabel(string basePvId, string paramsJson)
        {
            byte[] b = Utf8.Z(basePvId ?? throw new ArgumentNullException(nameof(basePvId)));
            return Doc(paramsJson, (byte* p, UIntPtr n, ref NfBuf o) => NativeMethods.nf_sweep_variant_label(b, p, n, ref o));
        }

        public static string TrainingSubjectHash(string tenantId, string subjectId)
        {
            byte[] t = Utf8.Z(tenantId ?? throw new ArgumentNullException(nameof(tenantId)));
            byte[] s = Utf8.Z(subjectId ?? throw new ArgumentNullException(nameof(subjectId)));
            return Interop.Text((ref NfBuf o) => NativeMethods.nf_training_subject_hash(t, s, ref o));
        }

        public static string TrainingManifestBuild(string argsJson) => Doc(argsJson, (byte* p, UIntPtr n, ref NfBuf o) => NativeMethods.nf_training_manifest_build(p, n, ref o));

        public static string TrainingManifestDigest(string manifestJson) => Doc(manifestJson, (byte* p, UIntPtr n, ref NfBuf o) => NativeMethods.nf_training_manifest_digest(p, n, ref o));

        /// <summary>Timing hash of a stream chunk (hashing.md sec. 10.1). The offset and local-clock
        /// arrays are flat pairs.</summary>
        public static string TimingSha256(ReadOnlySpan<double> lslTimestamps, ReadOnlySpan<double> clockOffsetPairs, ReadOnlySpan<double> localClockPairs)
        {
            if (clockOffsetPairs.Length % 2 != 0 || localClockPairs.Length % 2 != 0)
                throw new ArgumentException("clock offsets and local clock are flat (a, b) pairs");
            fixed (double* a = lslTimestamps)
            fixed (double* b = clockOffsetPairs)
            fixed (double* c = localClockPairs)
            {
                double* aa = a, bb = b, cc = c;
                UIntPtr na = Interop.Size(lslTimestamps.Length), nb = Interop.Size(clockOffsetPairs.Length / 2), nc = Interop.Size(localClockPairs.Length / 2);
                return Interop.Text((ref NfBuf o) => NativeMethods.nf_timing_sha256(aa, na, bb, nb, cc, nc, ref o));
            }
        }

        // ---- helpers

        internal delegate int DocCall(byte* p, UIntPtr n, ref NfBuf o);

        // Pass a string as (UTF-8 bytes, length) and return the text result.
        internal static string Doc(string json, DocCall f)
        {
            byte[] b = Utf8.Bytes(json);
            fixed (byte* p = b)
            {
                byte* pp = p;
                UIntPtr n = Interop.Size(b.Length);
                return Interop.Text((ref NfBuf o) => f(pp, n, ref o));
            }
        }
    }
}
