"""3.6: the ``nf_steps.decode_lda@1`` metric step (NumPy shrinkage LDA, stratified CV)."""

from __future__ import annotations

import numpy as np
import pytest
from nf_steps import Signal, StepError, get_step, signal
from nf_steps.decode import cross_validate, stratified_folds

DECODE = "nf_steps.decode_lda@1"


def _features(x: np.ndarray, codes, bads=()) -> Signal:
    n_ep, n_ch, n_f = x.shape
    return Signal(
        kind="features",
        data=x,
        sfreq=128.0,
        ch_names=[f"E{i}" for i in range(n_ch)],
        ch_types=["eeg"] * n_ch,
        bads=list(bads),
        meta={
            "event_codes": [int(c) for c in codes],
            "feature_names": [f"f{i}" for i in range(n_f)],
        },
    )


def _two_class(sep: float, n=40, seed=0):
    rng = np.random.default_rng(seed)
    codes = np.array([1, 2] * (n // 2))
    x = rng.lognormal(0.0, 0.3, (n, 3, 2))
    x[codes == 2, :, 0] *= np.exp(sep)
    return x, codes


def test_separable_classes_decode_perfectly_and_the_number_is_in_the_artifact():
    x, codes = _two_class(sep=5.0)
    out = get_step(DECODE)(_features(x, codes), {})
    assert out.info["accuracy"] == 1.0 and out.info["chance_level"] == 0.5
    assert out.signal.data[0, 0, 0] == 1.0
    assert out.signal.meta["decode"]["accuracy"] == 1.0
    assert out.params == get_step(DECODE).resolve({})  # every default explicit


def test_label_free_features_are_near_chance():
    x, codes = _two_class(sep=0.0, n=200, seed=3)
    acc = get_step(DECODE)(_features(x, codes), {}).info["accuracy"]
    assert 0.35 <= acc <= 0.65  # binomial sd at n=200 is 0.035


def test_folds_are_stratified_and_deterministic():
    y = np.array([1, 1, 2, 1, 2, 2, 1, 2, 1, 2])
    f = stratified_folds(y, 5)
    for k in range(5):
        assert sorted(y[f == k].tolist()) == [1, 2]
    x, codes = _two_class(sep=0.3, seed=5)
    feats = np.log10(x.reshape(len(x), -1))
    assert cross_validate(feats, codes, 5, 0.1) == cross_validate(feats, codes, 5, 0.1)


def test_output_is_byte_deterministic():
    x, codes = _two_class(sep=0.5, seed=1)
    a = signal.to_files(get_step(DECODE)(_features(x, codes), {}).signal)
    b = signal.to_files(get_step(DECODE)(_features(x, codes), {}).signal)
    assert a == b


def test_bad_channels_are_excluded():
    x, codes = _two_class(sep=0.0, seed=2)
    x[codes == 2, 0, :] *= 100.0  # only channel E0 carries the label
    assert get_step(DECODE)(_features(x, codes), {}).info["accuracy"] == 1.0
    out = get_step(DECODE)(_features(x, codes, bads=["E0"]), {})
    assert out.info["accuracy"] < 0.8 and out.info["n_features"] == 4


@pytest.mark.parametrize(
    ("codes", "msg"),
    [([1] * 40, "two classes"), ([1] * 37 + [2] * 3, "at least n_folds"), ([1, 2], "one label")],
)
def test_refuses_bad_labels(codes, msg):
    x, _ = _two_class(sep=1.0)
    with pytest.raises(StepError, match=msg):
        get_step(DECODE)(_features(x, codes), {})


def test_refuses_raw_input_and_non_positive_log_features():
    x, codes = _two_class(sep=1.0)
    raw = Signal("raw", np.zeros((2, 10)), 128.0, ["a", "b"], ["eeg", "eeg"])
    with pytest.raises(StepError, match="accepts"):
        get_step(DECODE)(raw, {})
    x[0, 0, 0] = 0.0
    with pytest.raises(StepError, match="positive"):
        get_step(DECODE)(_features(x, codes), {})
    assert get_step(DECODE)(_features(x, codes), {"log": False}).info["n_trials"] == 40
