// A local nf-signal/1 recording (level 0), read-only. The header does not declare nf_recording
// thread-safe, so every native call on one Recording is serialised with a lock; different
// Recordings are independent.
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using NeuroForge.Native;

namespace NeuroForge
{
    public sealed unsafe class Recording : IDisposable
    {
        private readonly RecordingHandle _h;
        private readonly object _lock = new object();
        private byte[] _scratch = Array.Empty<byte>();
        private double[] _scratchF64 = Array.Empty<double>();

        private Recording(RecordingHandle h, NfRecordingInfo info, string[] names, string[] units)
        {
            _h = h;
            SampleCount = checked((long)info.NSamples);
            ChannelCount = checked((int)info.NChannels);
            SampleRate = info.Sfreq;
            Dtype = (Dtype)info.Dtype;
            HasTimestamps = info.HasTimestamps != 0;
            ItemSize = NeuroForgeCore.ItemSize(Dtype);
            ChannelNames = names;
            ChannelUnits = units;
        }

        /// <summary>Open recording <paramref name="recordingId"/> under the Zarr root directory <paramref name="root"/>.</summary>
        public static Recording Open(string root, string recordingId)
        {
            byte[] r = Utf8.Z(root ?? throw new ArgumentNullException(nameof(root)));
            byte[] id = Utf8.Z(recordingId ?? throw new ArgumentNullException(nameof(recordingId)));
            int s = NativeMethods.nf_recording_open(r, id, out RecordingHandle h);
            if (s != Status.Ok) { h?.Dispose(); Interop.Check(s); }
            try
            {
                Interop.Check(NativeMethods.nf_recording_get_info(h, out NfRecordingInfo info));
                var names = new string[checked((int)info.NChannels)];
                var units = new string[names.Length];
                for (int i = 0; i < names.Length; i++)
                {
                    ulong idx = (ulong)i;
                    names[i] = Interop.Text((ref NfBuf o) => NativeMethods.nf_recording_channel_name(h, idx, ref o));
                    units[i] = Interop.Text((ref NfBuf o) => NativeMethods.nf_recording_channel_unit(h, idx, ref o));
                }
                return new Recording(h, info, names, units);
            }
            catch { h.Dispose(); throw; }
        }

        public long SampleCount { get; }
        public int ChannelCount { get; }
        /// <summary>Sampling frequency in Hz.</summary>
        public double SampleRate { get; }
        /// <summary>Stored dtype (int16, int32, int64, float32 or float64) of <see cref="ReadRaw"/>; <see cref="Read(long,int,Span{double})"/> returns physical values.</summary>
        public Dtype Dtype { get; }
        public bool HasTimestamps { get; }
        public int ItemSize { get; }
        public IReadOnlyList<string> ChannelNames { get; }
        public IReadOnlyList<string> ChannelUnits { get; }

        public bool IsDisposed => _h.IsClosed;

        /// <summary>Rows (samples) available from <paramref name="start"/>, capped at <paramref name="count"/>.</summary>
        public int RowsAvailable(long start, int count)
        {
            if (start < 0) throw new ArgumentOutOfRangeException(nameof(start));
            if (count < 0) throw new ArgumentOutOfRangeException(nameof(count));
            return (int)Math.Max(0, Math.Min(count, SampleCount - start));
        }

        /// <summary>Read raw little-endian samples of the stored dtype, row-major [rows][channels].
        /// Returns the number of rows read (clamped to the end of the recording).</summary>
        public int ReadRaw(long start, int count, Span<byte> dest)
        {
            int rows = RowsAvailable(start, count);
            if (rows == 0) return 0;
            int need = checked(rows * ChannelCount * ItemSize);
            if (dest.Length < need) throw new ArgumentException($"destination needs {need} bytes", nameof(dest));
            int rowBytes = ChannelCount * ItemSize;
            lock (_lock)
            {
                ThrowIfDisposed();
                fixed (byte* d = dest)
                {
                    for (int done = 0; done < rows;)
                    {
                        int r = Math.Min(rows - done, RowsPerCall);
                        int bytes = r * rowBytes;
                        Interop.Check(NativeMethods.nf_recording_read(_h, (ulong)(start + done), (ulong)(start + done + r), d + (long)done * rowBytes, Interop.Size(bytes), out UIntPtr got));
                        if ((ulong)got != (ulong)bytes) throw new NeuroForgeException(Status.Corrupt, $"read returned {got} bytes, expected {bytes}");
                        done += r;
                    }
                }
            }
            return rows;
        }

        public const int DefaultMaxStoredBytesPerCall = 64 << 20;
        private int _maxStoredBytesPerCall = DefaultMaxStoredBytesPerCall;

        /// <summary>Most stored bytes one native read may cover (default 64 MiB). The core refuses single
        /// reads over 1 GiB (ABI 1.2 hardening), so long reads are split into pieces of this size; a
        /// value below one row still reads one row per call.</summary>
        public int MaxStoredBytesPerCall
        {
            get => _maxStoredBytesPerCall;
            set
            {
                if (value <= 0 || value > (1 << 30)) throw new ArgumentOutOfRangeException(nameof(value), "1 byte .. 1 GiB");
                _maxStoredBytesPerCall = value;
            }
        }

        // Rows per native call so that rows * channels * itemsize <= MaxStoredBytesPerCall (at least 1).
        private int RowsPerCall => Math.Max(1, MaxStoredBytesPerCall / Math.Max(1, ChannelCount * ItemSize));

