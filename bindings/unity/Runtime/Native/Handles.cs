// One SafeHandle per opaque nf_* handle. ReleaseHandle runs exactly once (Dispose or finalizer) and
// calls the matching nf_*_free. While a P/Invoke call is using a handle, the marshaller holds a
// reference to it, so another thread's Dispose cannot free it mid-call (header rule "do not free a
// handle while another thread uses it").
using System;
using System.Runtime.InteropServices;

namespace NeuroForge.Native
{
    internal sealed class RecordingHandle : SafeHandle
    {
        public RecordingHandle() : base(IntPtr.Zero, true) { }
        public override bool IsInvalid => handle == IntPtr.Zero;
        protected override bool ReleaseHandle() { NativeMethods.nf_recording_free(handle); return true; }
    }

    internal sealed class ChunkCacheHandle : SafeHandle
    {
        public ChunkCacheHandle() : base(IntPtr.Zero, true) { }
        public override bool IsInvalid => handle == IntPtr.Zero;
        protected override bool ReleaseHandle() { NativeMethods.nf_chunk_cache_free(handle); return true; }
    }

    internal sealed class ChunkHandle : SafeHandle
    {
        public ChunkHandle() : base(IntPtr.Zero, true) { }
        public override bool IsInvalid => handle == IntPtr.Zero;
        protected override bool ReleaseHandle() { NativeMethods.nf_chunk_free(handle); return true; }
    }

    internal sealed class ProvRecorderHandle : SafeHandle
    {
        public ProvRecorderHandle() : base(IntPtr.Zero, true) { }
        public override bool IsInvalid => handle == IntPtr.Zero;
        protected override bool ReleaseHandle() { NativeMethods.nf_prov_recorder_free(handle); return true; }
    }

    internal sealed class DeviceKeyHandle : SafeHandle
    {
        public DeviceKeyHandle() : base(IntPtr.Zero, true) { }
        public override bool IsInvalid => handle == IntPtr.Zero;
        protected override bool ReleaseHandle() { NativeMethods.nf_device_key_free(handle); return true; }
    }

    internal sealed class WalHandle : SafeHandle
    {
        public WalHandle() : base(IntPtr.Zero, true) { }
        public override bool IsInvalid => handle == IntPtr.Zero;
        protected override bool ReleaseHandle() { NativeMethods.nf_wal_free(handle); return true; }
    }

    internal sealed class StreamWriterHandle : SafeHandle
    {
        public StreamWriterHandle() : base(IntPtr.Zero, true) { }
        public override bool IsInvalid => handle == IntPtr.Zero;
        protected override bool ReleaseHandle() { NativeMethods.nf_stream_writer_free(handle); return true; }
    }
}
