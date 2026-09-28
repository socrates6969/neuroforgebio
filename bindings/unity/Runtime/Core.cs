using System;
using NeuroForge.Native;

namespace NeuroForge
{
    /// <summary>Sample data types (hashing.md sec. 5.2). The values are the ABI codes.</summary>
    public enum Dtype
    {
        Int8 = 1, Uint8 = 2, Int16 = 3, Uint16 = 4, Int32 = 5, Uint32 = 6, Int64 = 7, Float32 = 8, Float64 = 9,
    }

    /// <summary>Version and compatibility of the loaded native library.</summary>
    public static class NeuroForgeCore
    {
        /// <summary>ABI version this C# package was written against (neuroforge.h).</summary>
        public const int AbiMajor = 1, AbiMinor = 2; // 1.1: nf_recording_read_f64; 1.2: keyed nf_wal_open, nf_wal_open_ephemeral

        /// <summary>ABI version of the loaded library as (major, minor, patch).</summary>
        public static (int Major, int Minor, int Patch) AbiVersion
        {
            get
            {
                uint v = NativeMethods.nf_abi_version();
                return ((int)(v >> 16), (int)((v >> 8) & 0xff), (int)(v & 0xff));
            }
        }

        /// <summary>Whether the loaded library can serve this package: same major, minor at least ours.</summary>
        public static bool IsCompatible => IsAbiCompatible(NativeMethods.nf_abi_version());

        /// <summary>The compatibility rule of neuroforge.h for a packed <c>major &lt;&lt; 16 | minor &lt;&lt; 8 | patch</c>
        /// version: same major, minor at least ours.</summary>
        public static bool IsAbiCompatible(uint packedVersion) =>
            (packedVersion >> 16) == AbiMajor && ((packedVersion >> 8) & 0xff) >= AbiMinor;

        /// <summary>Throw if the loaded library is not compatible (call once at startup).</summary>
        public static void EnsureCompatible()
        {
            if (!IsCompatible)
            {
                var v = AbiVersion;
                throw new InvalidOperationException(
                    $"neuroforge native library ABI {v.Major}.{v.Minor}.{v.Patch} is not compatible with this package (needs {AbiMajor}.{AbiMinor}+)");
            }
        }

        /// <summary>Version of nf-core inside the native library.</summary>
        public static string Version => Utf8.FromPtr(NativeMethods.nf_core_version());

        public static string DtypeName(Dtype d) => Utf8.FromPtr(NativeMethods.nf_dtype_name((int)d));

        public static int ItemSize(Dtype d) => (int)(ulong)NativeMethods.nf_dtype_itemsize((int)d);

        /// <summary>The dtype a C# element type stands for. Types are matched exactly, not by size, so
        /// an int can never be written as float32 bits (or the reverse).</summary>
        public static Dtype DtypeOf<T>() where T : unmanaged
        {
            Type t = typeof(T);
            if (t == typeof(sbyte)) return Dtype.Int8;
            if (t == typeof(byte)) return Dtype.Uint8;
            if (t == typeof(short)) return Dtype.Int16;
            if (t == typeof(ushort)) return Dtype.Uint16;
            if (t == typeof(int)) return Dtype.Int32;
            if (t == typeof(uint)) return Dtype.Uint32;
            if (t == typeof(long)) return Dtype.Int64;
            if (t == typeof(float)) return Dtype.Float32;
            if (t == typeof(double)) return Dtype.Float64;
            throw new ArgumentException($"{t.Name} is not a NeuroForge sample type");
        }

        internal static void CheckElementType<T>(Dtype expected) where T : unmanaged
        {
            Dtype got = DtypeOf<T>();
            if (got != expected)
                throw new ArgumentException($"element type {typeof(T).Name} is {got}, but the dtype is {expected}");
        }

        public static Dtype ParseDtype(string name)
        {
            Interop.Check(NativeMethods.nf_dtype_parse(Utf8.Z(name), out int d));
            return (Dtype)d;
        }
    }
}
