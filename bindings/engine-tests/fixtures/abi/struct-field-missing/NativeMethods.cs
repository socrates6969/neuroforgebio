// Fixture: NfBuf is missing its `Len` field (1 field instead of the header nf_buf's 2). Every
// [DllImport] signature is otherwise identical to the "ok" fixture, so this is a pure
// struct-layout regression. abi-conformance.test.mjs asserts the checker reports a field-count
// mismatch under structMismatches for NfBuf, with every function-level check still passing.
using System;
using System.Runtime.InteropServices;

namespace Fixture.Native
{
    [StructLayout(LayoutKind.Sequential)]
    internal struct NfBuf
    {
        public IntPtr Data;
        // BUG (planted): `public UIntPtr Len;` dropped -- the header's nf_buf still has `size_t len`.
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
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] [return: MarshalAs(UnmanagedType.U1)] internal static extern bool nf_widget_is_ready(WidgetHandle widget);
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern int nf_widget_get_score(WidgetHandle widget, double* scores, UIntPtr nScores, ref NfBuf outLabel);
    }
}
