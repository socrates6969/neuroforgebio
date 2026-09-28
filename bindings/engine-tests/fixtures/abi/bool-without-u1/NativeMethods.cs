// Fixture: nf_widget_is_ready's `bool` return is missing `[return: MarshalAs(UnmanagedType.U1)]`.
// Without it, the CLR marshals a 4-byte Win32 BOOL, misreading the C ABI's 1-byte C99 bool.
// abi-conformance.test.mjs asserts the checker reports a return-type mismatch for it.
using System;
using System.Runtime.InteropServices;

namespace Fixture.Native
{
    [StructLayout(LayoutKind.Sequential)]
    internal struct NfBuf
    {
        public IntPtr Data;
        public UIntPtr Len;
    }

    internal sealed class WidgetHandle : SafeHandle
    {
        public WidgetHandle() : base(IntPtr.Zero, true) { }
        public override bool IsInvalid => handle == IntPtr.Zero;
        protected override bool ReleaseHandle() { NativeMethods.nf_widget_free(handle); return true; }
    }

    internal static unsafe class NativeMethods
    {
        internal const string Lib = "fixture";

        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern int nf_widget_open(byte[] name, out WidgetHandle widget);
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern void nf_widget_free(IntPtr widget);
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern int nf_widget_read(WidgetHandle widget, ulong start, ulong stop, byte* output, UIntPtr capacity, out UIntPtr outLen);
        // BUG (planted): missing [return: MarshalAs(UnmanagedType.U1)].
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern bool nf_widget_is_ready(WidgetHandle widget);
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern int nf_widget_get_score(WidgetHandle widget, double* scores, UIntPtr nScores, ref NfBuf outLabel);
    }
}
