"""Build world-map figures from OpenAlex country counts.

Input:

    openalex_country_counts.csv

Outputs:

    fig_04_country_map_full_count.png
    fig_04_country_map_fractional_count.png
    fig_04_country_map_first_author_count.png

The script downloads Natural Earth 50m country geometries once and caches
the zip under ``figures/_natural_earth/``. The map uses ISO alpha-2 codes
from OpenAlex and Natural Earth.
"""

from __future__ import annotations

import urllib.request
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.colors import LogNorm


ROOT = Path(__file__).resolve().parents[2]
FIG = ROOT / "figures"
CSV = FIG / "csv"
COUNTS = CSV / "openalex_country_counts.csv"
NE_DIR = FIG / "_natural_earth"
NE_ZIP = NE_DIR / "ne_50m_admin_0_countries.zip"
NE_URL = "https://naturalearth.s3.amazonaws.com/50m_cultural/ne_50m_admin_0_countries.zip"

METRIC_LABELS = {
    "papers_full_count": "Publications (full count)",
    "papers_fractional_count": "Publications (fractional count)",
    "first_author_papers": "Publications (first-author count)",
}


def ensure_natural_earth() -> Path:
    """Download Natural Earth country geometry if not cached yet."""

    NE_DIR.mkdir(parents=True, exist_ok=True)
    if not NE_ZIP.exists():
        print(f"Downloading Natural Earth countries to {NE_ZIP}")
        urllib.request.urlretrieve(NE_URL, NE_ZIP)
    return NE_ZIP


def load_world() -> gpd.GeoDataFrame:
    """Load and normalize Natural Earth country geometries."""

    path = ensure_natural_earth()
    world = gpd.read_file(f"zip://{path}")
    world = world[world["ADMIN"] != "Antarctica"].copy()

    # Natural Earth has ISO_A2 and sometimes ISO_A2_EH for disputed areas.
    world["country_code"] = world["ISO_A2"].where(world["ISO_A2"] != "-99", world["ISO_A2_EH"])
    world["country_code"] = world["country_code"].str.upper()

    # Equal Earth is a visually pleasant compromise for global choropleths
    # and avoids the rectangular look of raw lon/lat maps.
    try:
        world = world.to_crs("EPSG:8857")
    except Exception:
        # Keep lon/lat if the local PROJ database does not know EPSG:8857.
        pass
    return world


def plot_map(world: gpd.GeoDataFrame, metric: str, title: str, filename_stem: str) -> None:
    """Plot one choropleth map for *metric*."""

    data = pd.read_csv(COUNTS)
    data["country_code"] = data["country_code"].str.upper()
    merged = world.merge(data, on="country_code", how="left")

    positive = merged[metric].dropna()
    positive = positive[positive > 0]
    vmax = float(positive.max()) if not positive.empty else 1.0
    vmin = 1.0 if metric != "papers_fractional_count" else max(0.5, float(positive.min()) if not positive.empty else 0.5)

    fig, ax = plt.subplots(figsize=(13.6, 7.0), facecolor="white")
    ax.set_axis_off()
    ax.set_title(title, fontsize=15, fontweight="bold", pad=16)

    ax.set_facecolor("#F7FAFC")
    world.plot(ax=ax, color="#EDF2F7", edgecolor="white", linewidth=0.20)
    merged.plot(
        ax=ax,
        column=metric,
        cmap="YlOrRd",
        linewidth=0.18,
        edgecolor="white",
        legend=True,
        norm=LogNorm(vmin=vmin, vmax=max(vmax, vmin + 0.1)),
        missing_kwds={"color": "#E2E8F0", "edgecolor": "white"},
        legend_kwds={"label": METRIC_LABELS[metric], "shrink": 0.58},
    )

    # Add compact top-10 callout so the map is interpretable without Excel.
    top = data.sort_values(metric, ascending=False).head(10)
    lines = [f"{r.country_name}: {getattr(r, metric):.0f}" for r in top.itertuples()]
    ax.text(
        0.02,
        0.04,
        "Top 10\n" + "\n".join(lines),
        transform=ax.transAxes,
        ha="left",
        va="bottom",
        fontsize=8.2,
        bbox={"boxstyle": "round,pad=0.35", "facecolor": "white", "edgecolor": "#CBD5E0", "alpha": 0.92},
    )

    for ext in ("png",):
        out = FIG / f"{filename_stem}.{ext}"
        fig.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)


def main() -> int:
    world = load_world()
    plot_map(
        world,
        "papers_full_count",
        "Country distribution of the merged review bibliography (full counting)",
        "fig_04_country_map_full_count",
    )
    plot_map(
        world,
        "papers_fractional_count",
        "Country distribution of the merged review bibliography (fractional counting)",
        "fig_04_country_map_fractional_count",
    )
    plot_map(
        world,
        "first_author_papers",
        "Country distribution of the merged review bibliography (first-author counting)",
        "fig_04_country_map_first_author_count",
    )
    print("Wrote country maps:")
    print("  fig_04_country_map_full_count.png")
    print("  fig_04_country_map_fractional_count.png")
    print("  fig_04_country_map_first_author_count.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
