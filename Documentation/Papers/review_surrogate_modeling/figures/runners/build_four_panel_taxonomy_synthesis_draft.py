"""Build a four-panel draft synthesis figure for the surrogate taxonomy.

The figure combines non-overlapping quantitative views:

A. model class x optimizer integration role
B. surrogate target criticality x optimizer integration role
C. reported DoE depth x reported validation depth
D. main application targets by dominant model class

Panels A, B and D use the broader curated library manifest/bucket layer.
Panel C uses the PDF-backed evidence-card layer, because DoE and validation
are explicitly coded there. All mappings are conservative draft encodings and
should be audited before the figure is cited as final manuscript evidence.
"""

from __future__ import annotations

import csv
import re
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D


ROOT = Path(__file__).resolve().parents[2]
FIG = ROOT / "figures"
CSV = FIG / "csv"
MANIFEST = ROOT / "paper_library" / "review_paper_library_manifest.csv"
BUCKETS = ROOT / "paper_library" / "review_paper_library_buckets.csv"
CARDS = ROOT / "paper_library" / "sec8_evidence_cards.csv"
OUT_COUNTS = CSV / "fig_four_panel_taxonomy_synthesis_draft_counts.csv"


ROLE_ORDER = [
    "Input / weak",
    "P1/P3 replace",
    "P2 accelerate",
    "P4 decompose",
    "P5 uncertainty",
]

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
TARGET_BUCKETS = {
    "ED / UC": {"B17_ed_uc"},
    "OPF": {"B18_opf"},
    "Expansion": {"B19_capacity_expansion"},
    "District heating": {"B20_district_heating"},
    "MES / sector": {"B21_mes_sector_coupling"},
    "Microgrid / hub": {"B22_microgrid_hub"},
    "MOO design": {"B23_moo_design"},
    "Stoch / robust": {"B24_stochastic_robust"},
}
TARGET_COLORS = {
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


def normalize(text: str) -> str:
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
    title = normalize(row.get("title", ""))
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
    text = normalize(doe)
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
    text = normalize(validation)
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


def main() -> None:
    extra = bucket_index()
    manifest_rows = [r for r in read_csv(MANIFEST) if r.get("primary_bucket") != "B01_cornerstone_reviews"]
    library_records: list[tuple[dict[str, str], set[str], str]] = []
    for row in manifest_rows:
        tags = merged_buckets(row, extra)
        family = family_from_tags(tags)
        if family:
            library_records.append((row, tags, family))

    panel_a: Counter[tuple[str, str, str]] = Counter()
    panel_b_counts: Counter[tuple[str, str]] = Counter()
    panel_b_family: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    panel_b_trust: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    panel_d: Counter[tuple[str, str]] = Counter()

    for row, tags, family in library_records:
        trust = trust_from_tags(tags)
        for role in roles_from_tags(tags):
            panel_a[(family, role, trust)] += 1
        role = strongest_role(tags)
        target = surrogate_target(row, tags)
        panel_b_counts[(role, target)] += 1
        panel_b_family[(role, target)][family] += 1
        panel_b_trust[(role, target)][trust] += 1
        for app, app_tags in TARGET_BUCKETS.items():
            if tags & app_tags:
                panel_d[(family, app)] += 1

    cards = read_csv(CARDS)
    panel_c_counts: Counter[tuple[int, int]] = Counter()
    panel_c_role: dict[tuple[int, int], Counter[str]] = defaultdict(Counter)
    panel_c_family: dict[tuple[int, int], Counter[str]] = defaultdict(Counter)
    for row in cards:
        x, _ = doe_depth(row.get("doe", ""))
        y, _ = validation_depth(row.get("validation", ""))
        panel_c_counts[(x, y)] += 1
        panel_c_role[(x, y)][role_from_card(row)] += 1
        panel_c_family[(x, y)][row.get("family", "--") or "--"] += 1

    with OUT_COUNTS.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["panel", "x", "y", "class_or_signal", "n"])
        for (family, role, trust), count in sorted(panel_a.items()):
            writer.writerow(["A", role, family, trust, count])
        for (role, target), count in sorted(panel_b_counts.items()):
            writer.writerow(["B", role, target, panel_b_family[(role, target)].most_common(1)[0][0], count])
        for (x, y), count in sorted(panel_c_counts.items()):
            writer.writerow(["C", x, y, panel_c_role[(x, y)].most_common(1)[0][0], count])
        for (family, app), count in sorted(panel_d.items()):
            writer.writerow(["D", app, family, "", count])

    fig, axes = plt.subplots(2, 2, figsize=(15.4, 11.2))
    ax_a, ax_b, ax_c, ax_d = axes.ravel()

    # Panel A
    x_role = {role: i for i, role in enumerate(ROLE_ORDER)}
    y_family = {family: i for i, family in enumerate(FAMILY_ORDER)}
    max_a = max(panel_a.values()) if panel_a else 1
    for (family, role, trust), count in panel_a.items():
        ax_a.scatter(
            x_role[role],
            y_family[family],
            s=42 + 650 * count / max_a,
            facecolor=TRUST_COLORS[trust],
            edgecolor="white",
            linewidth=0.8,
            alpha=0.82,
        )
        if count >= 7:
            ax_a.text(x_role[role], y_family[family], str(count), ha="center", va="center", color="white", fontsize=7.5, fontweight="bold")
    ax_a.set_xticks(range(len(ROLE_ORDER)), ROLE_ORDER, rotation=25, ha="right")
    ax_a.set_yticks(range(len(FAMILY_ORDER)), FAMILY_ORDER)
    ax_a.grid(True, color="#DDDDDD")
    ax_a.set_axisbelow(True)
    ax_a.set_title("A. Model class x optimizer role", loc="left", fontweight="bold")

    # Panel B
    y_target = {target: i for i, target in enumerate(TARGET_ORDER)}
    max_b = max(panel_b_counts.values()) if panel_b_counts else 1
    for (role, target), count in panel_b_counts.items():
        family = panel_b_family[(role, target)].most_common(1)[0][0]
        trust = panel_b_trust[(role, target)].most_common(1)[0][0]
        ax_b.scatter(
            x_role[role],
            y_target[target],
            s=50 + 700 * count / max_b,
            facecolor=FAMILY_COLORS[family],
            edgecolor=TRUST_COLORS[trust],
            linewidth=2.2,
            alpha=0.82,
        )
        if count >= 4:
            ax_b.text(x_role[role], y_target[target], str(count), ha="center", va="center", color="white", fontsize=7.5, fontweight="bold")
    ax_b.set_xticks(range(len(ROLE_ORDER)), ROLE_ORDER, rotation=25, ha="right")
    ax_b.set_yticks(range(len(TARGET_ORDER)), TARGET_ORDER)
    ax_b.grid(True, color="#DDDDDD")
    ax_b.set_axisbelow(True)
    ax_b.set_title("B. Surrogate target x optimizer role", loc="left", fontweight="bold")

    # Panel C
    max_c = max(panel_c_counts.values()) if panel_c_counts else 1
    for (x, y), count in panel_c_counts.items():
        role = panel_c_role[(x, y)].most_common(1)[0][0]
        family = panel_c_family[(x, y)].most_common(1)[0][0]
        ax_c.scatter(
            x,
            y,
            s=60 + 760 * count / max_c,
            facecolor=ROLE_COLORS[role],
            edgecolor="#333333",
            linewidth=0.9,
            alpha=0.82,
        )
        ax_c.text(x, y + 0.03, str(count), ha="center", va="center", color="white", fontsize=7.8, fontweight="bold")
        if count >= 7:
            ax_c.text(x, y - 0.23, family.replace(" / ", "/"), ha="center", va="center", color="#222222", fontsize=6.7)
    ax_c.set_xticks(range(4), ["unclear", "batch /\nhistorical", "static\nDoE", "sequential /\nmulti-source"])
    ax_c.set_yticks(range(4), ["unclear", "point\nmetrics", "operational /\nUQ", "decision /\nrobust"])
    ax_c.set_xlim(-0.55, 3.55)
    ax_c.set_ylim(-0.55, 3.55)
    ax_c.grid(True, color="#DDDDDD")
    ax_c.set_axisbelow(True)
    ax_c.set_title("C. Reported DoE x validation depth", loc="left", fontweight="bold")
    ax_c.set_xlabel("Training-design depth")
    ax_c.set_ylabel("Validation depth")

    # Panel D
    top_apps = [app for app, _ in Counter(app for _, app in panel_d).most_common(7)]
    left = [0] * len(FAMILY_ORDER)
    ypos = range(len(FAMILY_ORDER))
    for app in top_apps:
        vals = [panel_d.get((family, app), 0) for family in FAMILY_ORDER]
        ax_d.barh(ypos, vals, left=left, color=TARGET_COLORS[app], label=app, height=0.68)
        left = [a + b for a, b in zip(left, vals)]
    ax_d.set_yticks(list(ypos), FAMILY_ORDER)
    ax_d.grid(axis="x", color="#DDDDDD")
    ax_d.set_axisbelow(True)
    ax_d.set_title("D. Main application targets", loc="left", fontweight="bold")
    ax_d.set_xlabel("Tagged paper count")

    trust_handles = [
        Line2D([0], [0], marker="o", color="none", markerfacecolor=TRUST_COLORS[t], markersize=7, label=TRUST_LABELS[t])
        for t in ("basic", "adaptive", "uncertainty", "physics", "constraint", "decision")
    ]
    family_handles = [
        Line2D([0], [0], marker="o", color="none", markerfacecolor=FAMILY_COLORS[f], markersize=7, label=f)
        for f in FAMILY_ORDER
    ]
    role_handles = [
        Line2D([0], [0], marker="o", color="none", markerfacecolor=ROLE_COLORS[r], markersize=7, label=r)
        for r in ROLE_ORDER
    ]

    fig.legend(handles=trust_handles, title="Trust signal (Panel A fill; Panel B ring)", loc="lower left", bbox_to_anchor=(0.02, 0.012), ncol=3, frameon=False, fontsize=8, title_fontsize=9)
    fig.legend(handles=family_handles, title="Model class (Panel B fill)", loc="lower center", bbox_to_anchor=(0.51, 0.012), ncol=4, frameon=False, fontsize=8, title_fontsize=9)
    fig.legend(handles=role_handles, title="Integration role (Panel C fill)", loc="lower right", bbox_to_anchor=(0.99, 0.012), ncol=2, frameon=False, fontsize=8, title_fontsize=9)
    ax_d.legend(title="Application target (Panel D)", loc="lower right", frameon=False, fontsize=8, title_fontsize=9)

    fig.suptitle("Draft quantitative synthesis of surrogate taxonomy, evidence depth and applications", fontsize=15, fontweight="bold", y=0.985)
    fig.text(
        0.01,
        0.002,
        (
            f"Sources: Panels A/B/D use curated library bucket tags, non-review model-class records n={len(library_records)}; "
            f"Panel C uses PDF-backed evidence cards n={len(cards)}. Draft classification for visual review."
        ),
        fontsize=8,
        color="#555555",
    )
    fig.tight_layout(rect=(0, 0.105, 1, 0.955), h_pad=2.0, w_pad=2.0)
    for ext in ("png",):
        fig.savefig(FIG / f"fig_four_panel_taxonomy_synthesis_draft.{ext}", dpi=300, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()
