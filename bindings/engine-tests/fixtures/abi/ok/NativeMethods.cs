// Fixture: a correct binding of fixtures/abi/header.h. abi-conformance.test.mjs asserts this
// produces zero mismatches and zero missing-in-header entries.
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
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] [return: MarshalAs(UnmanagedType.U1)] internal static extern bool nf_widget_is_ready(WidgetHandle widget);
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] internal static extern int nf_widget_get_score(WidgetHandle widget, double* scores, UIntPtr nScores, ref NfBuf outLabel);
    }
}
