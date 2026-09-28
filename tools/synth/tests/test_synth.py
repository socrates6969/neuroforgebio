"""Local tests (numpy only): ground truth is recoverable, generation is deterministic, and the
hand-written EDF/BDF/BrainVision/XDF files decode back to the generated data."""

from __future__ import annotations

import json
import struct

import numpy as np
import pytest
from nf_synth import SynthParams, data_sha256, generate, welch_psd
from nf_synth.writers import write_bdf, write_brainvision, write_edf, write_truth, write_xdf

P = SynthParams(seed=7)


@pytest.fixture(scope="module")
def synth():
    return generate(P)


def test_shape_and_truth(synth):
    data, truth = synth
    assert data.shape == (8, P.sfreq * P.duration_s)
    assert truth["channels"] == ["Fp1", "Fp2", "F3", "F4", "C3", "C4", "P3", "P4"]
    assert truth["n_samples"] == data.shape[1]
    assert [e["code"] for e in truth["events"][:3]] == [1, 2, 1]
    assert truth["bad_channels"][0]["name"] == "C3"
    json.dumps(truth)  # serialisable


def test_deterministic_for_fixed_seed(synth):
    data, truth = synth
    data2, truth2 = generate(P)
    assert data_sha256(data) == data_sha256(data2) == truth["data_sha256"]
    assert truth == truth2
    data3, _ = generate(SynthParams(seed=8))
    assert data_sha256(data3) != truth["data_sha256"]


@pytest.mark.parametrize("seed", [0, 1, 7, 12345])
@pytest.mark.parametrize("alpha", [8.5, 10.0, 11.75])
def test_psd_peak_within_one_bin_of_injected_alpha(seed, alpha):
    p = SynthParams(seed=seed, alpha_freq_hz=alpha)
    data, truth = generate(p)
    ch = truth["channels"].index("P3")  # posterior: full alpha amplitude
    nperseg = 4 * p.sfreq  # 0.25 Hz bins
    f, psd = welch_psd(data[ch], p.sfreq, nperseg)
    band = (f >= 7) & (f <= 14)
    peak = f[band][np.argmax(psd[band])]
    assert abs(peak - alpha) <= f[1] - f[0], (peak, alpha)


def test_line_noise_and_bad_channel_visible(synth):
    data, truth = synth
    f, psd = welch_psd(data[truth["channels"].index("P4")], P.sfreq, 2 * P.sfreq)
    i50 = np.argmin(abs(f - 50))
    neighbours = np.r_[psd[i50 - 6 : i50 - 2], psd[i50 + 3 : i50 + 7]]
    assert psd[i50] > 10 * np.median(neighbours)
    sd = data.std(axis=1)
    bad = truth["channels"].index("C3")
    assert sd[bad] > 5 * np.median(np.delete(sd, bad))


def test_blinks_on_frontal_channels(synth):
    data, truth = synth
    b = truth["blinks"][0]
    s0 = int(b["onset_s"] * P.sfreq)
    seg = slice(s0, s0 + int(0.3 * P.sfreq))
    fp1 = truth["channels"].index("Fp1")
    assert data[fp1, seg].max() > 60


