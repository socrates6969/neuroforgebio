"""``estimate(pf_map, params) -> EstimateResult``: distinct-channel counts, clustering, attrition.

Research use only. Not a medical device. The result holds channel counts and statistics only; it
never contains stimulation parameters of any kind.

Method: a faithful port of the independently reviewed research analysis P6
(``research/somatosensory/code/p6_empirical_channels.py``; review ``REVIEW_cycle4.md``). A "channel"
is a hand territory with at least ``m`` PF electrodes whose dominant PF lies in it.
"""

from __future__ import annotations

import math
import os
import platform
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, TypedDict

import numpy as np

from . import __version__
from .attrition import p_k_ge_curve
from .labels import (
    DIGITS,
    RULES,
    Rule,
    class_vector,
    counts_of,
    k_digit,
    k_terr,
    neff,
    neff_bias_corrected,
    neff_soft,
    territory,
)
from .nulls import NullResults, run_nulls
from .pfmap import PFMap
from .reference import REFERENCE_UNAVAILABLE, ReferenceData, load_reference
from .relabel import RelabelLevel, run_relabelling

OUTPUT_SCHEMA_ID = "nf.channel-estimate/v1"
PACKAGE_NAME = "nf-channel-estimator"
NOTICE = (
    "Research use only. Not a medical device. Computational analysis of projected-field maps; "
    "not a stimulation protocol. Clinical use requires an IRB/FDA-approved study."
)
LIMITATIONS: tuple[str, ...] = (
    "Outputs are channel counts and statistics only; nothing here is a stimulation setting.",
    "No per-implant minimum channel count is verified: in the reviewed research (P6, 3 published "
    "participants) no level held in every implant after attrition.",
    "A distinct dominant territory is not proof that two channels feel distinct; perceptual "
    "independence is not tested.",
    "Attrition assumes independent electrode loss; spatially clustered loss gives lower "
    "probabilities.",
    "The clustering nulls and relabelling use reference tables digitised from one publication "
    "(Greenspon 2025, 3 participants, grade B source).",
    "Model-based channel counts (research P5/P5b) failed their validation gates and are not used.",
)

DEFAULT_SEED = 20260926
DEFAULT_SURVIVAL = 0.62
DEFAULT_SENSITIVITY: tuple[float, ...] = (0.47, 0.54, 0.62, 0.64, 0.75, 1.0)
DEFAULT_RELABEL_FRACTIONS: tuple[float, ...] = (0.05, 0.10, 0.20)
# Research P6 stream layout: SeedSequence(seed).spawn(10), streams named in this order.
STREAM_NAMES: tuple[str, ...] = (
    "mc",
    "rel",
    "boot",
    "nullA",
    "nullB",
    "shuf",
    "clust",
    "joint",
    "jhu",
    "test",
)
TERRITORY_CLASSES: dict[Rule, tuple[str, ...]] = {
    "R1": (*DIGITS, "PALM", "DORSUM_HAND", "WRIST"),
    "R2": (*DIGITS, "PALM", "DORSUM_HAND", "WRIST"),
    "ray": (*DIGITS, "PALM", "DORSUM_HAND", "WRIST"),
    "R3": (*DIGITS, "HAND", "MIXED"),
}


class ParameterError(ValueError):
    """An estimation parameter is out of range."""


