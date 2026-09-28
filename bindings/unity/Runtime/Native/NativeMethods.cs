// P/Invoke declarations for bindings/c/include/neuroforge.h (ABI 1.2). Hand-written, 1:1 with the
// header; keep the order of the header so a diff against it is easy to review.
//
// Marshalling rules (DESIGN.md):
// - const char* inputs are NUL-terminated UTF-8 byte[] built by Utf8.Z (never CharSet marshalling,
//   whose default differs between Mono and CoreCLR).
// - Returned const char* are IntPtr decoded by Utf8.FromPtr; library buffers are NfBuf, freed with
//   nf_buf_free.
// - C bool is one byte: MarshalAs(U1) on parameters and returns, byte fields in structs.
// - size_t is UIntPtr. Opaque handles are SafeHandle subclasses (Handles.cs).
//
// Not declared in v0: the streaming sender and the API client, which need callback tables
// (nf_ingest_transport, nf_http_transport, nf_token_source). See DESIGN.md "Out of scope".
// No function here sends anything to acquisition hardware (SEC-090/091).
using System;
using System.Runtime.InteropServices;

namespace NeuroForge.Native
{
    [StructLayout(LayoutKind.Sequential)]
    internal struct NfBuf
    {
        public IntPtr Data;
        public UIntPtr Len;
    }

    [StructLayout(LayoutKind.Sequential)]
    internal struct NfRecordingInfo
    {
        public ulong NSamples;
        public ulong NChannels;
        public double Sfreq;
        public int Dtype;
        public byte HasTimestamps;
    }

    [StructLayout(LayoutKind.Sequential)]
    internal struct NfWriterStats
    {
        public ulong Chunks;
        public ulong Samples;
        public ulong WalPeak;
    }

    [StructLayout(LayoutKind.Sequential)]
    internal unsafe struct NfStreamChunkFields
    {
        public byte* StreamId;
        public ulong Seq;
        public uint NSamples;
        public uint NChannels;
        public byte* ChunkId;
        public double* LslTimestamps;
        public UIntPtr NTimestamps;
        public double* ClockOffsets;
        public UIntPtr NClockOffsets;
        public double* LocalClock;
        public UIntPtr NLocalClock;
    }

    internal static unsafe class NativeMethods
    {
        internal const string Lib = "neuroforge";

        // ---- version, errors, memory
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern uint nf_abi_version();
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern IntPtr nf_core_version();
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern IntPtr nf_status_name(int status);
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern IntPtr nf_last_error();
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern IntPtr nf_last_error_detail();
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern void nf_buf_free(ref NfBuf buf);
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern IntPtr nf_dtype_name(int dtype);
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern UIntPtr nf_dtype_itemsize(int dtype);
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern int nf_dtype_parse(byte[] name, out int dtype);

        // ---- hashing spec v1
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern int nf_canonicalize(byte* json, UIntPtr len, ref NfBuf outCanonical);
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern int nf_format_number(double x, ref NfBuf outText);
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern int nf_blob_id(byte* data, UIntPtr len, ref NfBuf outId);
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern int nf_blob_id_file(byte[] path, ref NfBuf outId, out ulong outSize);
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern int nf_pipeline_version_id(byte* spec, UIntPtr len, ref NfBuf outId);
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern int nf_chunk_id(int dtype, ulong* shape, UIntPtr rank, byte* data, UIntPtr dataLen, ref NfBuf outId);
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern int nf_prov_batch_id(byte* batch, UIntPtr len, ref NfBuf outId);
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern int nf_verify_prov_chain(byte* batches, UIntPtr len, ref NfBuf outIds);
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] [return: MarshalAs(UnmanagedType.U1)] internal static extern bool nf_is_valid_id(byte[] id);

