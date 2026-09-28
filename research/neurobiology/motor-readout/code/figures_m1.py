r"""M1 figures from a results card (PNG + SVG): decoder comparison, bits/s vs R2, drift vs days.

RESEARCH USE ONLY. NOT A MEDICAL DEVICE.
Usage: figures_m1.py <card.json> <out_dir>
"""
import json
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

COL = {"ridge": "#2a78d6", "kf": "#eb6834", "gru": "#1baf7a", "R-a": "#eda100", "R-b": "#e87ba4", "B0": "#8a8984"}
NAME = {"ridge": "Ridge (Wiener)", "kf": "Kalman", "gru": "GRU", "B0": "B0 mean profile"}
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"
RUO = "RESEARCH USE ONLY - NOT A MEDICAL DEVICE"


def style(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(INK2)
    ax.tick_params(colors=INK2, labelsize=8)
    ax.grid(axis="y", color=GRID, lw=0.6)
    ax.set_axisbelow(True)


def save(fig, out, name, note):
    fig.text(0.99, 0.995, RUO, ha="right", va="top", fontsize=8, color="#b3261e", weight="bold")
    fig.text(0.01, 0.005, note, ha="left", va="bottom", fontsize=7, color=INK2)
    for ext in ("png", "svg"):
        fig.savefig(os.path.join(out, name + "." + ext), dpi=140, bbox_inches="tight",
                    metadata={"Date": None} if ext == "svg" else None)
    plt.close(fig)


def fig_decoders(c, out, note):
    d1 = c["D1"]
    decs = ["ridge", "kf", "gru"]
    fig, axs = plt.subplots(1, 2, figsize=(9.5, 3.8))
    for ax, key, lab in ((axs[0], "r2", "test R² (variance-weighted)"), (axs[1], "I_net", "I_net (bits/s, 0-10 Hz)")):
        for i, k in enumerate(decs):
            v = d1[k]["r2"] if key == "r2" else d1[k]["bits"]["I_net"]
            lo, hi = d1[k]["r2_ci99"] if key == "r2" else d1[k]["I_net_ci99"]
            ax.errorbar(i, v, yerr=[[v - lo], [hi - v]], fmt="o", ms=8, color=COL[k], ecolor=COL[k], elinewidth=2, capsize=0)
            ax.annotate("%.3f" % v if key == "r2" else "%.1f" % v, (i, v), xytext=(10, 0), textcoords="offset points",
                        va="center", fontsize=8, color=INK)
        if key == "r2":
            cond = c["D1_descriptive"]["condition_held_out_r2"]
            ax.scatter(range(3), [cond[k] for k in decs], marker="D", s=30, facecolor="white", edgecolor=INK2, zorder=3,
                       label="condition-held-out (descriptive)")
            ax.axhline(d1["B0"]["r2"], color=COL["B0"], lw=1, ls="--", label="B0 mean profile")
            ax.legend(fontsize=7, frameon=False, loc="lower left")
        ax.set_xticks(range(3), [NAME[k] for k in decs], fontsize=8)
        ax.set_xlim(-0.5, 2.8)
        ax.set_ylabel(lab, fontsize=9, color=INK2)
        style(ax)
    axs[0].set_title("D1 MC_Maze_Large: decoder accuracy (99% bootstrap CI)", fontsize=9, color=INK, loc="left")
    axs[1].set_title("D1: coherence-bound information rate (99% CI)", fontsize=9, color=INK, loc="left")
    fig.tight_layout(rect=(0, 0.03, 1, 0.95))
    save(fig, out, "M1_decoder_comparison", note)


def fig_bits_vs_r2(c, out, note):
    fig, ax = plt.subplots(figsize=(6.2, 4.4))
    d1 = c["D1"]
    for k in ("ridge", "kf", "gru"):
        ax.scatter(d1[k]["r2"], d1[k]["bits"]["I_net"], s=70, color=COL[k], edgecolor="white", lw=1.5, zorder=3,
                   label="%s, D1 (20 ms)" % NAME[k])
    offs = []
    if "D2" in c:
        for k in ("ridge", "kf", "gru"):
            xs, ys = [], []
            for d, e in c["D2"]["sessions"].items():
                for arm in ("D2within/", "D2fixed/"):
                    s = e["scores"][arm + k]
                    xs.append(s["r2"])
                    ys.append(s["I_net"])
            lo = -1.2
            off = [(xx, yy) for xx, yy in zip(xs, ys) if xx < lo]
            if off:
                ax.scatter([lo + 0.03] * len(off), [yy for _, yy in off], s=28, marker="<", color=COL[k], zorder=3)
                offs.extend("%.1f" % xx for xx, _ in off)
            ax.scatter(xs, ys, s=22, marker="s", facecolor="none", edgecolor=COL[k], lw=1.2, zorder=2,
                       label="%s, D2 sessions (32 ms)" % NAME[k])
    r = np.linspace(0.0, 0.95, 100)
    for n_f, df, lab in ((8, 1000 / 700, "flat coherence ρ²=R², D1 band"), (21, 1000 / 2048, "flat coherence ρ²=R², D2 band")):
        ax.plot(r, 2 * n_f * df * -np.log2(1 - r), color=INK2, lw=1, ls=":" if n_f == 21 else "--", label="reference: " + lab)
    ax.axhline(0, color=INK2, lw=0.6)
    ax.set_xlim(-1.2, 1.0)
    ax.set_ylim(-2, 45)
    if offs:
        ax.text(0.02, 0.02, "R² off-scale (◀): " + ", ".join(offs), transform=ax.transAxes, fontsize=6.5, color=INK2)
    ax.set_xlabel("test R² (variance-weighted)", fontsize=9, color=INK2)
    ax.set_ylabel("I_net (bits/s)", fontsize=9, color=INK2)
    ax.set_title("Information rate vs accuracy (offline, open-loop; not a BCI 'speed')", fontsize=9, color=INK, loc="left")
    ax.legend(fontsize=7, frameon=False, loc="upper left")
    style(ax)
    fig.tight_layout(rect=(0, 0.03, 1, 0.95))
    save(fig, out, "M1_bits_vs_r2", note)


def fig_drift(c, out, note):
    if "D2" not in c:
        return
    ses = c["D2"]["sessions"]
    ds = sorted(ses, key=lambda d: ses[d]["lag_days"])
    lag = np.array([ses[d]["lag_days"] for d in ds], float)
    x = np.log10(lag + 1)
    fig, axs = plt.subplots(1, 2, figsize=(10.5, 4.0))
    ax = axs[0]
    for k in ("ridge", "kf", "gru"):
        ax.plot(x, [ses[d]["scores"]["D2fixed/" + k]["r2"] for d in ds], "-o", color=COL[k], lw=2, ms=5,
                label="%s day-0 (fixed)" % NAME[k])
        ax.plot(x, [ses[d]["scores"]["D2within/" + k]["r2"] for d in ds], ":", color=COL[k], lw=1.5,
                label="%s within-day" % NAME[k])
    for arm, key in (("R-a", "D2Ra/ridge"), ("R-b", "D2Rb/ridge")):
        ax.plot(x, [ses[d]["scores"][key]["r2"] for d in ds], "-s", color=COL[arm], lw=1.5, ms=4,
                label="ridge + %s (%s)" % (arm, "re-z-score" if arm == "R-a" else "FA-Procrustes"))
    flag = [i for i, d in enumerate(ds) if ses[d]["flagged_random_targets"]]
    for i in flag:
        ax.annotate("RD", (x[i], 1.0), fontsize=7, color=INK2, ha="center")
    ax.set_ylabel("test R² on day-k test block", fontsize=9, color=INK2)
    ax.set_title("D2 LINK: accuracy vs days since day 0", fontsize=9, color=INK, loc="left")
    ax.legend(fontsize=6.5, frameon=False, loc="lower left", ncol=2, bbox_to_anchor=(0, 0.08))
    ax2 = axs[1]
    for k in ("ridge", "kf", "gru"):
        rh = [ses[d]["rho_" + k]["value"] for d in ds]
        ax2.plot(x, [np.nan if v is None else v for v in rh], "-o", color=COL[k], lw=2, ms=5, label=NAME[k])
    ci = np.array([ses[d]["rho_ridge"]["ci99"] for d in ds])
    ax2.fill_between(x, np.maximum(ci[:, 0], -4.0), ci[:, 1], color=COL["ridge"], alpha=0.15, lw=0, label="ridge 99% CI")
    ax2.axhline(0.5, color=INK2, lw=1, ls="--")
    ax2.axhline(0.8, color=INK2, lw=1, ls=":")
    ax2.text(x[-1], 0.30, "H4 PASS bar 0.5", fontsize=7, color=INK2, ha="right")
    ax2.text(x[-1], 0.9, "H4 FAIL bar 0.8", fontsize=7, color=INK2, ha="right")
    ax2.set_ylabel("retention ρ = R²_fixed / R²_within", fontsize=9, color=INK2)
    ax2.set_title("Retention of the day-0 decoder", fontsize=9, color=INK, loc="left")
    ax2.legend(fontsize=7, frameon=False, loc="lower left", bbox_to_anchor=(0, 0.08))
    for a, lo, hi in ((axs[0], -1.5, 0.75), (axs[1], -4.0, 1.4)):
        off = []
        for ln in a.get_lines():
            yd = np.asarray(ln.get_ydata(), float)
            for xi, yi in zip(ln.get_xdata(), yd):
                if np.isfinite(yi) and yi < lo:
                    a.plot([xi], [lo + 0.04 * (hi - lo)], marker="v", color=ln.get_color(), ms=6, clip_on=False)
                    off.append("%.1f" % yi)
        a.set_ylim(lo, hi)
        if off:
            a.text(0.99, 0.02, "off-scale (▼): " + ", ".join(off), transform=a.transAxes, ha="right", va="bottom",
                   fontsize=6.5, color=INK2)
    for a in axs:
        a.set_xticks(x, ["%d" % l for l in lag], fontsize=8)
        a.set_xlabel("days since day 0 (log scale)", fontsize=9, color=INK2)
        style(a)
    fig.tight_layout(rect=(0, 0.03, 1, 0.95))
    save(fig, out, "M1_drift_vs_days", note)


def main():
    card = json.load(open(sys.argv[1], encoding="utf-8"))
    out = sys.argv[2]
    os.makedirs(out, exist_ok=True)
    note = "M1 %s | card %s | seed 20261001 | GRU seeds %s | unreviewed" % (
        card.get("run_id"), card["card_sha256_excl_runtime"][:12], card["rng_streams"]["gru_seeds"])
    fig_decoders(card, out, note)
    fig_bits_vs_r2(card, out, note)
    fig_drift(card, out, note)


if __name__ == "__main__":
    main()
