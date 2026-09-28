// Small helpers shared by the wrappers: UTF-8 in/out, status checks, nf_buf ownership.
using System;
using System.Collections.Generic;
using System.Text;

namespace NeuroForge.Native
{
    internal static class Utf8
    {
        private static readonly UTF8Encoding Strict = new UTF8Encoding(false, true);

        // NUL-terminated UTF-8 for a const char* parameter; null stays null (a NULL pointer).
        internal static byte[] Z(string s)
        {
            if (s == null) return null;
            if (s.IndexOf('\0') >= 0) throw new ArgumentException("string contains a NUL character", nameof(s));
            int n = Strict.GetByteCount(s);
            var b = new byte[n + 1];
            Strict.GetBytes(s, 0, s.Length, b, 0);
            return b;
        }

        internal static byte[] Bytes(string s) => s == null ? throw new ArgumentNullException(nameof(s)) : Strict.GetBytes(s);

        internal static unsafe string FromPtr(IntPtr p)
        {
            if (p == IntPtr.Zero) return null;
            byte* b = (byte*)p;
            int n = 0;
            while (b[n] != 0) n++;
            return Encoding.UTF8.GetString(b, n);
        }
    }

    internal static unsafe class Interop
    {
        // Throw for any non-OK status. Reads nf_last_error on this thread before any other nf_ call.
        internal static void Check(int status)
        {
            if (status == Status.Ok) return;
            string message = Utf8.FromPtr(NativeMethods.nf_last_error()) ?? "";
            string detail = Utf8.FromPtr(NativeMethods.nf_last_error_detail()) ?? "";
            throw new NeuroForgeException(status, message, detail);
        }

        // Copy an nf_buf into managed memory and free it, whatever happens.
        internal static string TakeString(ref NfBuf buf)
        {
            try
            {
                if (buf.Data == IntPtr.Zero) return "";
                return Encoding.UTF8.GetString((byte*)buf.Data, checked((int)(ulong)buf.Len));
            }
            finally { NativeMethods.nf_buf_free(ref buf); }
        }

        internal static byte[] TakeBytes(ref NfBuf buf)
        {
            try
            {
                if (buf.Data == IntPtr.Zero) return Array.Empty<byte>();
                var b = new byte[checked((int)(ulong)buf.Len)];
                if (b.Length > 0) fixed (byte* d = b) Buffer.MemoryCopy((void*)buf.Data, d, b.Length, b.Length);
                return b;
            }
            finally { NativeMethods.nf_buf_free(ref buf); }
        }

        // Call f(out buf); on success return the text, on failure free the buffer and throw.
        internal delegate int BufCall(ref NfBuf buf);

        internal static string Text(BufCall f)
        {
            var buf = default(NfBuf);
            int s;
            try { s = f(ref buf); }
            catch { NativeMethods.nf_buf_free(ref buf); throw; }
            if (s != Status.Ok)
            {
                // Outputs are written only on success, but free defensively (a no-op on an empty buf).
                // Check first: nf_buf_free is itself an nf_ call and would clear the last error.
                try { Check(s); }
                finally { NativeMethods.nf_buf_free(ref buf); }
            }
            return TakeString(ref buf);
        }

        internal static IReadOnlyList<string> Lines(string s) =>
            s.Length == 0 ? Array.Empty<string>() : s.Split('\n');

        internal static UIntPtr Size(int n) => (UIntPtr)(uint)n;
        internal static UIntPtr Size(long n) => (UIntPtr)(ulong)n;
    }
}
