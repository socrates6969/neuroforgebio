"""N1b figures (PNG + SVG). RESEARCH USE ONLY. NOT A MEDICAL DEVICE.
Palette = the harness card palette (validated: #2a78d6, #eb6834, #1baf7a; green below 3:1 contrast, so every panel has
a legend and the numbers are in the result JSON / RESULTS_N1b.md)."""
import numpy as np

C1, C2, C3 = "#2a78d6", "#eb6834", "#1baf7a"
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"
LABEL = "RESEARCH USE ONLY - NOT A MEDICAL DEVICE"


def _plt():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.size": 8, "axes.edgecolor": INK2, "axes.labelcolor": INK2, "xtick.color": INK2,
                         "ytick.color": INK2, "svg.hashsalt": "n1b"})
    return plt


def _clean(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.grid(axis="y", color=GRID, lw=0.5)
    ax.set_axisbelow(True)


def _ecdf(ax, p, color, label):
    p = np.sort(np.asarray(p, dtype=float))
    ax.step(np.r_[0, p], np.r_[0, np.arange(1, p.size + 1) / p.size], where="post", color=color, lw=1.5, label=label)


def _strip(ax, reps, key, subjects, dx, color, label):
    for i, s in enumerate(subjects):
        v = [key(r) for r in reps if r["subject"] == s]
        x = i + dx + np.linspace(-0.08, 0.08, len(v)) if v else []
        ax.scatter(x, v, s=16, color=color, edgecolor="white", lw=0.5, zorder=3, label=label if i == 0 else None)


def _save(fig, base):
    for ext in ("png", "svg"):
        fig.savefig(base + "." + ext, dpi=130, bbox_inches="tight", metadata={"Date": None} if ext == "svg" else None)


def real_figure(card, f1_mc, f1_plc, base):
    plt = _plt()
    subs = sorted({r["subject"] for r in card["NC-P"]["replicates"]})
    ncp, pla, plb = card["NC-P"]["replicates"], card["PL-A"]["replicates"], card["PL-B"]["replicates"]
    agg = card["NC-P"]["aggregate"]
    fig, axs = plt.subplots(1, 4, figsize=(16, 4.2))
    ax = axs[0]
    _strip(ax, ncp, lambda r: r["T_A"], subs, -0.15, C1, "NC-P (honest)")
    _strip(ax, pla, lambda r: r["T_A"], subs, 0.15, C2, "PL-A (planted label leak)")
    ax.axhline(0.5, color=INK2, lw=0.8, ls="--")
    ax.set_xticks(range(len(subs)), subs)
    ax.set_ylabel("test window AUROC vs phantom labels")
    ax.set_title("(a) window arm T_A; dashed = 0.5", fontsize=9)
    ax.legend(frameon=False, fontsize=7, loc="upper left")
    ax = axs[1]
    ax.plot([0, 1], [0, 1], color=INK2, lw=0.8, ls="--", label="U(0,1)")
    _ecdf(ax, [r["p_A_up"] for r in ncp if not r["window_flag_sd"]], C1, "NC-P p_up(T_A)")
    _ecdf(ax, [r["E_rm"]["p_up"] for r in ncp if not r["degeneracy_rm"]["degenerate"]], C3, "NC-P p_up(T_E), non-degenerate")
    f = agg["fisher"]
    ax.set_title("(b) NC-P exact p-values; Fisher up/lo A %.3g/%.3g, E %.3g/%.3g" % (f["T_A_up"], f["T_A_lo"], f["T_E_up"], f["T_E_lo"]),
                 fontsize=8)
    ax.set_xlabel("p")
    ax.set_ylabel("ECDF")
    ax.legend(frameon=False, fontsize=7, loc="lower right")
    ax = axs[2]
    _strip(ax, ncp, lambda r: r["E_rm"]["T_E"], subs, -0.22, C1, "NC-P (t_rm)")
    _strip(ax, pla, lambda r: r["E_rm"]["T_E"], subs, 0.0, C2, "PL-A (t_rm)")
    _strip(ax, plb, lambda r: r["T_E"], subs, 0.22, C3, "PL-B (tau on test phantoms)")
    ax.set_xticks(range(len(subs)), subs)
    ax.set_ylabel("event F1 vs phantom references")
    ax.set_title("(c) event arm T_E per replicate", fontsize=9)
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
    ax.set_xlim(-0.02, max(0.7, c3["descriptive_model_pooled_f1"] + 0.05))
    ax.axvline(c3["descriptive_model_pooled_f1"], color=C3, lw=1.2)
    ax.set_xlabel("pooled random-alarm event F1 (dashed = exact q95; green = N2 model F1)")
    ax.set_ylabel("probability")
    ax.set_title("(d) C3': mu* %.4f, MC mean %.4f; above q95: MC %.3f, PL-C %.3f (bound %.4f)" % (
        c3["exact"]["mu_star"], c3["mc"]["mean_mc"], c3["mc"]["frac_above_q95"], c3["PL-C"]["frac_above_q95"],
        c3["mc"]["bound_ii"]), fontsize=7)
    ax.legend(frameon=False, fontsize=7, loc="upper right")
    for a in axs:
        _clean(a)
    rc = card["run_criteria"]
    fig.suptitle("N1b negative controls v2 (POST-HOC; CHB-MIT chb01/03/10): run criteria %s   |   %s" % (
        "all met" if card["run_criteria_all_true"] else "NOT all met: " + ", ".join(k for k, x in rc.items() if not x), LABEL),
        fontsize=9, color=INK)
    fig.tight_layout()
    _save(fig, base)
    plt.close(fig)


def synthetic_figure(out, f1_mc, base):
    plt = _plt()
    ncp, pla = out["NC-P"]["replicates"], out["PL-A"]["replicates"]
    subs = sorted({r["subject"] for r in ncp})
    fig, axs = plt.subplots(1, 2, figsize=(10, 4))
    ax = axs[0]
    ax.plot([0, 1], [0, 1], color=INK2, lw=0.8, ls="--", label="U(0,1)")
    _ecdf(ax, [r["p_A_up"] for r in ncp], C1, "NC-P p_up(T_A), n=%d" % len(ncp))
    k = out["dry_run"]["KS_T_A_p_up"]
    ax.set_title("(a) synthetic dry run: KS vs U(0,1) p = %.3f (needs >= 0.01)" % k["pvalue"], fontsize=9)
    ax.set_xlabel("p")
    ax.set_ylabel("ECDF")
    ax.legend(frameon=False, fontsize=7, loc="lower right")
    ax = axs[1]
    _strip(ax, ncp, lambda r: r["T_A"], subs, -0.15, C1, "NC-P")
    _strip(ax, pla, lambda r: r["T_A"], subs, 0.15, C2, "PL-A")
    ax.axhline(0.5, color=INK2, lw=0.8, ls="--")
    ax.set_xticks(range(len(subs)), subs)
    t = out["trips"]["PL-A"]
    ax.set_title("(b) T_A; PL-A Fisher up: T_A %.2g, T_E %.2g -> trip %s" % (t["fisher_T_A_up"], t["fisher_T_E_up"], t["trip"]),
                 fontsize=9)
    ax.set_ylabel("test window AUROC vs phantom labels")
    ax.legend(frameon=False, fontsize=7, loc="upper left")
    for a in axs:
        _clean(a)
    fig.suptitle("N1b synthetic dry run (SYNTHETIC DATA, real file/seizure layout)   |   " + LABEL, fontsize=9, color=INK)
    fig.tight_layout()
    _save(fig, base)
    plt.close(fig)
