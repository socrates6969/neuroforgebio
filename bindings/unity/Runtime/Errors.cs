using System;

namespace NeuroForge
{
    /// <summary>nf_status codes (neuroforge.h). New codes may appear in a minor ABI version; treat any
    /// unknown non-zero value as an error.</summary>
    public static class Status
    {
        public const int Ok = 0;
        public const int NullArg = 1;
        public const int InvalidArg = 2;
        public const int Canonical = 3;
        public const int Verify = 4;
        public const int Io = 5;
        public const int NotFound = 6;
        public const int BufferTooSmall = 7;
        public const int Corrupt = 8;
        public const int Unsupported = 9;
        public const int Transport = 10;
        public const int Auth = 11;
        public const int Http = 12;
        public const int Panic = 13;
    }

    /// <summary>A failed NeuroForge core call.</summary>
    public sealed class NeuroForgeException : Exception
    {
        public NeuroForgeException(int status, string message, string detail = "")
            : base(StatusName(status) + ": " + message)
        {
            Status = status;
            NativeMessage = message;
            Detail = detail ?? "";
        }

        /// <summary>The nf_status code (see <see cref="NeuroForge.Status"/>).</summary>
        public int Status { get; }

        /// <summary>The library's message (nf_last_error).</summary>
        public string NativeMessage { get; }

        /// <summary>problem+json for Status.Http, else empty.</summary>
        public string Detail { get; }

        /// <summary>Constant name of a status (NF_OK, NF_ERR_VERIFY, ...), from the library.</summary>
        public static string StatusName(int status) =>
            Native.Utf8.FromPtr(Native.NativeMethods.nf_status_name(status)) ?? "NF_ERR_UNKNOWN";
    }
}
