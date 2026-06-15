"""Build an alternative four-panel taxonomy synthesis figure.

This draft keeps only one bubble panel. The other panels use simpler encodings
so the figure does not repeat the same visual grammar:

A. heatmap: model class x optimizer role
B. bubble map: surrogate target x optimizer role
C. heatmap: reported DoE depth x validation depth
D. stacked bars: application targets by model class

The script only uses categories already present in the paper's curated library
and evidence-card pipeline. Panels A/B/D use the curated library bucket layer;
Panel C uses PDF-backed evidence cards, where DoE and validation are explicit.
"""

from __future__ import annotations

import csv
import re
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.patches import Patch


ROOT = Path(__file__).resolve().parents[2]
FIG = ROOT / "figures"
CSV = FIG / "csv"
MANIFEST = ROOT / "paper_library" / "review_paper_library_manifest.csv"
BUCKETS = ROOT / "paper_library" / "review_paper_library_buckets.csv"
CARDS = ROOT / "paper_library" / "sec8_evidence_cards.csv"
OUT_COUNTS = CSV / "fig_four_panel_taxonomy_synthesis_v2_draft_counts.csv"


ROLE_ORDER = ["Input / weak", "P1/P3 replace", "P2 accelerate", "P4 decompose", "P5 uncertainty"]
ROLE_BUCKETS = {
    "P1/P3 replace": {"B07_constraint_aware", "B09_decision_focused_l2o", "B17_ed_uc", "B18_opf"},
    "P2 accelerate": {
        "B10_doe_active_learning",
        "B11_multi_fidelity",
        "B12_bayes_accel",
        "B23_moo_design",
        "B25_moo_algorithms_nsga",
        "B26_moo_metaheuristics",
    },
    "P4 decompose": {"B14_decomposition"},
    "P5 uncertainty": {"B15_uncertainty", "B24_stochastic_robust"},
}

ROLE_COLORS = {
    "Input / weak": "#8C8C8C",
    "P1/P3 replace": "#1B9E77",
    "P2 accelerate": "#66A61E",
    "P4 decompose": "#7570B3",
    "P5 uncertainty": "#1F78B4",
}

FAMILY_ORDER = ["PCE/RSM", "GP/Kriging", "RBF/Kernel", "Tree", "NN", "Constraint NN", "Hybrid/PINN", "L2O"]
FAMILY_BUCKETS = {
    "PCE/RSM": {"B03_pce_response_surface"},
    "GP/Kriging": {"B02_gp_kriging"},
    "RBF/Kernel": {"B04_rbf_kernel"},
    "Tree": {"B05_tree_ensembles"},
    "NN": {"B06_neural_surrogates"},
    "Constraint NN": {"B07_constraint_aware"},
    "Hybrid/PINN": {"B08_hybrid_pinn"},
    "L2O": {"B09_decision_focused_l2o"},
}
FAMILY_COLORS = {
    "PCE/RSM": "#4E79A7",
    "GP/Kriging": "#F28E2B",
    "RBF/Kernel": "#59A14F",
    "Tree": "#EDC948",
    "NN": "#E15759",
    "Constraint NN": "#76B7B2",
    "Hybrid/PINN": "#B07AA1",
    "L2O": "#9C755F",
}

TARGET_ORDER = ["exogenous input", "objective / response", "constraints / states", "uncertainty / risk", "solution / policy"]
APPLICATION_BUCKETS = {
    "ED / UC": {"B17_ed_uc"},
    "OPF": {"B18_opf"},
    "Expansion": {"B19_capacity_expansion"},
    "District heating": {"B20_district_heating"},
    "MES / sector": {"B21_mes_sector_coupling"},
    "Microgrid / hub": {"B22_microgrid_hub"},
    "MOO design": {"B23_moo_design"},
    "Stoch / robust": {"B24_stochastic_robust"},
}
APPLICATION_COLORS = {
    "ED / UC": "#B279A2",
    "OPF": "#E45756",
    "Expansion": "#9D755D",
    "District heating": "#BAB0AC",
    "MES / sector": "#4C78A8",
    "Microgrid / hub": "#F58518",
    "MOO design": "#54A24B",
    "Stoch / robust": "#72B7B2",
}

