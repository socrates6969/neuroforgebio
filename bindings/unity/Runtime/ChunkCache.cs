// The local content-addressed chunk cache (read-only in this ABI): every get re-verifies the hash.
using System;
using NeuroForge.Native;

namespace NeuroForge
{
    /// <summary>A decoded, hash-verified chunk copied out of the cache.</summary>
    public sealed class Chunk
    {
        internal Chunk(Dtype dtype, ulong[] shape, byte[] data) { Dtype = dtype; Shape = shape; Data = data; }
        public Dtype Dtype { get; }
        public ulong[] Shape { get; }
        /// <summary>Little-endian values in C order.</summary>
        public byte[] Data { get; }
    }

    public sealed unsafe class ChunkCache : IDisposable
    {
        private readonly ChunkCacheHandle _h;
        private readonly object _lock = new object();

        private ChunkCache(ChunkCacheHandle h) { _h = h; }

        /// <summary>Open the cache at <paramref name="root"/> (created if missing).</summary>
        public static ChunkCache Open(string root, ulong maxBytes = 2UL << 30)
        {
            int s = NativeMethods.nf_chunk_cache_open(Utf8.Z(root ?? throw new ArgumentNullException(nameof(root))), maxBytes, out ChunkCacheHandle h);
            if (s != Status.Ok) { h?.Dispose(); Interop.Check(s); }
            return new ChunkCache(h);
        }

        /// <summary>The chunk, or null on a miss (a corrupt entry is removed and also reported as a miss).</summary>
        public Chunk TryGet(string chunkId)
        {
            byte[] id = Utf8.Z(chunkId ?? throw new ArgumentNullException(nameof(chunkId)));
            lock (_lock) return TryGetLocked(id);
        }

        // The header does not declare nf_chunk_cache thread-safe: every call on one cache is serialised.
        private Chunk TryGetLocked(byte[] id)
        {
            if (_h.IsClosed) throw new ObjectDisposedException(nameof(ChunkCache));
            int s = NativeMethods.nf_chunk_cache_get(_h, id, out ChunkHandle c);
            using (c)
            {
                if (s == Status.NotFound) return null;
                Interop.Check(s);
                var dtype = (Dtype)NativeMethods.nf_chunk_dtype(c);
                int rank = checked((int)(ulong)NativeMethods.nf_chunk_rank(c));
                ulong* sp = NativeMethods.nf_chunk_shape(c);
                var shape = new ulong[rank];
                for (int i = 0; i < rank; i++) shape[i] = sp[i];
                byte* dp = NativeMethods.nf_chunk_data(c, out UIntPtr len);
                var data = new byte[checked((int)(ulong)len)];
                if (data.Length > 0) fixed (byte* d = data) Buffer.MemoryCopy(dp, d, data.Length, data.Length);
                return new Chunk(dtype, shape, data);
            }
        }

        /// <summary>Total bytes currently cached.</summary>
        public ulong Size
        {
            get
            {
                lock (_lock)
                {
                    if (_h.IsClosed) throw new ObjectDisposedException(nameof(ChunkCache));
                    Interop.Check(NativeMethods.nf_chunk_cache_size(_h, out ulong n));
                    return n;
                }
            }
        }

        public void Dispose() { lock (_lock) _h.Dispose(); }
    }
}
