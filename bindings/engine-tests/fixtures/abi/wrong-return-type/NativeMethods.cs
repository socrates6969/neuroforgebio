// Fixture: nf_widget_open's return type is declared as C# `long` instead of `int` (the header's
// nf_status is a 32-bit int32_t; a 64-bit `long` return corrupts the calling convention on every
// call). abi-conformance.test.mjs asserts the checker reports a return-type mismatch for it.
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

        // BUG (planted): return type is `long`, not `int` (nf_status is int32_t).
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern long nf_widget_open(byte[] name, out WidgetHandle widget);
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern void nf_widget_free(IntPtr widget);
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern int nf_widget_read(WidgetHandle widget, ulong start, ulong stop, byte* output, UIntPtr capacity, out UIntPtr outLen);
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] [return: MarshalAs(UnmanagedType.U1)] internal static extern bool nf_widget_is_ready(WidgetHandle widget);
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern int nf_widget_get_score(WidgetHandle widget, double* scores, UIntPtr nScores, ref NfBuf outLabel);
    }
}
