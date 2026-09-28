// Capture side of streaming: a device key, the encrypted write-ahead log (WAL) and the writer that
// cuts pushed samples into signed chunks. Data flows device -> SDK -> platform only.
//
// Not in v0: the sender (nf_sender_*), which uploads WAL chunks through a caller-supplied gRPC
// transport given as C callbacks. Until it is wrapped, upload the WAL with the Python SDK or a C++
// host (bindings/cpp).
using System;
using NeuroForge.Native;

namespace NeuroForge
{
    /// <summary>An Ed25519 device key. The secret never leaves the native library. Thread-safe.</summary>
    public sealed unsafe class DeviceKey : IDisposable
    {
        internal readonly DeviceKeyHandle Handle;

        private DeviceKey(DeviceKeyHandle h) { Handle = h; }

        public static DeviceKey Generate()
        {
            int s = NativeMethods.nf_device_key_generate(out DeviceKeyHandle h);
            return Wrap(s, h);
        }

        /// <summary>Import a 32-byte Ed25519 seed (for keys held in an OS keystore).</summary>
        public static DeviceKey FromSeed(ReadOnlySpan<byte> seed)
        {
            fixed (byte* p = seed)
            {
                int s = NativeMethods.nf_device_key_from_seed(p, Interop.Size(seed.Length), out DeviceKeyHandle h);
                return Wrap(s, h);
            }
        }

        /// <summary>Windows: load the DPAPI-sealed key at <paramref name="path"/>, or create one there.
        /// Elsewhere this throws with Status.Unsupported.</summary>
        public static DeviceKey OpenSealed(string path)
        {
            int s = NativeMethods.nf_device_key_open_sealed(Utf8.Z(path ?? throw new ArgumentNullException(nameof(path))), out DeviceKeyHandle h);
            return Wrap(s, h);
        }

        public byte[] PublicKey
        {
            get
            {
                ThrowIfDisposed();
                var pk = new byte[Verification.PublicKeyLength];
                fixed (byte* p = pk) Interop.Check(NativeMethods.nf_device_key_public_key(Handle, p));
                return pk;
            }
        }

        /// <summary>A device token for tenant/device/stream, valid <paramref name="lifetimeSeconds"/> (at most 600).</summary>
        public string Token(string tenantId, string deviceId, string streamId, ulong lifetimeSeconds = 300)
        {
            ThrowIfDisposed();
            byte[] t = Utf8.Z(tenantId ?? throw new ArgumentNullException(nameof(tenantId)));
            byte[] d = Utf8.Z(deviceId ?? throw new ArgumentNullException(nameof(deviceId)));
            byte[] s = Utf8.Z(streamId ?? throw new ArgumentNullException(nameof(streamId)));
            return Interop.Text((ref NfBuf o) => NativeMethods.nf_device_key_token(Handle, t, d, s, lifetimeSeconds, ref o));
        }

        public void Dispose() => Handle.Dispose();

        internal void ThrowIfDisposed()
        {
            if (Handle.IsClosed) throw new ObjectDisposedException(nameof(DeviceKey));
        }

        private static DeviceKey Wrap(int s, DeviceKeyHandle h)
        {
            if (s != Status.Ok) { h?.Dispose(); Interop.Check(s); }
            return new DeviceKey(h);
        }
    }

    /// <summary>The encrypted on-disk write-ahead log of one stream. Thread-safe.</summary>
    public sealed unsafe class Wal : IDisposable
    {
        internal readonly WalHandle Handle;

        private Wal(WalHandle h) { Handle = h; }

        /// <summary>Open (or create) the WAL of <paramref name="streamId"/> in <paramref name="directory"/>
        /// with a PERSISTENT key, so unsent records survive a crash or restart. Key source, first match
        /// wins: <paramref name="key32"/> (32 bytes from an OS keystore: Windows Credential Manager/DPAPI,
        /// macOS Keychain, ...), then <paramref name="dpapiKeyPath"/> (Windows: a DPAPI-sealed key file
        /// created on first use; any process of the same Windows user can unseal it). At least one is
        /// required (ABI 1.2); a throwaway key exists only as <see cref="OpenEphemeralForTesting"/>.</summary>
        public static Wal Open(string directory, string streamId, byte[] key32, string dpapiKeyPath, bool fsync = true)
        {
            if (key32 == null && string.IsNullOrEmpty(dpapiKeyPath))
                throw new ArgumentException("a WAL needs a persistent key: pass key32 (OS keystore) or dpapiKeyPath", nameof(key32));
            if (key32 != null && key32.Length != 32) throw new ArgumentException("WAL key must be 32 bytes", nameof(key32));
            byte[] dir = Utf8.Z(directory ?? throw new ArgumentNullException(nameof(directory)));
            byte[] sid = Utf8.Z(streamId ?? throw new ArgumentNullException(nameof(streamId)));
            byte[] dp = string.IsNullOrEmpty(dpapiKeyPath) ? null : Utf8.Z(dpapiKeyPath);
            fixed (byte* k = key32)
            {
                int s = NativeMethods.nf_wal_open(dir, sid, k, dp, fsync, out WalHandle h);
                if (s != Status.Ok) { h?.Dispose(); Interop.Check(s); }
                return new Wal(h);
            }
        }

