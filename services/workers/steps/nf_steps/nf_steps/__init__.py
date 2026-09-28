"""nf_steps: step library v1 wrapping MNE-Python (BUILD-GUIDE 3.4, BLUEPRINT §3.5).

Analysis artifacts only (SEC-090): no step writes to or commands acquisition/stimulation hardware.
"""

from nf_steps import decode as _decode  # noqa: F401  (registers decode_lda@1; m3-sweeps 3.6)
from nf_steps.base import (
    PINNED_ENV,
    Library,
    Params,
    Step,
    StepError,
    StepOutput,
    environment,
    get_step,
    parse_ref,
)
from nf_steps.signal import Signal, SignalError
from nf_steps.steps import LIBRARY

__version__ = "1.0.0"

__all__ = [
    "LIBRARY",
    "PINNED_ENV",
    "Library",
    "Params",
    "Signal",
    "SignalError",
    "Step",
    "StepError",
    "StepOutput",
    "__version__",
    "environment",
    "get_step",
    "parse_ref",
]
