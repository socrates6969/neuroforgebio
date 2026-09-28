// Fixture: nf_widget_read's `size_t capacity` is declared as C# `int` instead of `UIntPtr` (the
// classic 32-vs-64-bit size_t bug). abi-conformance.test.mjs asserts the checker reports a
// type mismatch on that one parameter, with the param count and every other function matching.
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
        // BUG (planted): `capacity` is `int`, not `UIntPtr` -- truncates size_t on 64-bit callers.
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern int nf_widget_read(WidgetHandle widget, ulong start, ulong stop, byte* output, int capacity, out UIntPtr outLen);
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] [return: MarshalAs(UnmanagedType.U1)] internal static extern bool nf_widget_is_ready(WidgetHandle widget);
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern int nf_widget_get_score(WidgetHandle widget, double* scores, UIntPtr nScores, ref NfBuf outLabel);
    }
}
