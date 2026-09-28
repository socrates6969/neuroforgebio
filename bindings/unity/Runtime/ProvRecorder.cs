// Offline provenance recorder: a local hash chain that is synced to the platform later
// (hashing.md sec. 5.3). Mirrors neuroforge.local.ProvRecorder in the Python SDK.
using System;
using System.Collections.Generic;
using NeuroForge.Native;

namespace NeuroForge
{
    public readonly struct ProvBatch
    {
        public ProvBatch(ulong seq, string id, byte[] canonical) { Seq = seq; Id = id; Canonical = canonical; }
        public ulong Seq { get; }
        /// <summary>The <c>provb:</c> ID.</summary>
        public string Id { get; }
        /// <summary>Canonical batch bytes to upload (Pending only; otherwise null).</summary>
        public byte[] Canonical { get; }
    }

    public sealed unsafe class ProvRecorder : IDisposable
    {
        private readonly ProvRecorderHandle _h;
        private readonly object _lock = new object();

        private ProvRecorder(ProvRecorderHandle h) { _h = h; }

        /// <summary>Open (or create) chain <paramref name="chain"/> in <paramref name="directory"/> and
        /// verify it; a chain that does not verify throws with Status.Verify.</summary>
        public static ProvRecorder Open(string directory, string chain)
        {
            int s = NativeMethods.nf_prov_recorder_open(
                Utf8.Z(directory ?? throw new ArgumentNullException(nameof(directory))),
                Utf8.Z(chain ?? throw new ArgumentNullException(nameof(chain))), out ProvRecorderHandle h);
            if (s != Status.Ok) { h?.Dispose(); Interop.Check(s); }
            return new ProvRecorder(h);
        }

        /// <summary>Append one batch (a JSON array of PROV records); returns its sequence number and ID.</summary>
        public ProvBatch Record(string recordsJson)
        {
            byte[] b = Utf8.Bytes(recordsJson);
            lock (_lock)
            {
                ThrowIfDisposed();
                ulong seq = 0;
                fixed (byte* p = b)
                {
                    byte* pp = p;
                    UIntPtr n = Interop.Size(b.Length);
                    string id = Interop.Text((ref NfBuf o) => NativeMethods.nf_prov_recorder_record(_h, pp, n, out seq, ref o));
                    return new ProvBatch(seq, id, null);
                }
            }
        }

        public int Count
        {
            get
            {
                lock (_lock)
                {
                    ThrowIfDisposed();
                    Interop.Check(NativeMethods.nf_prov_recorder_len(_h, out UIntPtr n));
                    return checked((int)(ulong)n);
                }
            }
        }

        /// <summary>The newest batch, or null for an empty chain.</summary>
        public ProvBatch? Head
        {
            get
            {
                lock (_lock)
                {
                    ThrowIfDisposed();
                    var buf = default(NfBuf);
                    int s = NativeMethods.nf_prov_recorder_head(_h, out ulong seq, ref buf);
                    if (s == Status.NotFound) { NativeMethods.nf_buf_free(ref buf); return null; }
                    if (s != Status.Ok) { try { Interop.Check(s); } finally { NativeMethods.nf_buf_free(ref buf); } }
                    return new ProvBatch(seq, Interop.TakeString(ref buf), null);
                }
            }
        }

        /// <summary>Batches not yet marked synced, oldest first, with their upload bytes.</summary>
        public IReadOnlyList<ProvBatch> Pending()
        {
            lock (_lock)
            {
                ThrowIfDisposed();
                Interop.Check(NativeMethods.nf_prov_recorder_pending_count(_h, out UIntPtr n));
                var list = new List<ProvBatch>(checked((int)(ulong)n));
                for (ulong i = 0; i < (ulong)n; i++)
                {
                    NfBuf id = default, canon = default;
                    try
                    {
                        int s = NativeMethods.nf_prov_recorder_pending(_h, (UIntPtr)i, out ulong seq, ref id, ref canon);
                        Interop.Check(s);
                        string idText = Interop.TakeString(ref id);
                        list.Add(new ProvBatch(seq, idText, Interop.TakeBytes(ref canon)));
                    }
                    finally
                    {
                        NativeMethods.nf_buf_free(ref id);
                        NativeMethods.nf_buf_free(ref canon);
                    }
                }
                return list;
            }
        }

        /// <summary>Mark every batch up to and including <paramref name="seq"/> as synced.</summary>
        public void MarkSynced(ulong seq)
        {
            lock (_lock)
            {
                ThrowIfDisposed();
                Interop.Check(NativeMethods.nf_prov_recorder_mark_synced(_h, seq));
            }
        }

        public void Dispose() { lock (_lock) _h.Dispose(); }

        private void ThrowIfDisposed()
        {
            if (_h.IsClosed) throw new ObjectDisposedException(nameof(ProvRecorder));
        }
    }
}