# ---------------------------------------------------------------- minimal readers for round trips
def read_edf_like(path, bdf=False):
    raw = path.read_bytes()
    ns = int(raw[252:256])
    h = raw[256 : 256 * (ns + 1)]

    def fields(offset, width):
        return [
            h[offset * ns + i * width : offset * ns + (i + 1) * width].decode().strip()
            for i in range(ns)
        ]

    labels = fields(0, 16)
    off = 16 + 80 + 8
    pmin = [float(x) for x in fields(off, 8)]
    pmax = [float(x) for x in fields(off + 8, 8)]
    dmin = [int(x) for x in fields(off + 16, 8)]
    dmax = [int(x) for x in fields(off + 24, 8)]
    spr = [int(x) for x in fields(off + 32 + 80, 8)]
    n_rec = int(raw[236:244])
    w = 3 if bdf else 2
    body = raw[256 * (ns + 1) :]
    sigs = [[] for _ in range(ns)]
    ann = b""
    pos = 0
    for _ in range(n_rec):
        for i in range(ns):
            chunk = body[pos : pos + spr[i] * w]
            pos += spr[i] * w
            if labels[i].endswith("Annotations"):
                ann += chunk
                continue
            if bdf:
                v = [
                    int.from_bytes(chunk[k : k + 3], "little", signed=True)
                    for k in range(0, len(chunk), 3)
                ]
            else:
                v = list(struct.unpack(f"<{spr[i]}h", chunk))
            sigs[i].extend(v)
    out = []
    for i in range(ns):
        if labels[i].endswith("Annotations"):
            continue
        d = np.array(sigs[i], dtype=float)
        out.append((d - dmin[i]) / (dmax[i] - dmin[i]) * (pmax[i] - pmin[i]) + pmin[i])
    step = [(pmax[i] - pmin[i]) / (dmax[i] - dmin[i]) for i in range(len(out))]
    return labels, np.array(out), np.array(step), ann, raw


@pytest.mark.parametrize("bdf", [False, True])
def test_edf_bdf_round_trip(tmp_path, synth, bdf):
    data, truth = synth
    path = (write_bdf if bdf else write_edf)(tmp_path / ("x.bdf" if bdf else "x.edf"), data, truth)
    labels, back, step, ann, raw = read_edf_like(path, bdf=bdf)
    assert labels[:-1] == truth["channels"]
    assert labels[-1] == ("BDF Annotations" if bdf else "EDF Annotations")
    assert raw[:8] == (b"\xffBIOSEMI" if bdf else b"0       ")
    assert raw[192:197] == (b"BDF+C" if bdf else b"EDF+C")
    assert np.all(np.abs(back - data) <= step[:, None] * 0.51 + 1e-9)
    assert b"+1\x14stim/1\x14" in ann and b"+3\x14stim/2\x14" in ann


def test_brainvision_round_trip(tmp_path, synth):
    data, truth = synth
    vhdr = write_brainvision(tmp_path / "x.vhdr", data, truth)
    back = np.frombuffer(vhdr.with_suffix(".eeg").read_bytes(), dtype="<f4").reshape(-1, 8).T
    assert np.allclose(back, data, atol=1e-3)
    text = vhdr.read_text(encoding="utf-8")
    assert "SamplingInterval=3906.25" in text and "Ch5=C3,,1,µV" in text
    mk = vhdr.with_suffix(".vmrk").read_text(encoding="utf-8")
    assert "Mk2=Stimulus,S  1,257,1,0" in mk


def test_xdf_structure(tmp_path, synth):
    data, truth = synth
    raw = write_xdf(tmp_path / "x.xdf", data, truth).read_bytes()
    assert raw[:4] == b"XDF:"
    pos, tags, n_eeg = 4, [], 0
    while pos < len(raw):
        nb = raw[pos]
        length = int.from_bytes(raw[pos + 1 : pos + 1 + nb], "little")
        tag = int.from_bytes(raw[pos + 1 + nb : pos + 3 + nb], "little")
        content = raw[pos + 3 + nb : pos + 1 + nb + length]
        tags.append(tag)
        if tag == 3 and int.from_bytes(content[:4], "little") == 1:
            k = content[4]
            n_eeg += int.from_bytes(content[5 : 5 + k], "little")
        pos += 1 + nb + length
    assert pos == len(raw)
    assert tags[0] == 1 and tags[1:3] == [2, 2] and tags[-2:] == [6, 6]
    assert n_eeg == data.shape[1]


def test_truth_json(tmp_path, synth):
    _, truth = synth
    p = write_truth(tmp_path / "t.json", truth)
    assert json.loads(p.read_text(encoding="utf-8")) == json.loads(json.dumps(truth))
