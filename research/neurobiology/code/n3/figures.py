"""N3 figures (PNG + SVG). RESEARCH USE ONLY. NOT A MEDICAL DEVICE.

Palette = the harness card palette (#2a78d6, #eb6834, #1baf7a; the green is below 3:1 contrast on white, so every panel
has a legend and every number is also in the result JSON / RESULTS_N3.md). SVGs are written with a fixed hash salt and no
date, so re-running gives the same file.
"""
import numpy as np

C1, C2, C3 = "#2a78d6", "#eb6834", "#1baf7a"
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"
LABEL = "RESEARCH USE ONLY - NOT A MEDICAL DEVICE"


def _plt():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.size": 8, "axes.edgecolor": INK2, "axes.labelcolor": INK2, "xtick.color": INK2,
                         "ytick.color": INK2, "svg.hashsalt": "n3"})
    return plt


def _clean(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.grid(axis="y", color=GRID, lw=0.5)
    ax.set_axisbelow(True)


def _ecdf(ax, p, color, label, ls="-"):
    p = np.sort(np.asarray([x for x in p if x == x], dtype=float))
    if p.size == 0:
        return
    ax.step(np.r_[0, p], np.r_[0, np.arange(1, p.size + 1) / p.size], where="post", color=color, lw=1.5, ls=ls,
            label=label)


def _strip(ax, reps, key, subjects, dx, color, label, marker="o"):
    for i, s in enumerate(subjects):
        v = [key(r) for r in reps if r["subject"] == s]
        x = i + dx + np.linspace(-0.07, 0.07, len(v)) if v else []
        ax.scatter(x, v, s=16, color=color, edgecolor="white", lw=0.5, zorder=3, marker=marker,
                   label=label if i == 0 else None)


def _save(fig, base):
    for ext in ("png", "svg"):
        fig.savefig(base + "." + ext, dpi=130, bbox_inches="tight", metadata={"Date": None} if ext == "svg" else None)


def _g(x):
    return "NaN" if x is None or x != x else "%.3g" % x


def synthetic_figure(out, base):
    plt = _plt()
    blk = out["controls"]
    ncp, pla = blk["NC-P"]["replicates"], blk["PL-A"]["replicates"]
    subs = sorted({r["subject"] for r in ncp})
    d = out["dry_run"]
    fig, axs = plt.subplots(1, 3, figsize=(14, 4.2))
    ax = axs[0]
    ax.plot([0, 1], [0, 1], color=INK2, lw=0.8, ls="--", label="U(0,1)")
    _ecdf(ax, [r["p_A_up"] for r in ncp], C1, "p_up(T_A), n=%d" % len(ncp))
    _ecdf(ax, [r["p_A_lo"] for r in ncp], C1, "p_lo(T_A)", ls=":")
    keep = [r for r in ncp if not r["degeneracy_rm"]["degenerate"]]
    _ecdf(ax, [r["E_rm"]["p_up"] for r in keep], C3, "p_up(SigmaF1, 1 rep), n=%d" % len(keep))
    _ecdf(ax, [r["E_rm"]["p_lo"] for r in keep], C3, "p_lo(SigmaF1, 1 rep)", ls=":")
    ax.set_title("(a) NC-P exact p-values; one-sided KS p: A %s/%s, E %s/%s (need >= 0.01)" % (
        _g(d["a_T_A_up"]["ks_one_sided_super_uniform_p"]), _g(d["a_T_A_lo"]["ks_one_sided_super_uniform_p"]),
        _g(d["a_pooled_SigmaF1_up_per_replicate"]["ks_one_sided_super_uniform_p"]),
        _g(d["a_pooled_SigmaF1_lo_per_replicate"]["ks_one_sided_super_uniform_p"])), fontsize=7)
    ax.set_xlabel("p")
    ax.set_ylabel("ECDF")
    ax.legend(frameon=False, fontsize=7, loc="lower right")
    ax = axs[1]
    _strip(ax, ncp, lambda r: r["T_A"], subs, -0.15, C1, "NC-P")
    _strip(ax, pla, lambda r: r["T_A"], subs, 0.15, C2, "PL-A (25%)")
    ax.axhline(0.5, color=INK2, lw=0.8, ls="--")
    ax.set_xticks(range(len(subs)), subs)
    ax.set_ylabel("test window AUROC vs phantom labels")
    ax.set_title("(b) window arm T_A; PL-A Fisher up %s -> trip %s" % (_g(blk["PL-A"]["fisher_T_A_up"]),
                                                                       blk["PL-A"]["trips_T_A"]), fontsize=8)
    ax.legend(frameon=False, fontsize=7, loc="upper left")
    ax = axs[2]
    gp = d.get("descriptive_grouped_pooled_SigmaF1") or []
    x = np.arange(len(gp))
    ax.scatter(x - 0.08, [g["p_up"] for g in gp], color=C1, s=20, label="pooled SigmaF1 p_up")
    ax.scatter(x + 0.08, [g["p_lo"] for g in gp], color=C2, s=20, marker="s", label="pooled SigmaF1 p_lo")
    ax.axhline(0.0025, color=INK, lw=0.8, ls="--")
    ax.set_yscale("log")
    ax.set_ylim(1e-3, 1.2)
    ax.set_xticks(x, ["g%d" % g["group"] for g in gp])
    ax.set_ylabel("p (log); dashed = 0.0025 gate")
    ax.set_title("(c) pooled SigmaF1 over groups of 10 reps x 2 subjects (descriptive)", fontsize=8)
    ax.legend(frameon=False, fontsize=7, loc="lower right")
    for a in axs:
        _clean(a)
    fig.suptitle("N3 synthetic dry run (SYNTHETIC DATA, chb23/chb24 file and seizure layout): PASS = %s   |   %s"
                 % (d["PASS"], LABEL), fontsize=9, color=INK)
    fig.tight_layout()
    _save(fig, base)
    plt.close(fig)


def real_figure(card, f1_mc, f1_plc, base):
    plt = _plt()
    blk = card["controls"]
    ncp, pla = blk["NC-P"]["replicates"], blk["PL-A"]["replicates"]
    pla10, plb = blk["PL-A10_descriptive"]["replicates"], blk["PL-B_descriptive"]["replicates"]
    subs = sorted({r["subject"] for r in ncp})
    fig, axs = plt.subplots(1, 4, figsize=(17, 4.4))
    ax = axs[0]
    _strip(ax, ncp, lambda r: r["T_A"], subs, -0.22, C1, "NC-P (honest)")
    _strip(ax, pla10, lambda r: r["T_A"], subs, 0.0, C3, "PL-A10 (10%, descriptive)", marker="D")
    _strip(ax, pla, lambda r: r["T_A"], subs, 0.22, C2, "PL-A (25%, formal)", marker="s")
    ax.axhline(0.5, color=INK2, lw=0.8, ls="--")
    ax.set_xticks(range(len(subs)), subs)
    ax.set_ylabel("test window AUROC vs phantom labels")
    ax.set_title("(a) window arm T_A (formal leak gate); Fisher up: PL-A %s, PL-A10 %s" % (
        _g(blk["PL-A"]["fisher_T_A_up"]), _g(blk["PL-A10_descriptive"]["fisher_T_A_up"])), fontsize=7)
    ax.legend(frameon=False, fontsize=7, loc="upper left")
    ax = axs[1]
    ax.plot([0, 1], [0, 1], color=INK2, lw=0.8, ls="--", label="U(0,1)")
    _ecdf(ax, [r["p_A_up"] for r in ncp if not r["window_flag_sd"]], C1, "NC-P p_up(T_A)")
    _ecdf(ax, [r["p_A_lo"] for r in ncp if not r["window_flag_sd"]], C1, "NC-P p_lo(T_A)", ls=":")
    _ecdf(ax, [r["E_rm"]["p_up"] for r in ncp if not r["degeneracy_rm"]["degenerate"]], C3,
          "NC-P p_up(T_E), retained")
    ev = blk["NC-P"]["event_arm"]["pooled_SigmaF1"]
    ax.set_title("(b) NC-P: V1-A Fisher up/lo %s/%s; V1-E pooled SigmaF1 up/lo %s/%s" % (
        _g(blk["NC-P"]["T_A_fisher_up"]), _g(blk["NC-P"]["T_A_fisher_lo"]), _g(ev["p_up"]), _g(ev["p_lo"])), fontsize=7)
    ax.set_xlabel("p")
    ax.set_ylabel("ECDF")
    ax.legend(frameon=False, fontsize=7, loc="lower right")
    ax = axs[2]
    _strip(ax, ncp, lambda r: r["E_rm"]["T_E"], subs, -0.22, C1, "NC-P (t_rm)")
    _strip(ax, pla, lambda r: r["E_rm"]["T_E"], subs, 0.0, C2, "PL-A (t_rm)", marker="s")
    _strip(ax, plb, lambda r: r["T_E"], subs, 0.22, C3, "PL-B (tau on test phantoms)", marker="D")
    ax.set_xticks(range(len(subs)), subs)
    ax.set_ylabel("event F1 vs phantom references")
    ax.set_title("(c) event arm per replicate (validity only; descriptive for power)", fontsize=8)
    ax.legend(frameon=False, fontsize=7, loc="upper left")
    ax = axs[3]
    c3 = card["C3prime"]
    v = np.array([a for a, _ in c3["exact_pmf"]])
    m = np.array([b for _, b in c3["exact_pmf"]])
    ax.vlines(v, 0, m, color=INK2, lw=2, label="exact pmf")
    for arr, col, lab in ((f1_mc, C1, "harness MC (C3')"), (f1_plc, C2, "PL-C (forced alarm)")):
        u, c = np.unique(arr, return_counts=True)
        ax.scatter(u, c / arr.size, s=14, color=col, zorder=3, label=lab)
    ax.axvline(c3["exact"]["q95"], color=INK, lw=0.8, ls="--")
    ax.axvline(c3["descriptive_model_pooled_f1"], color=C3, lw=1.2, label="N2 model pooled F1")
    ax.set_xlim(-0.02, max(0.7, c3["descriptive_model_pooled_f1"] + 0.05))
    ax.set_xlabel("pooled random-alarm event F1 (dashed = exact q95)")
    ax.set_ylabel("probability")
    ax.set_title("(d) C3': mu* %.4f, MC mean %.4f; above q95: MC %.3f, PL-C %.3f (bound %.4f)" % (
        c3["exact"]["mu_star"], c3["mc"]["mean_mc"], c3["mc"]["frac_above_q95"], c3["PL-C"]["frac_above_q95"],
        c3["mc"]["bound_ii"]), fontsize=7)
    ax.legend(frameon=False, fontsize=7, loc="upper right")
    for a in axs:
        _clean(a)
    g = card["gate_items_real_run"]
    bad = [k for k, x in g.items() if not x]
    fig.suptitle("N3 harness validation, fresh subjects chb23/chb24 (prereg blind): real-run gate items %s   |   %s" % (
        "all met" if not bad else "NOT met: " + ", ".join(bad), LABEL), fontsize=9, color=INK)
    fig.tight_layout()
    _save(fig, base)
    plt.close(fig)
