from __future__ import annotations

import json
import re
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[4]
OUTPUT_DIR = Path(r"C:\Users\Philipp Thunshirn\Desktop\PhD\Papers\Konferenzen\SEST26")
META_RUN_DIR = PROJECT_ROOT / "Optimization" / "run" / "scheduler" / "meta_20260314_185648"
SH_RUN_DIR = PROJECT_ROOT / "Optimization" / "run" / "scheduler" / "meta_20260314_203939"
ARM_PATTERN = re.compile(r"bess(?P<bess>[01])_v2h(?P<v2h>[01])_h2(?P<h2>[01])_tf(?P<tf>[01])")
AUTARKY_BAND_COLORS = {
    "0.50-0.60": "#94a3b8",
    "0.60-0.70": "#f59e0b",
    "0.70+": "#16a34a",
}
BASE_GREY = "#c7c7c7"
ACCENT = "#0f766e"


def setup_style(font_size: float = 11.5, axes_labelsize: float = 12.5, axes_titlesize: float = 12.5) -> None:
    plt.rcParams.update(
        {
            "font.size": font_size,
            "axes.labelsize": axes_labelsize,
            "axes.titlesize": axes_titlesize,
            "font.family": "DejaVu Sans",
        }
    )


def load_meta_ranking(meta_run_dir: Path = META_RUN_DIR) -> list[dict]:
    summary_path = meta_run_dir / "summary.json"
    with summary_path.open("r", encoding="utf-8") as f:
        summary = json.load(f)
    return summary["arm_ranking"]


def load_fronts(meta_run_dir: Path = META_RUN_DIR) -> pd.DataFrame:
    df = pd.read_csv(meta_run_dir / "pareto_designs_final_excel.csv")
    df = df[df["feasible"] == True].copy()  # noqa: E712
    df["autarky"] = pd.to_numeric(df["autarky"], errors="coerce")

    kept = []
    for arm, g in df.groupby("arm"):
        pts = g[["f0", "f1"]].to_numpy()
        keep = np.ones(len(g), dtype=bool)
        for i in range(len(g)):
            for j in range(len(g)):
                if i == j:
                    continue
                if (pts[j, 0] <= pts[i, 0] and pts[j, 1] <= pts[i, 1]) and (
                    pts[j, 0] < pts[i, 0] or pts[j, 1] < pts[i, 1]
                ):
                    keep[i] = False
                    break
        kept.append(g.loc[keep])
    return pd.concat(kept, ignore_index=True)


def autarky_band(value: float) -> str:
    if pd.isna(value):
        return "0.50-0.60"
    if value < 0.60:
        return "0.50-0.60"
    if value < 0.70:
        return "0.60-0.70"
    return "0.70+"


def draw_autarky_fronts(ax: plt.Axes, fronts: pd.DataFrame, ranking: list[dict], climate_scale: float = 1_000.0) -> None:
    for row in ranking:
        arm = row["arm"]
        g = fronts[fronts["arm"] == arm].sort_values("f0").copy()
        if len(g) == 0:
            continue
        x = (g["f0"] / 1e6).to_numpy()
        y = (g["f1"] / climate_scale).to_numpy()
        a = g["autarky"].to_numpy()
        ax.plot(x, y, color=BASE_GREY, lw=0.8, alpha=0.5, zorder=1)
        if len(g) >= 2:
            pts = np.array([x, y]).T.reshape(-1, 1, 2)
            segs = np.concatenate([pts[:-1], pts[1:]], axis=1)
            colors = [
                AUTARKY_BAND_COLORS[autarky_band((a[i] + a[i + 1]) / 2.0)]
                for i in range(len(a) - 1)
            ]
            lc = LineCollection(segs, colors=colors, linewidths=3.6, alpha=0.97, zorder=2, capstyle="round")
            ax.add_collection(lc)
        marker_edges = [AUTARKY_BAND_COLORS[autarky_band(val)] for val in a]
        ax.scatter(x, y, s=16, color="white", edgecolors=marker_edges, linewidths=0.95, zorder=3)


def draw_pareto_labels(ax: plt.Axes, fronts: pd.DataFrame, ranking: list[dict], climate_scale: float = 1_000.0) -> None:
    x_all = fronts["f0"].to_numpy() / 1e6
    y_all = fronts["f1"].to_numpy() / climate_scale
    xmin, xmax = float(np.min(x_all)), float(np.max(x_all))
    ymin, ymax = float(np.min(y_all)), float(np.max(y_all))

    label_items = []
    for row in ranking:
        arm = row["arm"]
        g = fronts[fronts["arm"] == arm].sort_values("f0")
        if len(g) == 0:
            continue
        idx = min(len(g) - 1, max(0, int(round(0.68 * (len(g) - 1)))))
        r = g.iloc[idx]
        label_items.append({"rank": row["rank"], "x": float(r["f0"] / 1e6), "y": float(r["f1"] / climate_scale)})

    label_items.sort(key=lambda d: d["y"])
    min_gap = 0.040 * (ymax - ymin)
    last_y = -1e9
    for item in label_items:
        yy = item["y"] if item["y"] - last_y >= min_gap else last_y + min_gap
        item["yy"] = yy
        last_y = yy

    x_offset = 0.055 * (min(30.0, xmax) - xmin)
    for item in label_items:
        x1, y1 = item["x"], item["y"]
        x2, y2 = item["x"] + x_offset, item["yy"]
        ax.plot([x1, x2], [y1, y2], color="#9ca3af", lw=0.75, zorder=3)
        txt = ax.text(
            x2 + 0.006 * (min(30.0, xmax) - xmin),
            y2,
            f"#{item['rank']}",
            fontsize=8.6,
            color="#111827",
            va="center",
            ha="left",
            zorder=5,
            bbox=dict(boxstyle="round,pad=0.16", facecolor="white", edgecolor="#4b5563", linewidth=0.75, alpha=0.96),
        )
        txt.set_path_effects([pe.withStroke(linewidth=1.0, foreground="white")])


def draw_status(ax: plt.Axes, x: float, y: float, enabled: bool, size: float = 0.022) -> None:
    face = "#16a34a" if enabled else "#dc2626"
    ax.add_patch(Rectangle((x - size / 2, y - size / 2), size, size, facecolor=face, edgecolor=face, linewidth=0.8, zorder=2))
    if enabled:
        ax.plot(
            [x - size * 0.22, x - size * 0.04, x + size * 0.24],
            [y - size * 0.02, y - size * 0.20, y + size * 0.22],
            color="white",
            lw=1.5,
            solid_capstyle="round",
            zorder=3,
        )
    else:
        ax.plot(
            [x - size * 0.22, x + size * 0.22],
            [y - size * 0.22, y + size * 0.22],
            color="white",
            lw=1.5,
            solid_capstyle="round",
            zorder=3,
        )
        ax.plot(
            [x - size * 0.22, x + size * 0.22],
            [y + size * 0.22, y - size * 0.22],
            color="white",
            lw=1.5,
            solid_capstyle="round",
            zorder=3,
        )


def feature_flags(arm: str) -> dict[str, bool]:
    m = ARM_PATTERN.match(arm)
    if not m:
        raise ValueError(f"Could not parse arm name: {arm}")
    return {
        "bess": m["bess"] == "1",
        "v2h": m["v2h"] == "1",
        "h2": m["h2"] == "1",
        "tf": m["tf"] == "1",
    }
