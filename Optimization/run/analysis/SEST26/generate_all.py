from __future__ import annotations

from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
from matplotlib.lines import Line2D

from Optimization.run.analysis.SEST26.common import (
    ACCENT,
    ARM_PATTERN,
    AUTARKY_BAND_COLORS,
    BASE_GREY,
    META_RUN_DIR,
    OUTPUT_DIR,
    SH_RUN_DIR,
    draw_autarky_fronts,
    draw_pareto_labels,
    draw_status,
    feature_flags,
    load_fronts,
    load_meta_ranking,
    setup_style,
)


def generate_pareto_plot() -> Path:
    ranking = load_meta_ranking(META_RUN_DIR)
    fronts = load_fronts(META_RUN_DIR)
    setup_style(font_size=11.8, axes_labelsize=13.5, axes_titlesize=13.5)

    fig, ax = plt.subplots(figsize=(11.2, 8.0))
    draw_autarky_fronts(ax, fronts, ranking, climate_scale=1_000.0)
    draw_pareto_labels(ax, fronts, ranking, climate_scale=1_000.0)

    x_all = fronts["f0"].to_numpy() / 1e6
    y_all = fronts["f1"].to_numpy() / 1e3
    xmin, xmax = float(x_all.min()), float(x_all.max())
    ymin, ymax = float(y_all.min()), float(y_all.max())
    ax.set_xlim(xmin - 0.04 * (30.0 - xmin), 30.0)
    ax.set_ylim(ymin - 0.04 * (ymax - ymin), ymax + 0.06 * (ymax - ymin))
    ax.set_xlabel("Net Present Costs [million EUR]")
    ax.set_ylabel("Greenhouse gas emissions [t CO$_2$-eq]")
    ax.grid(alpha=0.22)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(axis="both", labelsize=12)
    legend_bands = [Line2D([0], [0], color=c, lw=5, label=k) for k, c in AUTARKY_BAND_COLORS.items()]
    ax.legend(handles=legend_bands, title="Autarky range", loc="upper right", frameon=True, fontsize=11.2, title_fontsize=12.0, borderpad=0.9, handlelength=2.4)

    out = OUTPUT_DIR / "sest26_pareto_all_arms_only.png"
    fig.savefig(out, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return out


def generate_arm_table() -> Path:
    ranking = [row for row in load_meta_ranking(META_RUN_DIR) if row["arm"] != "bess0_v2h0_h20_tf0"]
    fronts = load_fronts(META_RUN_DIR)
    front_arms = set(fronts["arm"].unique())
    hv_lookup = {row["arm"]: row["hv"] for row in load_meta_ranking(META_RUN_DIR)}
    setup_style(font_size=11.0, axes_labelsize=12.5, axes_titlesize=12.5)

    fig, ax = plt.subplots(figsize=(10.6, 8.2))
    ax.axis("off")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.text(0.02, 0.985, "Arm ranking and technology composition", fontsize=13, fontweight="bold", va="top")

    cols = {"rank": 0.03, "arm": 0.13, "bess": 0.56, "v2c": 0.66, "h2": 0.76, "tf": 0.86, "hv": 0.97}
    ax.text(cols["rank"], 0.94, "Rank", fontsize=9.5, fontweight="bold", va="top")
    ax.text(cols["arm"], 0.94, "Arm", fontsize=9.5, fontweight="bold", va="top")
    ax.text(cols["bess"], 0.94, "BESS", fontsize=9.3, fontweight="bold", va="top", ha="center")
    ax.text(cols["v2c"], 0.94, "V2C", fontsize=9.3, fontweight="bold", va="top", ha="center")
    ax.text(cols["h2"], 0.94, "H$_2$", fontsize=9.3, fontweight="bold", va="top", ha="center")
    ax.text(cols["tf"], 0.94, "Thermal flexibility", fontsize=9.3, fontweight="bold", va="top", ha="center")
    ax.text(cols["hv"], 0.94, "HV", fontsize=9.5, fontweight="bold", va="top", ha="right")
    ax.plot([0.02, 0.98], [0.926, 0.926], color="#d1d5db", lw=1.0)

    start_y = 0.90
    row_h = 0.055
    for i, row in enumerate(ranking):
        arm = row["arm"]
        y = start_y - i * row_h
        shade = "#f8fafc" if i % 2 == 0 else "white"
        ax.add_patch(plt.Rectangle((0.02, y - 0.032), 0.96, 0.043, facecolor=shade, edgecolor="none", zorder=0))
        flags = feature_flags(arm)
        color = "#111827" if arm in front_arms else "#9ca3af"
        ax.text(cols["rank"], y, f"#{row['rank']:>2}", fontsize=9.3, color=color, va="center", fontweight="bold")
        ax.text(cols["arm"], y, arm, fontsize=8.5, color=color, va="center", family="DejaVu Sans Mono")
        draw_status(ax, cols["bess"], y, flags["bess"])
        draw_status(ax, cols["v2c"], y, flags["v2h"])
        draw_status(ax, cols["h2"], y, flags["h2"])
        draw_status(ax, cols["tf"], y, flags["tf"])
        ax.text(cols["hv"], y, f"{hv_lookup.get(arm, 0.0):.2e}", fontsize=8.7, color=color, va="center", ha="right")

    out = OUTPUT_DIR / "sest26_arm_ranking_table.png"
    fig.savefig(out, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return out


def generate_technology_deltas() -> Path:
    df = pd.read_csv(META_RUN_DIR / "pareto_designs_final_excel.csv")
    df["export_share"] = df["G_export_share_max"] + 0.5
    df["import_share"] = 1.0 - df["autarky"]
    summary = df.groupby("arm").agg(
        npc=("f0", "min"),
        climate=("f1", "min"),
        import_share=("import_share", "median"),
        export_share=("export_share", "median"),
    ).reset_index()
    for c in ["bess", "v2h", "h2", "tf"]:
        summary[c] = summary["arm"].str.extract(ARM_PATTERN)[c].astype(int)

    tech_order = ["tf", "v2h", "bess", "h2"]
    tech_label = {
        "tf": "Thermal flexibility",
        "v2h": "Vehicle-to-community",
        "bess": "Battery energy storage system",
        "h2": "Hydrogen",
    }
    records = []
    for tech in tech_order:
        others = [c for c in ["bess", "v2h", "h2", "tf"] if c != tech]
        for _, a in summary[summary[tech] == 0].iterrows():
            mask = summary[tech] == 1
            for c in others:
                mask &= summary[c] == a[c]
            m = summary[mask]
            if len(m) == 1:
                b = m.iloc[0]
                records.append(
                    {
                        "tech": tech,
                        "npc": (b["npc"] - a["npc"]) / 1e6,
                        "climate": (b["climate"] - a["climate"]) / 1e6,
                        "import_share": (b["import_share"] - a["import_share"]) * 100.0,
                        "export_share": (b["export_share"] - a["export_share"]) * 100.0,
                    }
                )
    pairs = pd.DataFrame(records)
    setup_style(font_size=11.0, axes_labelsize=11.0, axes_titlesize=13.0)

    fig, axes = plt.subplots(2, 2, figsize=(12.6, 7.5))
    fig.subplots_adjust(hspace=0.36, wspace=0.18, left=0.08, right=0.985, top=0.96, bottom=0.08)
    axes = axes.ravel()
    metric_specs = [
        ("npc", r"$\Delta$ NPC [million EUR]"),
        ("climate", r"$\Delta$ greenhouse gas emissions [million kg CO$_2$-eq]"),
        ("import_share", r"$\Delta$ import share [percentage points]"),
        ("export_share", r"$\Delta$ export share [percentage points]"),
    ]
    color_map = {"tf": "#c2410c", "v2h": "#2563eb", "bess": "#7c3aed", "h2": "#0f766e"}
    for idx, (ax, (metric, title)) in enumerate(zip(axes, metric_specs)):
        for yi, tech in enumerate(tech_order):
            vals = pairs.loc[pairs["tech"] == tech, metric].to_numpy()
            if len(vals) == 0:
                continue
            jitter = np.linspace(-0.14, 0.14, len(vals)) if len(vals) > 1 else np.array([0.0])
            y = np.full(len(vals), yi, dtype=float) + jitter
            ax.scatter(vals, y, s=40, color=color_map[tech], alpha=0.82, edgecolors="white", linewidths=0.55, zorder=3)
            q1, med, q3 = np.percentile(vals, [25, 50, 75])
            ax.hlines(yi, q1, q3, colors="black", linewidth=3.2, zorder=4)
            ax.vlines(med, yi - 0.18, yi + 0.18, colors="black", linewidth=2.1, zorder=4)
        ax.axvline(0, color="black", linewidth=1.0)
        ax.set_title(title, pad=8)
        ax.grid(axis="x", alpha=0.25)
        ax.set_axisbelow(True)
        vals_all = pairs[metric].to_numpy()
        lim = max(abs(vals_all.min()), abs(vals_all.max())) * 1.18 if len(vals_all) else 1.0
        ax.set_xlim(-lim, lim)
        if idx % 2 == 0:
            ax.set_yticks(np.arange(len(tech_order)), [tech_label[t] for t in tech_order])
        else:
            ax.set_yticks(np.arange(len(tech_order)))
            ax.set_yticklabels([])
            ax.tick_params(axis="y", length=0)

    out = OUTPUT_DIR / "sest26_technology_deltas_points_formatted.png"
    fig.savefig(out, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return out


def generate_sh_dashboard() -> Path:
    with (SH_RUN_DIR / "run_metrics.json").open("r", encoding="utf-8") as f:
        m = json.load(f)
    em = m["evaluation_metrics"]
    full_evals = int(em["baseline_full_evaluations"])
    sh_evals = int(em["effective_evaluations"])
    requested_budget = float(em["budget_requested_total"])
    executed_budget = float(em["budget_executed_total"])
    mean_eval_s = float(em["mean_eval_walltime_s"])
    sh_time_s = float(m["total_walltime_s"])
    full_time_est_s = full_evals * mean_eval_s
    n_arms = int(em["n_arms"])

    stage_df = pd.read_csv(SH_RUN_DIR / "stage_log.csv")
    survival = stage_df.groupby("budget_n_gen")["arm"].count().reset_index().sort_values("budget_n_gen")

    setup_style(font_size=11.5, axes_labelsize=12.5, axes_titlesize=12.5)
    fig, axes = plt.subplots(2, 2, figsize=(11.2, 8.0))
    fig.subplots_adjust(wspace=0.28, hspace=0.34, left=0.08, right=0.97, top=0.95, bottom=0.10)

    labels = ["Full search", "Successive halving"]
    colors = [BASE_GREY, ACCENT]

    ax = axes[0, 0]
    vals = [full_evals / 1000.0, sh_evals / 1000.0]
    bars = ax.bar(labels, vals, color=colors, edgecolor="black", linewidth=0.8, width=0.62)
    ax.set_title("Function evaluations")
    ax.set_ylabel("Evaluations [thousand]")
    ax.grid(axis="y", alpha=0.22)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    for b, raw in zip(bars, [full_evals, sh_evals]):
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 2.8, f"{raw:,}", ha="center", va="bottom", fontsize=10.5)

    ax = axes[0, 1]
    vals_t = [full_time_est_s / 3600.0, sh_time_s / 3600.0]
    bars = ax.bar(labels, vals_t, color=colors, edgecolor="black", linewidth=0.8, width=0.62)
    ax.set_title("Wall-clock time")
    ax.set_ylabel("Runtime [h]")
    ax.grid(axis="y", alpha=0.22)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    for b, raw in zip(bars, [full_time_est_s, sh_time_s]):
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.04, f"{raw/3600.0:.2f} h", ha="center", va="bottom", fontsize=10.5)

    ax = axes[1, 0]
    vals_b = [requested_budget, executed_budget]
    bars = ax.bar(["Requested budget", "Executed budget"], vals_b, color=[BASE_GREY, ACCENT], edgecolor="black", linewidth=0.8, width=0.62)
    ax.set_title("Budget allocation")
    ax.set_ylabel("Budget [generation-equivalents]")
    ax.grid(axis="y", alpha=0.22)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    for b, raw in zip(bars, vals_b):
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 18, f"{int(raw)}", ha="center", va="bottom", fontsize=10.5)

    ax = axes[1, 1]
    xs = survival["budget_n_gen"].astype(int).tolist()
    ys = survival["arm"].astype(int).tolist()
    ax.plot(xs, [n_arms] * len(xs), color=BASE_GREY, linestyle="--", linewidth=2.0, label="Full search")
    ax.plot(xs, ys, color=ACCENT, marker="o", linewidth=2.2, markersize=7, label="Successive halving")
    ax.set_title("Arms surviving by budget stage")
    ax.set_xlabel("Budget $n_{gen}$")
    ax.set_ylabel("Number of active arms")
    ax.set_xticks(xs)
    ax.grid(alpha=0.22)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    for x, y in zip(xs, ys):
        ax.text(x, y + 0.35, f"{y}", ha="center", va="bottom", fontsize=10.5)
    ax.legend(frameon=True, fontsize=9.8, loc="upper right", bbox_to_anchor=(0.98, 0.86))

    out = OUTPUT_DIR / "sest26_sh_efficiency_dashboard.png"
    fig.savefig(out, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return out


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    outputs = [
        generate_pareto_plot(),
        generate_arm_table(),
        generate_technology_deltas(),
        generate_sh_dashboard(),
    ]
    for path in outputs:
        print(path)


if __name__ == "__main__":
    main()