@dataclass(frozen=True)
class EstimateParams:
    """All parameters of one estimate. Every value is written into the result's provenance.

    - ``m``: electrodes per channel (redundancy); research primary value 2.
    - ``survival``: independent per-electrode survival fraction p for the attrition curve; 0.62 is
      the published long-term functional fraction cited by the research (prereg P6 4c).
    - ``rule``: labelling rule used for the attrition curve (R1 palm-first is the research primary).
      Counts are always reported for all four rules; clustering and relabelling are R1 by design.
    - ``seed`` / ``null_draws``: random nulls (research: 20260926 / 10,000).
    - ``sensitivity``: extra survival fractions for the attrition sensitivity rows.
    - ``relabel``: also run the digitisation relabelling check (off by default).
    """

    m: int = 2
    survival: float = DEFAULT_SURVIVAL
    rule: Rule = "R1"
    seed: int = DEFAULT_SEED
    null_draws: int = 10000
    sensitivity: tuple[float, ...] = DEFAULT_SENSITIVITY
    relabel: bool = False
    relabel_fractions: tuple[float, ...] = DEFAULT_RELABEL_FRACTIONS
    relabel_draws: int = 5000

    def validate(self) -> None:
        """Raise :class:`ParameterError` on an out-of-range value."""
        if isinstance(self.m, bool) or not isinstance(self.m, int) or not 1 <= self.m <= 64:
            raise ParameterError("m must be an integer in 1..64")
        for name, p in [("survival", self.survival)] + [
            ("sensitivity", s) for s in self.sensitivity
        ]:
            if not isinstance(p, (int, float)) or not (0.0 <= float(p) <= 1.0):
                raise ParameterError(f"{name} must be a number in [0, 1], got {p!r}")
        if self.rule not in RULES:
            raise ParameterError(f"rule must be one of {list(RULES)}, got {self.rule!r}")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int) or self.seed < 0:
            raise ParameterError("seed must be a non-negative integer")
        if not isinstance(self.null_draws, int) or not 0 <= self.null_draws <= 1_000_000:
            raise ParameterError("null_draws must be an integer in 0..1,000,000 (0 = skip)")
        if not isinstance(self.relabel_draws, int) or not 1 <= self.relabel_draws <= 1_000_000:
            raise ParameterError("relabel_draws must be an integer in 1..1,000,000")
        for x in self.relabel_fractions:
            if not isinstance(x, (int, float)) or not 0.0 <= float(x) <= 1.0:
                raise ParameterError(f"relabel fraction must be in [0, 1], got {x!r}")

    def as_dict(self) -> dict[str, Any]:
        """Parameters as written into the provenance."""
        return {
            "m": self.m,
            "survival": float(self.survival),
            "rule": self.rule,
            "seed": self.seed,
            "null_draws": self.null_draws,
            "sensitivity": [float(s) for s in self.sensitivity],
            "relabel": self.relabel,
            "relabel_fractions": [float(x) for x in self.relabel_fractions],
            "relabel_draws": self.relabel_draws,
        }


class RuleCounts(TypedDict):
    """Territory class sizes and channel counts under one labelling rule."""

    territory_counts: dict[str, int]
    k_digit: int
    k_territory: int


class KProbability(TypedDict):
    """P(K >= k)."""

    k: int
    probability: float


class AttritionLevel(TypedDict):
    """Attrition curve at one level (digit: D1..D5; territory: D1..D5 + pooled hand)."""

    class_sizes: dict[str, int]
    p_k_at_least: list[KProbability]


class SensitivityRow(TypedDict):
    """Attrition curves at one extra survival fraction."""

    survival: float
    digit_level: list[KProbability]
    territory_level: list[KProbability]


@dataclass(frozen=True)
class EstimateResult:
    """Typed result. :meth:`to_dict` gives the JSON document (schema ``nf.channel-estimate/v1``)."""

    map_id: str | None
    input_summary: dict[str, Any]
    channel_counts: dict[str, Any]
    diversity: dict[str, Any]
    clustering: dict[str, Any]
    attrition: dict[str, Any]
    relabelling: dict[str, Any]
    provenance: dict[str, Any]
    limitations: tuple[str, ...] = field(default=LIMITATIONS)

    def k_digit(self, rule: Rule = "R1") -> int:
        """K_digit(m) under ``rule``."""
        return int(self.channel_counts["by_rule"][rule]["k_digit"])

    def k_territory(self, rule: Rule = "R1") -> int:
        """K_territory(m) under ``rule``."""
        return int(self.channel_counts["by_rule"][rule]["k_territory"])

    def p_k_at_least(self, k: int, level: Literal["digit", "territory"] = "digit") -> float:
        """P(K >= k) at the requested survival fraction (1.0 for k <= 0)."""
        if k <= 0:
            return 1.0
        rows = self.attrition[f"{level}_level"]["p_k_at_least"]
        return float(rows[k - 1]["probability"]) if k <= len(rows) else 0.0

    def to_dict(self) -> dict[str, Any]:
        """The JSON document, in a fixed key order."""
        return {
            "schema": OUTPUT_SCHEMA_ID,
            "notice": NOTICE,
            "map_id": self.map_id,
            "input_summary": self.input_summary,
            "channel_counts": self.channel_counts,
            "diversity": self.diversity,
            "clustering": self.clustering,
            "attrition": self.attrition,
            "relabelling": self.relabelling,
            "limitations": list(self.limitations),
            "provenance": self.provenance,
        }


def streams(seed: int) -> dict[str, np.random.Generator]:
    """Generators in the research P6 layout (one SeedSequence spawned into 10 streams)."""
    ss = np.random.SeedSequence(seed)
    return {
        name: np.random.default_rng(s) for name, s in zip(STREAM_NAMES, ss.spawn(10), strict=True)
    }


def _nan_to_none(x: float | None) -> float | None:
    return None if x is None or math.isnan(x) else float(x)


