"""Provenance: code / prereg / manifest hashes, package versions, platform, peak RAM; canonical JSON + card hash.

RESEARCH USE ONLY. NOT A MEDICAL DEVICE.
"""
import glob
import hashlib
import json
import math
import os
import platform
import sys
from importlib.metadata import PackageNotFoundError, version

from .data import sha256_file

PKGS = ["numpy", "scipy", "timescoring", "matplotlib", "pytest"]
BLAS_VARS = ["OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"]


def pin_blas_threads():
    """Must be called before numpy is imported (scripts do it at the very top)."""
    for v in BLAS_VARS:
        os.environ[v] = "1"


def package_versions():
    out = {}
    for p in PKGS:
        try:
            out[p] = version(p)
        except PackageNotFoundError:
            out[p] = None
    return out


def code_hashes(code_dir, extra=()):
    files = sorted(glob.glob(os.path.join(code_dir, "nfharness", "*.py"))) + [os.path.join(code_dir, "edf_reader.py")]
    files += list(extra)
    return {os.path.relpath(f, code_dir).replace("\\", "/"): sha256_file(f) for f in files}


def environment():
    return {"python": sys.version.split()[0], "platform": platform.platform(), "machine": platform.machine(),
            "processor": platform.processor(), "blas_threads": {v: os.environ.get(v) for v in BLAS_VARS},
            "packages": package_versions()}


def peak_rss_mb():
    """Peak working set of this process (Windows psapi); None elsewhere."""
    try:
        import ctypes
        from ctypes import wintypes

        class PMC(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                        ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]
        c = PMC()
        c.cb = ctypes.sizeof(PMC)
        k32 = ctypes.WinDLL("kernel32")
        k32.GetCurrentProcess.restype = wintypes.HANDLE
        k32.K32GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PMC), wintypes.DWORD]
        k32.K32GetProcessMemoryInfo.restype = wintypes.BOOL
        if not k32.K32GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(c), c.cb):
            return None
        return c.PeakWorkingSetSize / 2 ** 20
    except Exception:
        try:
            import resource
            return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0
        except Exception:
            return None


def _clean(o):
    """NaN/inf -> strings so the JSON is strict and stable."""
    if isinstance(o, float):
        if math.isnan(o):
            return "NaN"
        if math.isinf(o):
            return "Infinity" if o > 0 else "-Infinity"
        return o
    if isinstance(o, dict):
        return {str(k): _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if hasattr(o, "item") and not isinstance(o, (str, bytes)):
        return _clean(o.item())
    return o


def dumps(obj):
    """Canonical serialisation: sorted keys, repr() floats (Python json uses float.__repr__)."""
    return json.dumps(_clean(obj), sort_keys=True, indent=1, allow_nan=False)


def card_hash(card):
    """SHA-256 of the card with the 'runtime' block removed (N1 c3)."""
    c = {k: v for k, v in card.items() if k != "runtime"}
    return hashlib.sha256(dumps(c).encode("utf-8")).hexdigest()


def sha256_text(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()