        // ---- hashing spec v2
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] [return: MarshalAs(UnmanagedType.U1)] internal static extern bool nf_is_valid_id_v2(byte[] id);
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern int nf_audit_batch_id(byte* batch, UIntPtr len, ref NfBuf outId);
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern int nf_verify_audit_chain(byte* batches, UIntPtr len, ref NfBuf outIds);
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern int nf_prov_node_hash(byte* record, UIntPtr len, ref NfBuf outHash);
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern int nf_consent_record_hash(byte* record, UIntPtr len, ref NfBuf outHash);
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern int nf_verify_consent_chain(byte* records, UIntPtr len, ref NfBuf outHashes);
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern int nf_ruleset_content_sha256(byte* rules, UIntPtr len, ref NfBuf outHash);
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern int nf_sweep_variant_label(byte[] basePvId, byte* paramsJson, UIntPtr len, ref NfBuf outLabel);
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern int nf_training_subject_hash(byte[] tenantId, byte[] subjectId, ref NfBuf outHash);
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern int nf_training_manifest_build(byte* args, UIntPtr len, ref NfBuf outManifest);
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern int nf_training_manifest_digest(byte* manifest, UIntPtr len, ref NfBuf outDigest);
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern int nf_timing_sha256(double* lsl, UIntPtr nLsl, double* offsets, UIntPtr nOffsets, double* local, UIntPtr nLocal, ref NfBuf outHash);

        // ---- signature verification
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern int nf_verify_stream_chunk(ref NfStreamChunkFields fields, byte* signature, UIntPtr signatureLen, byte* publicKey, [MarshalAs(UnmanagedType.U1)] out bool valid);
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern int nf_verify_device_token(byte[] token, byte* publicKey, long nowUnixS, ref NfBuf outClaims);
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern int nf_verify_provb_signature(byte[] batchId, byte* signature, UIntPtr signatureLen, byte* publicKey, [MarshalAs(UnmanagedType.U1)] out bool valid);
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern int nf_verify_anchor(byte* anchor, UIntPtr len, byte* publicKey, [MarshalAs(UnmanagedType.U1)] out bool valid);
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern int nf_verify_certificate(byte* certificate, UIntPtr len, byte* publicKey, [MarshalAs(UnmanagedType.U1)] out bool valid);

        // ---- local recordings (read-only)
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern int nf_recording_open(byte[] root, byte[] recordingId, out RecordingHandle recording);
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern void nf_recording_free(IntPtr recording);
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern int nf_recording_get_info(RecordingHandle recording, out NfRecordingInfo info);
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern int nf_recording_channel_name(RecordingHandle recording, ulong index, ref NfBuf outName);
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern int nf_recording_channel_unit(RecordingHandle recording, ulong index, ref NfBuf outUnit);
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern int nf_recording_read(RecordingHandle recording, ulong start, ulong stop, byte* output, UIntPtr capacity, out UIntPtr outLen);
        // ABI 1.1
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern int nf_recording_read_f64(RecordingHandle recording, ulong start, ulong stop, double* output, UIntPtr capacity, out UIntPtr outCount);
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern int nf_recording_read_timestamps(RecordingHandle recording, ulong start, ulong stop, double* output, UIntPtr capacity, out UIntPtr outCount);

        // ---- chunk cache (read-only)
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern int nf_chunk_cache_open(byte[] root, ulong maxBytes, out ChunkCacheHandle cache);
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern void nf_chunk_cache_free(IntPtr cache);
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern int nf_chunk_cache_get(ChunkCacheHandle cache, byte[] chunkId, out ChunkHandle chunk);
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern int nf_chunk_cache_size(ChunkCacheHandle cache, out ulong bytes);
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern void nf_chunk_free(IntPtr chunk);
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern int nf_chunk_dtype(ChunkHandle chunk);
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern UIntPtr nf_chunk_rank(ChunkHandle chunk);
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern ulong* nf_chunk_shape(ChunkHandle chunk);
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern byte* nf_chunk_data(ChunkHandle chunk, out UIntPtr len);

        // ---- provenance recorder
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern int nf_prov_recorder_open(byte[] dir, byte[] chain, out ProvRecorderHandle recorder);
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern void nf_prov_recorder_free(IntPtr recorder);
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern int nf_prov_recorder_record(ProvRecorderHandle recorder, byte* records, UIntPtr len, out ulong seq, ref NfBuf outId);
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern int nf_prov_recorder_len(ProvRecorderHandle recorder, out UIntPtr len);
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern int nf_prov_recorder_head(ProvRecorderHandle recorder, out ulong seq, ref NfBuf outId);
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern int nf_prov_recorder_pending_count(ProvRecorderHandle recorder, out UIntPtr count);
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern int nf_prov_recorder_pending(ProvRecorderHandle recorder, UIntPtr index, out ulong seq, ref NfBuf outId, ref NfBuf outCanonical);
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern int nf_prov_recorder_mark_synced(ProvRecorderHandle recorder, ulong seq);

        // ---- streaming: keys, WAL, writer (the sender needs callbacks and is not in v0)
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern int nf_device_key_generate(out DeviceKeyHandle key);
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern int nf_device_key_from_seed(byte* seed, UIntPtr seedLen, out DeviceKeyHandle key);
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern int nf_device_key_open_sealed(byte[] path, out DeviceKeyHandle key);
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern void nf_device_key_free(IntPtr key);
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern int nf_device_key_public_key(DeviceKeyHandle key, byte* outPublicKey);
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern int nf_device_key_token(DeviceKeyHandle key, byte[] tenantId, byte[] deviceId, byte[] streamId, ulong lifetimeS, ref NfBuf outToken);
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern int nf_wal_open(byte[] dir, byte[] streamId, byte* key32, byte[] dpapiKeyPath, [MarshalAs(UnmanagedType.U1)] bool fsync, out WalHandle wal);
        // ABI 1.2: tests and throwaway sessions only (random in-memory key). Wrapped only as Wal.OpenEphemeralForTesting.
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern int nf_wal_open_ephemeral(byte[] dir, byte[] streamId, [MarshalAs(UnmanagedType.U1)] bool fsync, out WalHandle wal);
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern void nf_wal_free(IntPtr wal);
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern int nf_wal_len(WalHandle wal, out UIntPtr len);
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern int nf_stream_writer_new(byte[] streamId, int dtype, uint nChannels, uint chunkSamples, DeviceKeyHandle key, WalHandle wal, out StreamWriterHandle writer);
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern void nf_stream_writer_free(IntPtr writer);
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern int nf_stream_writer_push(StreamWriterHandle writer, byte* samples, UIntPtr samplesLen, double* timestamps, UIntPtr nTimestamps, out UIntPtr outChunks);
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern int nf_stream_writer_add_clock_offset(StreamWriterHandle writer, double collectionTime, double offset);
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern int nf_stream_writer_add_local_clock(StreamWriterHandle writer, double lslTime, double monotonicTime);
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern int nf_stream_writer_flush(StreamWriterHandle writer, [MarshalAs(UnmanagedType.U1)] out bool wrote);
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern int nf_stream_writer_next_seq(StreamWriterHandle writer, out ulong seq);
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern int nf_stream_writer_buffered_samples(StreamWriterHandle writer, out UIntPtr samples);
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern int nf_stream_writer_get_stats(StreamWriterHandle writer, out NfWriterStats stats);
    }
}