        /// <summary>FOR TESTS ONLY. Opens a WAL with a random in-memory key: every unsent record is
        /// unreadable after this process ends, so data is lost on a crash or restart. Never use it in
        /// a game, sample or tool (nfb-security condition for ABI 1.2's nf_wal_open_ephemeral).</summary>
        public static Wal OpenEphemeralForTesting(string directory, string streamId, bool fsync = false)
        {
            byte[] dir = Utf8.Z(directory ?? throw new ArgumentNullException(nameof(directory)));
            byte[] sid = Utf8.Z(streamId ?? throw new ArgumentNullException(nameof(streamId)));
            int s = NativeMethods.nf_wal_open_ephemeral(dir, sid, fsync, out WalHandle h);
            if (s != Status.Ok) { h?.Dispose(); Interop.Check(s); }
            return new Wal(h);
        }

        /// <summary>Records waiting in the WAL (not yet acknowledged by the platform).</summary>
        public int Count
        {
            get
            {
                if (Handle.IsClosed) throw new ObjectDisposedException(nameof(Wal));
                Interop.Check(NativeMethods.nf_wal_len(Handle, out UIntPtr n));
                return checked((int)(ulong)n);
            }
        }

        public void Dispose() => Handle.Dispose();
    }

    public readonly struct WriterStats
    {
        internal WriterStats(NfWriterStats s) { Chunks = s.Chunks; Samples = s.Samples; WalPeak = s.WalPeak; }
        public ulong Chunks { get; }
        public ulong Samples { get; }
        public ulong WalPeak { get; }
    }

    /// <summary>Cuts pushed samples into signed chunks and appends them to the WAL. One producer
    /// thread is the intended use (the native writer locks internally).</summary>
    public sealed unsafe class StreamWriter : IDisposable
    {
        private readonly StreamWriterHandle _h;

        /// <param name="dtype">int16, int32, float32 or float64.</param>
        /// <param name="chunkSamples">Samples per chunk (for example 100 = 100 ms at 1 kHz).</param>
        public StreamWriter(string streamId, Dtype dtype, int channelCount, int chunkSamples, DeviceKey key, Wal wal)
        {
            if (key == null) throw new ArgumentNullException(nameof(key));
            if (wal == null) throw new ArgumentNullException(nameof(wal));
            if (channelCount <= 0) throw new ArgumentOutOfRangeException(nameof(channelCount));
            if (chunkSamples <= 0) throw new ArgumentOutOfRangeException(nameof(chunkSamples));
            Dtype = dtype;
            ChannelCount = channelCount;
            int s = NativeMethods.nf_stream_writer_new(Utf8.Z(streamId ?? throw new ArgumentNullException(nameof(streamId))),
                (int)dtype, (uint)channelCount, (uint)chunkSamples, key.Handle, wal.Handle, out StreamWriterHandle h);
            if (s != Status.Ok) { h?.Dispose(); Interop.Check(s); }
            _h = h;
        }

        public Dtype Dtype { get; }
        public int ChannelCount { get; }

        /// <summary>Push samples (row-major [n][channels] of the writer dtype, one timestamp per
        /// sample). Returns how many full chunks were written.</summary>
        public int Push<T>(ReadOnlySpan<T> samples, ReadOnlySpan<double> timestamps) where T : unmanaged
        {
            ThrowIfDisposed();
            NeuroForgeCore.CheckElementType<T>(Dtype);
            if (samples.Length != checked((long)timestamps.Length * ChannelCount))
                throw new ArgumentException($"expected {timestamps.Length} x {ChannelCount} samples, got {samples.Length}");
            if (!BitConverter.IsLittleEndian) throw new PlatformNotSupportedException("big-endian host");
            var bytes = System.Runtime.InteropServices.MemoryMarshal.AsBytes(samples);
            fixed (byte* p = bytes)
            fixed (double* t = timestamps)
            {
                Interop.Check(NativeMethods.nf_stream_writer_push(_h, p, Interop.Size(bytes.Length), t, Interop.Size(timestamps.Length), out UIntPtr chunks));
                return checked((int)(ulong)chunks);
            }
        }

        public void AddClockOffset(double collectionTime, double offset)
        {
            ThrowIfDisposed();
            Interop.Check(NativeMethods.nf_stream_writer_add_clock_offset(_h, collectionTime, offset));
        }

        public void AddLocalClock(double lslTime, double monotonicTime)
        {
            ThrowIfDisposed();
            Interop.Check(NativeMethods.nf_stream_writer_add_local_clock(_h, lslTime, monotonicTime));
        }

        /// <summary>Write the buffered partial chunk (end of acquisition); false if there was none.</summary>
        public bool Flush()
        {
            ThrowIfDisposed();
            Interop.Check(NativeMethods.nf_stream_writer_flush(_h, out bool wrote));
            return wrote;
        }

        public ulong NextSeq
        {
            get { ThrowIfDisposed(); Interop.Check(NativeMethods.nf_stream_writer_next_seq(_h, out ulong s)); return s; }
        }

        public int BufferedSamples
        {
            get { ThrowIfDisposed(); Interop.Check(NativeMethods.nf_stream_writer_buffered_samples(_h, out UIntPtr n)); return checked((int)(ulong)n); }
        }

        public WriterStats Stats
        {
            get { ThrowIfDisposed(); Interop.Check(NativeMethods.nf_stream_writer_get_stats(_h, out NfWriterStats s)); return new WriterStats(s); }
        }

        /// <summary>Free the writer. Buffered samples that were not flushed are dropped.</summary>
        public void Dispose() => _h.Dispose();

        private void ThrowIfDisposed()
        {
            if (_h.IsClosed) throw new ObjectDisposedException(nameof(StreamWriter));
        }
    }
}