def code_commit() -> str | None:
    """Git commit of this checkout (``NF_CODE_COMMIT`` overrides); ``None`` if unknown."""
    env = os.environ.get("NF_CODE_COMMIT")
    if env:
        return env
    try:
        r = subprocess.run(
            ["git", "-C", str(Path(__file__).resolve().parent), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    out = r.stdout.strip()
    return out if r.returncode == 0 and len(out) == 40 else None


def _curve(nvec: Sequence[int], p: float, m: int) -> list[KProbability]:
    return [{"k": i + 1, "probability": v} for i, v in enumerate(p_k_ge_curve(nvec, p, m))]


def _rule_counts(pf: Sequence[Any], rule: Rule, m: int) -> RuleCounts:
    c = counts_of(territory(e.palm_segment, e.dorsum_segment, rule) for e in pf)
    return {
        "territory_counts": {t: int(c.get(t, 0)) for t in TERRITORY_CLASSES[rule]},
        "k_digit": k_digit(c, m),
        "k_territory": k_terr(c, m),
    }


def estimate(
    pf_map: PFMap,
    params: EstimateParams | None = None,
    reference: ReferenceData | None = None,
    *,
    reference_dir: str | None = None,
) -> EstimateResult:
    """Distinct-channel counts, clustering vs random nulls and attrition for one PF map.

    ``reference`` (or ``reference_dir``, else ``NF_CHANNELS_REFERENCE_DIR``) supplies the
    third-party reference tables used by the clustering nulls and relabelling. They are not
    shipped in the package; without them those two sections report ``skipped``.
    """
    params = params or EstimateParams()
    params.validate()
    ref = reference or load_reference(reference_dir)
    m = params.m
    pf = pf_map.pf_electrodes
    n = len(pf)
    arrays = sorted({e.array_id for e in pf_map.electrodes})
    ref_keys = set(ref.keys) if ref is not None else set()
    outside = (
        sorted({e.dominant_segment for e in pf if e.dominant_segment not in ref_keys})
        if ref is not None
        else []
    )

    input_summary = {
        "electrodes_listed": len(pf_map.electrodes),
        "pf_electrodes": n,
        "arrays": [
            {
                "array_id": a,
                "electrodes_listed": sum(e.array_id == a for e in pf_map.electrodes),
                "pf_electrodes": sum(e.array_id == a for e in pf),
            }
            for a in arrays
        ],
        "positions_present": all(e.x_mm is not None for e in pf_map.electrodes)
        and bool(pf_map.electrodes),
        "dominant_segments_outside_reference": outside,
    }

    # ---- channel counts (all rules) and per array (R1)
    by_rule = {rule: _rule_counts(pf, rule, m) for rule in RULES}
    per_array = []
    for a in arrays:
        ea = [e for e in pf if e.array_id == a]
        rc = _rule_counts(ea, "R1", m)
        per_array.append(
            {"array_id": a, "k_digit": rc["k_digit"], "k_territory": rc["k_territory"]}
        )
    best_single = max((x["k_digit"] for x in per_array), default=0)
    channel_counts = {
        "m": m,
        "definition": "a channel is a hand territory with at least m PF electrodes whose dominant "
        "projected field lies in it; k_digit counts D1..D5, k_territory adds the pooled "
        "palm/dorsum-of-hand territory",
        "by_rule": by_rule,
        "per_array_R1": per_array,
        "second_array_gain_R1": by_rule["R1"]["k_digit"] - best_single if len(arrays) > 1 else None,
    }

    # ---- diversity (R1)
    c1 = counts_of(territory(e.palm_segment, e.dorsum_segment, "R1") for e in pf)
    segc = counts_of(e.dominant_segment for e in pf)
    soft_sets = [
        {s for s in ("palm:" + e.palm_segment if e.palm_segment else "",
                     "dors:" + e.dorsum_segment if e.dorsum_segment else "") if s}
        for e in pf
    ]  # fmt: skip
    n_eff_digit = neff(c1)
    n_eff_seg = neff(segc)
    diversity = {
        "rule": "R1",
        "n_eff_digit": _nan_to_none(n_eff_digit),
        "n_eff_digit_bias_corrected": neff_bias_corrected(c1) if n else None,
        "n_eff_segment": _nan_to_none(n_eff_seg),
        "n_eff_segment_bias_corrected": neff_bias_corrected(segc) if n else None,
        "n_segment_classes": len(segc),
        "n_eff_soft": _nan_to_none(neff_soft(soft_sets)),
    }

    g = streams(params.seed)
    rng_doc = {
        "construction": "numpy.random.SeedSequence(seed).spawn(10) -> default_rng (PCG64); "
        "streams in research P6 order " + ",".join(STREAM_NAMES),
        "streams_used": {"null_a": "nullA", "null_b": "nullB", "relabelling": "rel"},
    }

    # ---- clustering vs spatially random nulls (R1 labels)
    clustering: dict[str, Any]
    if n == 0 or params.null_draws == 0 or ref is None:
        clustering = {
            "status": "skipped",
            "reason": "no PF electrodes"
            if n == 0
            else ("null_draws = 0" if params.null_draws == 0 else REFERENCE_UNAVAILABLE),
        }
    else:
        nr: NullResults = run_nulls(
            g["nullA"],
            g["nullB"],
            ref,
            n,
            params.null_draws,
            n_eff_seg,
            n_eff_digit,
            by_rule["R1"]["k_digit"],
            m,
        )
        clustering = {
            "status": "computed",
            "statistic": "N_eff (inverse Simpson index of R1 labels) observed vs spatially "
            "random nulls; p_value = P(null <= observed); ratio = observed / null median",
            "seed": params.seed,
            "draws": params.null_draws,
            "rng": rng_doc,
            "null_a_area": nr["null_a_area"],
            "null_b_pooled": nr["null_b_pooled"],
            "null_a_area_no_wrist": nr["null_a_area_no_wrist"],
            "reference": {
                "source": ref.source,
                "segments_sha256": ref.segments_sha256,
                "pooled_sha256": ref.pooled_sha256,
                "pooled_electrodes": len(ref.pooled_keys),
            },
        }

    # ---- attrition (exact DP) under the selected rule
    cr = counts_of(territory(e.palm_segment, e.dorsum_segment, params.rule) for e in pf)
    dv, tv = class_vector(cr, False), class_vector(cr, True)
    attrition = {
        "rule": params.rule,
        "m": m,
        "survival": float(params.survival),
        "model": "each PF electrode survives independently with probability survival; exact "
        "Poisson-binomial DP over disjoint territory classes",
        "digit_level": {
            "class_sizes": dict(zip(DIGITS, dv, strict=True)),
            "p_k_at_least": _curve(dv, params.survival, m),
        },
        "territory_level": {
            "class_sizes": dict(zip((*DIGITS, "HAND_POOLED"), tv, strict=True)),
            "p_k_at_least": _curve(tv, params.survival, m),
        },
        "sensitivity": [
            {
                "survival": float(p),
                "digit_level": _curve(dv, p, m),
                "territory_level": _curve(tv, p, m),
            }
            for p in params.sensitivity
        ],
    }

    # ---- relabelling (optional, R1)
    relabelling: dict[str, Any]
    if not params.relabel:
        relabelling = {"status": "not_requested"}
    elif n == 0:
        relabelling = {"status": "skipped", "reason": "no PF electrodes"}
    elif ref is None:
        relabelling = {"status": "skipped", "reason": REFERENCE_UNAVAILABLE}
    elif outside:
        relabelling = {
            "status": "skipped",
            "reason": "dominant segment tags outside the reference table: " + ", ".join(outside),
        }
    else:
        levels: list[RelabelLevel] = run_relabelling(
            g["rel"],
            ref,
            [e.dominant_segment for e in pf],
            params.relabel_fractions,
            params.relabel_draws,
            m,
            by_rule["R1"]["k_digit"],
        )
        relabelling = {
            "status": "computed",
            "rule": "R1",
            "method": "per draw, round(fraction * N) PF electrodes get their dominant segment "
            "replaced by one of the 3 nearest same-surface reference segments (uniform)",
            "seed": params.seed,
            "rng": rng_doc,
            "levels": levels,
        }

    provenance = {
        "package": PACKAGE_NAME,
        "version": __version__,
        "code_commit": code_commit(),
        "input_sha256": pf_map.sha256(),
        "input_hash_scheme": "SHA-256 of the NF-CJSON v1 canonical JSON of the normalised "
        "nf.pf-map/v1 document (docs/spec/hashing.md)",
        "parameters": params.as_dict(),
        "reference_data": {
            "segments_sha256": ref.segments_sha256,
            "pooled_sha256": ref.pooled_sha256,
        }
        if ref is not None
        else {"status": "not_installed"},
        "method": "port of research/somatosensory/code/p6_empirical_channels.py "
        "(independent code review: research/somatosensory/code/REVIEW_cycle4.md)",
        "runtime": {"python": platform.python_version(), "numpy": np.__version__},
    }

    return EstimateResult(
        map_id=pf_map.map_id,
        input_summary=input_summary,
        channel_counts=channel_counts,
        diversity=diversity,
        clustering=clustering,
        attrition=attrition,
        relabelling=relabelling,
        provenance=provenance,
    )
