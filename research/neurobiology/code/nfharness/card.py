"""Evaluation card: JSON (canonical, hashable minus 'runtime') + Markdown rendering + one card figure per subject.

RESEARCH USE ONLY. NOT A MEDICAL DEVICE.
"""
import os

import numpy as np

from .provenance import card_hash, dumps

RUO = ("RESEARCH USE ONLY. NOT A MEDICAL DEVICE. No clinical claims. Software intended for diagnosis, monitoring or "
       "treatment decisions may be a medical device under EU MDR 2017/745 (e.g. Rule 11) or FDA SaMD rules. Any clinical "
       "use requires regulatory clearance and clinical validation (IRB/ethics approval).")
FIG_LABEL = "RESEARCH USE ONLY - NOT A MEDICAL DEVICE"
C_SERIES = "#2a78d6"   # score trace (categorical slot 1)
C_ALARM = "#eb6834"    # hypothesis (slot 2)
C_REF = "#1baf7a"      # reference seizures (slot 3)
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"


def write_card(card, json_path, md_path):
    card = dict(card)
    card["card_sha256_excl_runtime"] = None
    h = card_hash({k: v for k, v in card.items() if k != "card_sha256_excl_runtime"})
    card["card_sha256_excl_runtime"] = h
    with open(json_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(dumps(card))
    with open(md_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(render_md(card))
    return h


def _f(x, nd=3):
    if isinstance(x, (int, np.integer)):
        return str(int(x))
    if isinstance(x, float):
        return "NaN" if x != x else ("%." + str(nd) + "f") % x
    return str(x)


def render_md(c):
    L = ["# Evaluation card: %s" % c["run_id"], "", "**%s**" % RUO, "",
         "**Verdict: %s**" % c["verdict"], ""]
    if c.get("verdict_note"):
        L += [c["verdict_note"], ""]
    L += ["## Intended use / task", c["task"], "", "## Data", ""]
    for k, v in c["data"].items():
        L.append("- %s: %s" % (k, v))
    L += ["", "## Split", "", "- scheme: %s" % c["split"]["scheme"], "- buffer B = %s s" % c["split"]["buffer_s"],
          "- split hash: `%s` (prereg literal matched: %s)" % (c["split"]["hash"], c["split"]["hash_matches_prereg"]),
          "- %s" % c["split"]["note"], "", "| subject | train files | test files |", "|---|---|---|"]
    for s, v in c["split"]["folds"].items():
        L.append("| %s | %s | %s |" % (s, ", ".join(v["train"]), ", ".join(v["test"])))
    L += ["", "## Model", ""]
    for k, v in c["model"].items():
        L.append("- %s: %s" % (k, v))
    L += ["", "## Metrics (per subject, summed over test files)", "",
          "| subject | verdict | TP/N_ref | sens (CP 95%) | FP | FA/24h (Garwood 95%) | precision | F1 | median latency s | "
          "sample F1 | AUROC (file-bootstrap 95%) | AUPRC (prevalence) | tau* | flags |", "|" + "---|" * 14]
    for s, m in c["metrics"].items():
        L.append("| %s | %s | %d/%d | %s [%s, %s] | %d | %s [%s, %s] | %s | %s | %s | %s | %s [%s, %s] | %s (%s) | %s | %s |" % (
            s, m["verdict"], m["tp"], m["n_ref"], _f(m["sensitivity"], 2), _f(m["sens_ci_clopper_pearson"][0]),
            _f(m["sens_ci_clopper_pearson"][1]), m["fp"], _f(m["fa_per_24h"], 1), _f(m["fa_ci_garwood_per_24h"][0], 1),
            _f(m["fa_ci_garwood_per_24h"][1], 1), _f(m["precision"], 2), _f(m["f1"], 2), _f(m["latency_median"], 1),
            _f(m["sample_f1"], 2), _f(m["window_auroc"]), _f(m["auroc_ci_block_bootstrap_files"][0]),
            _f(m["auroc_ci_block_bootstrap_files"][1]), _f(m["window_auprc"]), _f(m["prevalence"], 4), _f(m["tau"], 2),
            "; ".join(m["flags"])))
    if c.get("cross_subject"):
        L += ["", "Cross-subject means (DESCRIPTIVE, 3 clusters; CI not valid inference): %s" % c["cross_subject"]]
    L += ["", "## Controls", ""]
    for k, v in c["controls"].items():
        L.append("- **%s**: %s" % (k, v if isinstance(v, str) else dumps(v).replace("\n", " ")))
    L += ["", "## Leakage checklist (Kapoor et al.; evidence = harness guard / test)", ""]
    for k, v in c["leakage_checklist"].items():
        L.append("- %s: %s" % (k, v))
    L += ["", "## Provenance", "", "```", dumps(c["provenance"]), "```", "", "## Runtime (excluded from the card hash)", "",
          "```", dumps(c.get("runtime", {})), "```", "", "card SHA-256 (excluding runtime): `%s`" % c["card_sha256_excl_runtime"], ""]
    return "\n".join(L)


def subject_figure(subject, metrics, p_by_file, hyp_by_file, ref_by_file, tau, out_base, verdict_line):
    """One clean evaluation-card figure per subject: per test file, raw window score, tau*, alarms, reference seizures,
    plus a metrics panel. Saved as PNG + SVG."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    files = list(p_by_file)
    n = len(files)
    fig = plt.figure(figsize=(11, 1.25 * n + 2.6))
    gs = fig.add_gridspec(n + 1, 1, height_ratios=[1.6] + [1] * n, hspace=0.55)
    ax0 = fig.add_subplot(gs[0])
    ax0.axis("off")
    m = metrics
    txt = ("%s  |  verdict: %s\n"
           "event sensitivity %d/%d = %.2f (Clopper-Pearson 95%% %.2f-%.2f)   FP %d in %.2f h = %.1f/24 h (Garwood 95%% %.1f-%.1f)\n"
           "window AUROC %.3f (file-bootstrap 95%% %.3f-%.3f)   AUPRC %.3f (chance %.4f)   tau* = %.2f   median latency %s s\n"
           "%s" % (subject, m["verdict"], m["tp"], m["n_ref"], m["sensitivity"], m["sens_ci_clopper_pearson"][0],
                   m["sens_ci_clopper_pearson"][1], m["fp"], m["hours"], m["fa_per_24h"], m["fa_ci_garwood_per_24h"][0],
                   m["fa_ci_garwood_per_24h"][1], m["window_auroc"], m["auroc_ci_block_bootstrap_files"][0],
                   m["auroc_ci_block_bootstrap_files"][1], m["window_auprc"], m["prevalence"], tau,
                   _f(m["latency_median"], 1), verdict_line))
    ax0.text(0, 1, txt, va="top", ha="left", fontsize=9, color=INK, family="DejaVu Sans")
    ax0.text(1, 1.02, FIG_LABEL, va="bottom", ha="right", fontsize=10, color="#b3261e", weight="bold")
    for k, f in enumerate(files):
        ax = fig.add_subplot(gs[k + 1])
        p = p_by_file[f]
        t = np.arange(p.size) + 1.0
        ref = ref_by_file[f]
        for a, b in _runs(ref):
            ax.axvspan(a, b, color=C_REF, alpha=0.35, lw=0)
        for a, b in _runs(hyp_by_file[f]):
            ax.axvspan(a, b, ymin=0.9, ymax=1.0, color=C_ALARM, lw=0)
        ax.plot(t, p, color=C_SERIES, lw=0.6)
        ax.axhline(tau, color=INK2, lw=0.8, ls="--")
        ax.set_ylim(0, 1.05)
        ax.set_xlim(0, ref.size)
        ax.set_ylabel(f.replace(".edf", ""), fontsize=8, color=INK2, rotation=0, ha="right", va="center")
        ax.tick_params(labelsize=7, colors=INK2)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        ax.grid(axis="y", color=GRID, lw=0.5)
        if k == n - 1:
            ax.set_xlabel("time in file (s)", fontsize=8, color=INK2)
    handles = [plt.Line2D([], [], color=C_SERIES, lw=1.5, label="window score p_i"),
               plt.Line2D([], [], color=INK2, lw=1, ls="--", label="tau*"),
               plt.Rectangle((0, 0), 1, 1, color=C_REF, alpha=0.35, label="reference seizure"),
               plt.Rectangle((0, 0), 1, 1, color=C_ALARM, label="alarm (4-of-5 hypothesis)")]
    fig.legend(handles=handles, loc="lower center", ncol=4, fontsize=8, frameon=False)
    for ext in ("png", "svg"):
        fig.savefig(out_base + "." + ext, dpi=130, bbox_inches="tight", metadata=None if ext == "png" else {"Date": None})
    plt.close(fig)


def _runs(mask):
    m = np.concatenate([[0], np.asarray(mask, dtype=np.int8), [0]])
    d = np.diff(m)
    return list(zip(np.flatnonzero(d == 1), np.flatnonzero(d == -1)))


def ensure_dir(p):
    os.makedirs(p, exist_ok=True)
    return p