TRUST_COLORS = {
    "basic": "#999999",
    "adaptive": "#66A61E",
    "uncertainty": "#1F78B4",
    "physics": "#7570B3",
    "constraint": "#1B9E77",
    "decision": "#D95F02",
}
TRUST_LABELS = {
    "basic": "basic / point",
    "adaptive": "adaptive / BO",
    "uncertainty": "uncertainty",
    "physics": "physics-informed",
    "constraint": "constraint-aware",
    "decision": "decision-aware",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip().lower()


def bucket_index() -> dict[str, set[str]]:
    index: dict[str, set[str]] = defaultdict(set)
    if not BUCKETS.is_file():
        return index
    for row in read_csv(BUCKETS):
        key = row.get("cite_key", "").strip()
        tag = row.get("bucket_id", "").strip()
        if key and tag:
            index[key].add(tag)
    return index


def merged_buckets(row: dict[str, str], extra: dict[str, set[str]]) -> set[str]:
    tags: set[str] = set()
    for raw in (row.get("primary_bucket", ""), row.get("all_buckets", "")):
        for tag in raw.split(";"):
            tag = tag.strip()
            if tag:
                tags.add(tag)
    tags.update(extra.get(row.get("cite_key", ""), set()))
    return tags


def family_from_tags(tags: set[str]) -> str | None:
    found = [label for label in FAMILY_ORDER if tags & FAMILY_BUCKETS[label]]
    if not found:
        return None
    for specific in ("L2O", "Hybrid/PINN", "Constraint NN"):
        if specific in found:
            return specific
    return found[0]


def roles_from_tags(tags: set[str]) -> list[str]:
    found = [role for role in ROLE_ORDER[1:] if tags & ROLE_BUCKETS[role]]
    return found or ["Input / weak"]


def strongest_role(tags: set[str]) -> str:
    for role in reversed(ROLE_ORDER[1:]):
        if tags & ROLE_BUCKETS[role]:
            return role
    return "Input / weak"


def trust_from_tags(tags: set[str]) -> str:
    if tags & {"B09_decision_focused_l2o", "B16_validation"}:
        return "decision"
    if "B07_constraint_aware" in tags:
        return "constraint"
    if "B08_hybrid_pinn" in tags:
        return "physics"
    if tags & {"B15_uncertainty", "B24_stochastic_robust"}:
        return "uncertainty"
    if tags & {"B10_doe_active_learning", "B11_multi_fidelity", "B12_bayes_accel"}:
        return "adaptive"
    return "basic"


def surrogate_target(row: dict[str, str], tags: set[str]) -> str:
    title = norm(row.get("title", ""))
    if "B09_decision_focused_l2o" in tags:
        return "solution / policy"
    if tags & {"B15_uncertainty", "B24_stochastic_robust"}:
        return "uncertainty / risk"
    if tags & {"B07_constraint_aware", "B18_opf"}:
        return "constraints / states"
    if re.search(r"\b(load|forecast|wind|solar|pv|price|demand)\b", title) and not tags & {
        "B17_ed_uc",
        "B18_opf",
        "B21_mes_sector_coupling",
        "B22_microgrid_hub",
        "B23_moo_design",
    }:
        return "exogenous input"
    return "objective / response"


def doe_depth(doe: str) -> tuple[int, str]:
    text = norm(doe)
    if not text or text == "--":
        return 0, "unclear"
    if any(term in text for term in ("historical", "synthetic")):
        return 1, "batch / historical"
    if any(term in text for term in ("lhs", "quasi", "factorial", "doe")):
        return 2, "static DoE"
    if any(term in text for term in ("adaptive", "active", "multi-fidelity", "transfer")):
        return 3, "sequential"
    return 1, "batch / historical"


def validation_depth(validation: str) -> tuple[int, str]:
    text = norm(validation)
    if not text or text == "--":
        return 0, "unclear"
    if any(term in text for term in ("decision-aware", "regret", "gap", "stress test")):
        return 3, "decision / robust"
    if any(term in text for term in ("feasibility", "constraint", "uncertainty", "interval calibration")):
        return 2, "operational / UQ"
    return 1, "point metrics"


def role_from_card(row: dict[str, str]) -> str:
    return {
        "P1": "P1/P3 replace",
        "P2": "P2 accelerate",
        "P4": "P4 decompose",
        "P5": "P5 uncertainty",
    }.get((row.get("pattern") or "").strip(), "Input / weak")


def annotate_heatmap(ax: plt.Axes, data: np.ndarray, threshold: float) -> None:
    for y in range(data.shape[0]):
        for x in range(data.shape[1]):
            value = int(data[y, x])
            if value:
                color = "white" if value >= threshold else "#222222"
                ax.text(x, y, str(value), ha="center", va="center", color=color, fontsize=8, fontweight="bold")


def main() -> None:
    extra = bucket_index()
    manifest_rows = [r for r in read_csv(MANIFEST) if r.get("primary_bucket") != "B01_cornerstone_reviews"]
    library_records: list[tuple[dict[str, str], set[str], str]] = []
    for row in manifest_rows:
        tags = merged_buckets(row, extra)
        family = family_from_tags(tags)
        if family:
            library_records.append((row, tags, family))

    model_role_counts: Counter[tuple[str, str]] = Counter()
    target_role_counts: Counter[tuple[str, str]] = Counter()
    target_role_family: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    target_role_trust: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    application_counts: Counter[tuple[str, str]] = Counter()

    for row, tags, family in library_records:
        for role in roles_from_tags(tags):
            model_role_counts[(family, role)] += 1
        role = strongest_role(tags)
        target = surrogate_target(row, tags)
        trust = trust_from_tags(tags)
        target_role_counts[(target, role)] += 1
        target_role_family[(target, role)][family] += 1
        target_role_trust[(target, role)][trust] += 1
        for app, app_tags in APPLICATION_BUCKETS.items():
            if tags & app_tags:
                application_counts[(family, app)] += 1

    cards = read_csv(CARDS)
    rigor_counts: Counter[tuple[int, int]] = Counter()
    rigor_role: dict[tuple[int, int], Counter[str]] = defaultdict(Counter)
    for row in cards:
        x, _ = doe_depth(row.get("doe", ""))
        y, _ = validation_depth(row.get("validation", ""))
        rigor_counts[(x, y)] += 1
        rigor_role[(x, y)][role_from_card(row)] += 1

    with OUT_COUNTS.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["panel", "x", "y", "n", "dominant"])
        for (family, role), count in sorted(model_role_counts.items()):
            writer.writerow(["A", role, family, count, ""])
        for (target, role), count in sorted(target_role_counts.items()):
            writer.writerow(["B", role, target, count, target_role_family[(target, role)].most_common(1)[0][0]])
        for (x, y), count in sorted(rigor_counts.items()):
            dominant = rigor_role[(x, y)].most_common(1)[0][0]
            writer.writerow(["C", x, y, count, dominant])
        for (family, app), count in sorted(application_counts.items()):
            writer.writerow(["D", app, family, count, ""])

    fig, axes = plt.subplots(2, 2, figsize=(15.2, 11.0))
    ax_a, ax_b, ax_c, ax_d = axes.ravel()

    # A. Model-class by optimizer-role heatmap.
    matrix_a = np.array(
        [[model_role_counts.get((family, role), 0) for role in ROLE_ORDER] for family in FAMILY_ORDER],
        dtype=float,
    )
    im_a = ax_a.imshow(matrix_a, cmap="YlGnBu", aspect="auto")
    annotate_heatmap(ax_a, matrix_a, threshold=max(matrix_a.max() * 0.55, 1))
    ax_a.set_xticks(range(len(ROLE_ORDER)), ROLE_ORDER, rotation=25, ha="right")
    ax_a.set_yticks(range(len(FAMILY_ORDER)), FAMILY_ORDER)
    ax_a.set_title("A. Model class x optimizer role", loc="left", fontweight="bold")
    ax_a.set_xlabel("Optimizer integration role")
    ax_a.set_ylabel("Surrogate model class")
    fig.colorbar(im_a, ax=ax_a, fraction=0.035, pad=0.02, label="paper count")

    # B. Single bubble panel: target criticality x role.
    x_role = {role: i for i, role in enumerate(ROLE_ORDER)}
    y_target = {target: i for i, target in enumerate(TARGET_ORDER)}
    max_b = max(target_role_counts.values()) if target_role_counts else 1
    for (target, role), count in target_role_counts.items():
        family = target_role_family[(target, role)].most_common(1)[0][0]
        trust = target_role_trust[(target, role)].most_common(1)[0][0]
        ax_b.scatter(
            x_role[role],
            y_target[target],
            s=55 + 760 * count / max_b,
            facecolor=FAMILY_COLORS[family],
            edgecolor=TRUST_COLORS[trust],
            linewidth=2.2,
            alpha=0.84,
        )
        if count >= 4:
            ax_b.text(x_role[role], y_target[target], str(count), ha="center", va="center", color="white", fontsize=8, fontweight="bold")
    ax_b.set_xticks(range(len(ROLE_ORDER)), ROLE_ORDER, rotation=25, ha="right")
    ax_b.set_yticks(range(len(TARGET_ORDER)), TARGET_ORDER)
    ax_b.grid(True, color="#DDDDDD")
    ax_b.set_axisbelow(True)
    ax_b.set_title("B. Surrogate target x optimizer role", loc="left", fontweight="bold")
    ax_b.set_xlabel("Optimizer integration role")
    ax_b.set_ylabel("Surrogate target")

    # C. DoE by validation heatmap, with dominant role encoded as a small marker.
    matrix_c = np.zeros((4, 4), dtype=float)
    for (x, y), count in rigor_counts.items():
        matrix_c[y, x] = count
    im_c = ax_c.imshow(matrix_c, cmap="PuBuGn", aspect="auto", origin="lower")
    annotate_heatmap(ax_c, matrix_c, threshold=max(matrix_c.max() * 0.55, 1))
    for (x, y), roles in rigor_role.items():
        if matrix_c[y, x]:
            ax_c.scatter(x + 0.32, y + 0.32, s=48, c=ROLE_COLORS[roles.most_common(1)[0][0]], edgecolor="white", linewidth=0.8)
    ax_c.set_xticks(range(4), ["unclear", "batch /\nhistorical", "static\nDoE", "sequential /\nmulti-source"])
    ax_c.set_yticks(range(4), ["unclear", "point\nmetrics", "operational /\nUQ", "decision /\nrobust"])
    ax_c.set_title("C. Reported DoE x validation depth", loc="left", fontweight="bold")
    ax_c.set_xlabel("Training-design depth")
    ax_c.set_ylabel("Validation depth")
    fig.colorbar(im_c, ax=ax_c, fraction=0.035, pad=0.02, label="paper count")

    # D. Stacked application targets by model class.
    top_apps = [app for app, _ in Counter(app for _, app in application_counts).most_common(7)]
    left = [0] * len(FAMILY_ORDER)
    ypos = range(len(FAMILY_ORDER))
    for app in top_apps:
        vals = [application_counts.get((family, app), 0) for family in FAMILY_ORDER]
        ax_d.barh(ypos, vals, left=left, color=APPLICATION_COLORS[app], label=app, height=0.68)
        left = [a + b for a, b in zip(left, vals)]
    ax_d.set_yticks(list(ypos), FAMILY_ORDER)
    ax_d.grid(axis="x", color="#DDDDDD")
    ax_d.set_axisbelow(True)
    ax_d.set_title("D. Main application targets", loc="left", fontweight="bold")
    ax_d.set_xlabel("Tagged paper count")
    ax_d.legend(title="Application target", loc="lower right", frameon=False, fontsize=8, title_fontsize=9)

    family_handles = [
        Line2D([0], [0], marker="o", color="none", markerfacecolor=FAMILY_COLORS[f], markersize=7, label=f)
        for f in FAMILY_ORDER
    ]
    trust_handles = [
        Line2D([0], [0], marker="o", color=TRUST_COLORS[t], markerfacecolor="white", markeredgewidth=2.2, markersize=7, label=TRUST_LABELS[t])
        for t in ("basic", "adaptive", "uncertainty", "physics", "constraint", "decision")
    ]
    role_handles = [Patch(facecolor=ROLE_COLORS[r], label=r) for r in ROLE_ORDER]

    fig.legend(handles=family_handles, title="Panel B fill: dominant model class", loc="lower left", bbox_to_anchor=(0.02, 0.017), ncol=4, frameon=False, fontsize=8, title_fontsize=9)
    fig.legend(handles=trust_handles, title="Panel B ring: dominant trust signal", loc="lower center", bbox_to_anchor=(0.52, 0.017), ncol=3, frameon=False, fontsize=8, title_fontsize=9)
    fig.legend(handles=role_handles, title="Panel C marker: dominant integration role", loc="lower right", bbox_to_anchor=(0.99, 0.017), ncol=2, frameon=False, fontsize=8, title_fontsize=9)

    fig.suptitle("Draft quantitative synthesis of surrogate taxonomy, evidence depth and applications", fontsize=15, fontweight="bold", y=0.984)
    fig.text(
        0.01,
        0.004,
        (
            f"Sources: Panels A/B/D use curated library bucket tags, non-review model-class records n={len(library_records)}; "
            f"Panel C uses PDF-backed evidence cards n={len(cards)}. Draft classification for visual review."
        ),
        fontsize=8,
        color="#555555",
    )
    fig.tight_layout(rect=(0, 0.11, 1, 0.955), h_pad=2.1, w_pad=2.0)
    for ext in ("png",):
        fig.savefig(FIG / f"fig_four_panel_taxonomy_synthesis_v2_draft.{ext}", dpi=300, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()
