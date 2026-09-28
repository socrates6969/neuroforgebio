// Ed25519 signature checks (hashing.md sec. 10). Verification only: the SDK cannot sign anything
// except through a DeviceKey it owns (Streaming.cs). All functions are thread-safe.
using System;
using NeuroForge.Native;

namespace NeuroForge
{
    /// <summary>The chunk fields a stream-chunk signature covers (hashing.md sec. 10.1).</summary>
    public sealed class StreamChunkFields
    {
        public string StreamId;
        public ulong Seq;
        public uint NSamples;
        public uint NChannels;
        public string ChunkId;
        public double[] LslTimestamps = Array.Empty<double>();
        /// <summary>Flat (collection_time, offset) pairs.</summary>
        public double[] ClockOffsetPairs = Array.Empty<double>();
        /// <summary>Flat (lsl_time, monotonic_time) pairs.</summary>
        public double[] LocalClockPairs = Array.Empty<double>();
    }

    public static unsafe class Verification
    {
        public const int PublicKeyLength = 32;

        /// <summary>Whether <paramref name="signature"/> (64 bytes) signs the chunk fields. A bad
        /// signature returns false; malformed input throws.</summary>
        public static bool VerifyStreamChunk(StreamChunkFields f, ReadOnlySpan<byte> signature, ReadOnlySpan<byte> publicKey)
        {
            if (f == null) throw new ArgumentNullException(nameof(f));
            CheckKey(publicKey);
            if (f.ClockOffsetPairs.Length % 2 != 0 || f.LocalClockPairs.Length % 2 != 0)
                throw new ArgumentException("clock offsets and local clock are flat (a, b) pairs");
            byte[] sid = Utf8.Z(f.StreamId ?? throw new ArgumentNullException(nameof(f.StreamId)));
            byte[] cid = Utf8.Z(f.ChunkId ?? throw new ArgumentNullException(nameof(f.ChunkId)));
            fixed (byte* s = sid)
            fixed (byte* c = cid)
            fixed (double* ts = f.LslTimestamps)
            fixed (double* co = f.ClockOffsetPairs)
            fixed (double* lc = f.LocalClockPairs)
            fixed (byte* sig = signature)
            fixed (byte* pk = publicKey)
            {
                var fields = new NfStreamChunkFields
                {
                    StreamId = s,
                    Seq = f.Seq,
                    NSamples = f.NSamples,
                    NChannels = f.NChannels,
                    ChunkId = c,
                    LslTimestamps = ts,
                    NTimestamps = Interop.Size(f.LslTimestamps.Length),
                    ClockOffsets = co,
                    NClockOffsets = Interop.Size(f.ClockOffsetPairs.Length / 2),
                    LocalClock = lc,
                    NLocalClock = Interop.Size(f.LocalClockPairs.Length / 2),
                };
                Interop.Check(NativeMethods.nf_verify_stream_chunk(ref fields, sig, Interop.Size(signature.Length), pk, out bool ok));
                return ok;
            }
        }

        /// <summary>Verify a device token at <paramref name="nowUnixSeconds"/>; returns the canonical
        /// claims JSON. An invalid or expired token throws with Status.Verify.</summary>
        public static string VerifyDeviceToken(string token, ReadOnlySpan<byte> publicKey, long nowUnixSeconds)
        {
            CheckKey(publicKey);
            byte[] t = Utf8.Z(token ?? throw new ArgumentNullException(nameof(token)));
            fixed (byte* pk = publicKey)
            {
                byte* p = pk;
                return Interop.Text((ref NfBuf o) => NativeMethods.nf_verify_device_token(t, p, nowUnixSeconds, ref o));
            }
        }

        public static bool VerifyProvbSignature(string batchId, ReadOnlySpan<byte> signature, ReadOnlySpan<byte> publicKey)
        {
            CheckKey(publicKey);
            byte[] b = Utf8.Z(batchId ?? throw new ArgumentNullException(nameof(batchId)));
            fixed (byte* sig = signature)
            fixed (byte* pk = publicKey)
            {
                Interop.Check(NativeMethods.nf_verify_provb_signature(b, sig, Interop.Size(signature.Length), pk, out bool ok));
                return ok;
            }
        }

        public static bool VerifyAnchor(string anchorJson, ReadOnlySpan<byte> publicKey) =>
            VerifyDoc(anchorJson, publicKey, (byte* d, UIntPtr n, byte* pk, out bool ok) => NativeMethods.nf_verify_anchor(d, n, pk, out ok));

        public static bool VerifyCertificate(string certificateJson, ReadOnlySpan<byte> publicKey) =>
            VerifyDoc(certificateJson, publicKey, (byte* d, UIntPtr n, byte* pk, out bool ok) => NativeMethods.nf_verify_certificate(d, n, pk, out ok));

        private delegate int DocVerify(byte* doc, UIntPtr len, byte* publicKey, out bool ok);

        private static bool VerifyDoc(string json, ReadOnlySpan<byte> publicKey, DocVerify f)
        {
            CheckKey(publicKey);
            byte[] b = Utf8.Bytes(json);
            fixed (byte* d = b)
            fixed (byte* pk = publicKey)
            {
                Interop.Check(f(d, Interop.Size(b.Length), pk, out bool ok));
                return ok;
            }
        }

        // The C functions read exactly 32 bytes from the key pointer; never hand them less.
        private static void CheckKey(ReadOnlySpan<byte> publicKey)
        {
            if (publicKey.Length != PublicKeyLength)
                throw new ArgumentException($"public key must be {PublicKeyLength} bytes", nameof(publicKey));
        }
    }
}