        /// <summary>Read PHYSICAL values (stored * scale + offset per channel, in <see cref="ChannelUnits"/>;
        /// ABI 1.1 nf_recording_read_f64), row-major [rows][channels]. Returns the rows read.</summary>
        public int Read(long start, int count, Span<double> dest)
        {
            int rows = RowsAvailable(start, count);
            if (rows == 0) return 0;
            int n = checked(rows * ChannelCount);
            if (dest.Length < n) throw new ArgumentException($"destination needs {n} values", nameof(dest));
            lock (_lock)
            {
                ThrowIfDisposed();
                fixed (double* d = dest)
                {
                    for (int done = 0; done < rows;)
                    {
                        int r = Math.Min(rows - done, RowsPerCall);
                        int values = r * ChannelCount;
                        Interop.Check(NativeMethods.nf_recording_read_f64(_h, (ulong)(start + done), (ulong)(start + done + r), d + (long)done * ChannelCount, Interop.Size(values), out UIntPtr got));
                        if ((ulong)got != (ulong)values) throw new NeuroForgeException(Status.Corrupt, $"read returned {got} values, expected {values}");
                        done += r;
                    }
                }
            }
            return rows;
        }

        /// <summary>As <see cref="Read(long,int,Span{double})"/>, narrowed to float (Unity-friendly).</summary>
        public int Read(long start, int count, Span<float> dest)
        {
            int rows = RowsAvailable(start, count);
            if (rows == 0) return 0;
            int n = checked(rows * ChannelCount);
            if (dest.Length < n) throw new ArgumentException($"destination needs {n} values", nameof(dest));
            lock (_lock)
            {
                if (_scratchF64.Length < n) _scratchF64 = new double[n];
                Read(start, rows, _scratchF64.AsSpan(0, n));
                for (int i = 0; i < n; i++) dest[i] = (float)_scratchF64[i];
            }
            return rows;
        }

        /// <summary>Read STORED values (no scale/offset) converted to double. int64 values beyond 2^53
        /// lose precision. Returns the rows read.</summary>
        public int ReadStored(long start, int count, Span<double> dest)
        {
            int rows = RowsAvailable(start, count);
            if (rows == 0) return 0;
            int n = checked(rows * ChannelCount);
            if (dest.Length < n) throw new ArgumentException($"destination needs {n} values", nameof(dest));
            lock (_lock)
            {
                byte[] raw = Scratch(checked(n * ItemSize));
                ReadRaw(start, rows, raw);
                Convert(raw, n, dest);
            }
            return rows;
        }

        /// <summary>Read timestamps (seconds). Throws with Status.NotFound when the recording has none.</summary>
        public int ReadTimestamps(long start, int count, Span<double> dest)
        {
            int rows = RowsAvailable(start, count);
            if (rows == 0) return 0;
            if (dest.Length < rows) throw new ArgumentException($"destination needs {rows} values", nameof(dest));
            lock (_lock)
            {
                ThrowIfDisposed();
                fixed (double* d = dest)
                {
                    int tsPerCall = Math.Max(1, MaxStoredBytesPerCall / sizeof(double));
                    for (int done = 0; done < rows;)
                    {
                        int r = Math.Min(rows - done, tsPerCall);
                        Interop.Check(NativeMethods.nf_recording_read_timestamps(_h, (ulong)(start + done), (ulong)(start + done + r), d + done, Interop.Size(r), out UIntPtr got));
                        if ((ulong)got != (ulong)r) throw new NeuroForgeException(Status.Corrupt, $"read returned {got} timestamps, expected {r}");
                        done += r;
                    }
                }
            }
            return rows;
        }

        public void Dispose()
        {
            lock (_lock) _h.Dispose();
        }

        private void ThrowIfDisposed()
        {
            if (_h.IsClosed) throw new ObjectDisposedException(nameof(Recording));
        }

        private byte[] Scratch(int n)
        {
            if (_scratch.Length < n) _scratch = new byte[n];
            return _scratch;
        }

        private void Convert(byte[] raw, int n, Span<double> dest)
        {
            if (!BitConverter.IsLittleEndian) throw new PlatformNotSupportedException("big-endian host");
            var src = new ReadOnlySpan<byte>(raw, 0, n * ItemSize);
            switch (Dtype)
            {
                case Dtype.Int8: { var v = MemoryMarshal.Cast<byte, sbyte>(src); for (int i = 0; i < n; i++) dest[i] = v[i]; break; }
                case Dtype.Uint8: { for (int i = 0; i < n; i++) dest[i] = src[i]; break; }
                case Dtype.Int16: { var v = MemoryMarshal.Cast<byte, short>(src); for (int i = 0; i < n; i++) dest[i] = v[i]; break; }
                case Dtype.Uint16: { var v = MemoryMarshal.Cast<byte, ushort>(src); for (int i = 0; i < n; i++) dest[i] = v[i]; break; }
                case Dtype.Int32: { var v = MemoryMarshal.Cast<byte, int>(src); for (int i = 0; i < n; i++) dest[i] = v[i]; break; }
                case Dtype.Uint32: { var v = MemoryMarshal.Cast<byte, uint>(src); for (int i = 0; i < n; i++) dest[i] = v[i]; break; }
                case Dtype.Int64: { var v = MemoryMarshal.Cast<byte, long>(src); for (int i = 0; i < n; i++) dest[i] = v[i]; break; }
                case Dtype.Float32: { var v = MemoryMarshal.Cast<byte, float>(src); for (int i = 0; i < n; i++) dest[i] = v[i]; break; }
                case Dtype.Float64: { MemoryMarshal.Cast<byte, double>(src).CopyTo(dest); break; }
                default: throw new NeuroForgeException(Status.InvalidArg, $"unknown dtype code {(int)Dtype}");
            }
        }
    }
}
