"""Named exceptions raised by the harness guards (one per forbidden operation / split rule).

RESEARCH USE ONLY. NOT A MEDICAL DEVICE.
IDs refer to notes\\harness_requirements.md (S*, F*) and prereg\\N1_harness_controls.md (d).
"""


class HarnessViolation(Exception):
    """Base class: the harness refused an operation that could leak test information."""
    rule = "?"


class NormaliserLeakError(HarnessViolation):          # F1
    rule = "F1"


class ConfigLockError(HarnessViolation):              # F2 (config hash / search on test files)
    rule = "F2"


class ThresholdSelectionError(HarnessViolation):      # F3 (tau on non-train_oof scores, off-grid tau, k/n changed)
    rule = "F3"


class WindowBoundaryError(HarnessViolation):          # F4 (window crosses a file / partition, buffer)
    rule = "F4"


class ResamplingLeakError(HarnessViolation):          # F5
    rule = "F5"


class CausalSplitError(HarnessViolation):             # F6
    rule = "F6"


class FeatureWhitelistError(HarnessViolation):        # F7
    rule = "F7"


class TestLabelAccessError(HarnessViolation):         # F8
    rule = "F8"


class ScorerParameterError(HarnessViolation):         # F9
    rule = "F9"


class SubjectOverlapError(HarnessViolation):          # S1
    rule = "S1"


class RandomSplitForbiddenError(HarnessViolation):    # S5
    rule = "S5"


class SplitHashError(HarnessViolation):               # S7
    rule = "S7"


class InputHashError(HarnessViolation):               # N1 (c)1
    rule = "C-hash"
