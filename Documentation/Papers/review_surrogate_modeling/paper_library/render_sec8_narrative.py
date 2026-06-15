"""Render Section~8: case bridges plus paper-specific sentences (one cite each).

Run after build_sec8_evidence_cards.py::
    py paper_library/render_sec8_narrative.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

ROOT = Path(__file__).resolve().parent.parent
IN_JSON = ROOT / "paper_library" / "sec8_by_subsection.json"
OUT_TEX = ROOT / "manuscript" / "08_application_evidence_map.tex"

SECTION_META = [
    ("mes", "Multi-energy and sector-coupled systems", "sec:apps:mes"),
    ("moo", "Multi-objective energy system design", "sec:apps:moo"),
    ("microgrid", "Microgrids and energy hubs", "sec:apps:microgrid"),
    ("dh", "District heating systems and thermal storage", "sec:apps:dh"),
    ("dispatch", "Economic dispatch and unit commitment", "sec:apps:dispatch"),
    ("opf", "Optimal power flow and AC relaxations", "sec:apps:opf"),
    ("expansion", "Capacity and generation expansion planning", "sec:apps:expansion"),
]

INTRO = r"""\section{Applications and evidence map}
\label{sec:applications}

Table~\ref{tab:T6-evidence-map} lists the curated studies.
The narrative below alternates short case sketches with study-level statements.
Each citation supports one claim; emulator class, integration role, and
training-point design are stated separately only when the accessible PDF
or title supports one clear sampling regime (not merged T6 bucket labels).
Sector-coupled multi-energy systems are discussed first.

% BEGIN inlined table table_T6_evidence_map
\input{appendix/table_T6_evidence_map}
% END inlined table table_T6_evidence_map

"""

SYNTHESIS = r"""\subsection{Synthesis: where surrogates help, where they do not}
\label{sec:apps:synthesis}

Taken together, the evidence map supports four observations.
\emph{First}, sector-coupled and MOO studies predominantly use surrogates
to accelerate outer-loop search, whereas dispatch and OPF work more often
replace inner solves or handle uncertainty in the reformulation layer.
\emph{Second}, Gaussian-process and response-surface models remain frequent
in MES and MOO, while neural proxies dominate OPF replacement and several
DH metamodels. \emph{Third}, most studies still stop at point fit metrics;
feasibility-rate reporting and decision-aware regret or gap metrics remain
the exception outside dispatch and chance-constrained strands.
\emph{Fourth}, the open MES question is how surrogate-derived Pareto or robust
solutions should be communicated to decision makers
\cite{Mylonopoulos202332697,Lim2025}.
"""

MIN_CLUSTER_BRIDGE = 4

_SKIP_VAL_TAGS = frozenset(
    {
        "Fit metrics",
        "Point metrics (RMSE/MAE/R²)",
        "Validation",
        "Uncertainty",
        "Uncertainty (problem UQ)",
    }
)

_VAL_SENTENCE: Dict[str, str] = {
    "Decision-aware (regret/gap)": "Validation reports regret or optimality-gap checks, not only fit error.",
    "Decision-aware": "Validation reports regret or optimality-gap checks, not only fit error.",
    "Feasibility rate": "Validation reports feasibility or constraint violations on the host problem.",
    "Feasibility": "Validation reports feasibility or constraint violations on the host problem.",
    "Stress test": "Validation includes stress-test blocks.",
    "OOD / policy shift": "Validation tests out-of-distribution or policy-shift behaviour.",
    "OOD": "Validation tests out-of-distribution or policy-shift behaviour.",
    "Interval calibration": "Validation assesses prediction-interval calibration.",
    "Calibration": "Validation assesses prediction-interval calibration.",
}

CLUSTER_BRIDGES = (
    "Several studies in {themes} use {fam} emulators {integration}.",
    "A common thread in {themes} is {fam} emulators {integration}.",
    "Much of the work on {themes} embeds {fam} emulators {integration}.",
    "The contributions below on {themes} mainly use {fam} emulators {integration}.",
)

OPENING_FRAMES: Tuple[str, ...] = (
    "{author}~\\cite{{{key}}} examine {topic}.",
    "{author}~\\cite{{{key}}} address {topic}.",
    "For {topic}, {author}~\\cite{{{key}}} report a surrogate-assisted formulation.",
    "Regarding {topic}, {author}~\\cite{{{key}}} present an application study.",
    "In work on {topic}, {author}~\\cite{{{key}}} develop a computational workflow.",
    "{topic} is analysed by {author}~\\cite{{{key}}}.",
    "{author}~\\cite{{{key}}} study {topic}.",
    "{author}~\\cite{{{key}}} target {topic}.",
)


def cluster_key(card: Dict[str, str]) -> Tuple[str, str]:
    return (card.get("pattern", "--"), card.get("family", "--"))


def emulator_label(fam: str) -> str:
    """Surrogate / emulator class (Section~4 taxonomy), not a sampling design."""
    m = {
        "GP / kriging": "Gaussian-process or kriging",
        "Neural network": "neural-network",
        "PCE / RSM": "polynomial-chaos expansion or response-surface",
        "RBF / kernel": "RBF or kernel",
        "Tree ensembles": "tree-ensemble",
        "Hybrid / PINN": "physics-informed neural",
        "L2O / decision-focused": "learning-to-optimize",
        "Constraint-aware NN": "constraint-aware neural",
    }
    if fam == "--":
        return ""
    return m.get(fam, fam.lower())


def integration_clause(pat: str) -> str:
    """How the emulator is embedded in the host problem."""
    m = {
        "P1": "to replace expensive inner optimisation solves in the host problem",
        "P2": "inside an outer multi-objective or evolutionary search loop",
        "P3": "to warm-start repeated operational solves",
        "P4": "within a decomposition layer (recourse or pricing)",
        "P5": "to propagate uncertainty in chance- or robust-constrained formulations",
        "P1/P3": "to replace or warm-start inner operational solves",
    }
    return m.get(pat, "")


def emulator_sentence(fam: str, pat: str) -> str:
    label = emulator_label(fam)
    integration = integration_clause(pat)
    if label and integration:
        return f"The emulator is {label}-based and is used {integration}."
    if label:
        return f"The emulator class is {label}-based."
    if integration:
        return f"The integration role is {integration.strip()}."
    return ""


def doe_sentence(card: Dict[str, str]) -> str:
    """Training-point design from build-time PDF/title pass (fail closed)."""
    return (card.get("doe_prose") or "").strip()


_WEAK_TAIL_WORDS = frozenset(
    {
        "to",
        "for",
        "in",
        "of",
        "and",
        "using",
        "with",
        "under",
        "on",
        "the",
        "based",
        "via",
        "from",
        "improve",
        "machine",
        "multiple",
        "empirical",
        "electric",
        "sparse",
        "ancillary",
        "flows",
        "a",
        "an",
    }
)


def _strip_dangling_title(t: str) -> str:
    bad = (
        " to",
        " for",
        " in",
        " of",
        " and",
        " using",
        " with",
        " under",
        " on",
        " the",
        " based",
        " via",
        " from",
    )
    changed = True
    while changed and t:
        changed = False
        low = t.lower()
        for suffix in bad:
            if low.endswith(suffix):
                t = t[: -len(suffix)].rstrip(" ,;:")
                changed = True
                break
    words = t.split()
    while len(words) > 5 and words[-1].lower() in _WEAK_TAIL_WORDS:
        words.pop()
    return " ".join(words)


def shorten_topic(card: Dict[str, str], *, sentence_start: bool = False) -> str:
    """Topic phrase for prose (no ellipsis, no dangling prepositions)."""
    t = re.sub(r"\s+", " ", (card.get("system") or "").strip())
    t = re.sub(r"\.{2,}$", "", t).strip().rstrip(",")
    if len(t) > 100:
        t = t[:100].rsplit(" ", 1)[0]
    t = _strip_dangling_title(t)
    if not t:
        return "the application setting in the cited study"
    if sentence_start:
        return t[0].upper() + t[1:] if len(t) > 1 else t.upper()
    return t[0].lower() + t[1:] if len(t) > 1 else t.lower()


def validation_sentence(card: Dict[str, str]) -> str:
    """Beyond point metrics only when PDF text supports it (not T6 tags alone)."""
    return (card.get("validation_prose") or "").strip()


def _parse_val_tags(val: str) -> List[str]:
    if not val or val == "--":
        return []
    return [t.strip() for t in val.split(";") if t.strip()]


def infer_themes(cards: Sequence[Dict[str, str]], section: str) -> str:
    blob = " ".join((c.get("system") or "").lower() for c in cards)
    if section == "mes":
        return "sector-coupled multi-carrier energy systems"
    if section == "moo":
        return "multi-objective energy-system design"
    if section == "microgrid":
        return "microgrid, energy-hub and VPP applications"
    if section == "dh":
        return "district heating and building thermal networks"
    if section == "dispatch":
        return "economic dispatch and unit commitment"
    if section == "opf":
        if any(
            k in blob
            for k in (
                "stochastic",
                "distributionally robust",
                "chance-constrained",
                "uncertainty",
            )
        ):
            return "AC optimal power flow and stochastic or robust distribution planning"
        return "AC optimal power flow and load-flow studies"
    if section == "expansion":
        return "generation and network expansion planning"
    return "energy-system optimisation"


def render_cluster_bridge(
    cards: List[Dict[str, str]], section: str, bridge_idx: int
) -> str:
    pat, fam = cluster_key(cards[0])
    tpl = CLUSTER_BRIDGES[bridge_idx % len(CLUSTER_BRIDGES)]
    integration = integration_clause(pat) or "in mixed integration roles"
    label = emulator_label(fam) or "surrogate"
    return tpl.format(
        fam=label,
        integration=integration,
        themes=infer_themes(cards, section),
    )


def render_paper_sentence(card: Dict[str, str], sent_idx: int) -> str:
    key = card["cite_key"]
    author = card.get("author_label") or "Authors"
    frame = OPENING_FRAMES[sent_idx % len(OPENING_FRAMES)]
    topic = shorten_topic(card, sentence_start=frame.startswith("{topic}"))
    opening = frame.format(author=author, key=key, topic=topic)

    parts = [opening]
    emu = emulator_sentence(card.get("family", "--"), card.get("pattern", "--"))
    if emu:
        parts.append(emu)
    doe = doe_sentence(card)
    if doe:
        parts.append(doe)
    val = validation_sentence(card)
    if val:
        parts.append(val)
    return " ".join(parts)


def cluster_cards(cards: List[Dict[str, str]]) -> List[List[Dict[str, str]]]:
    buckets: Dict[Tuple[str, str], List[Dict[str, str]]] = {}
    for c in cards:
        buckets.setdefault(cluster_key(c), []).append(c)
    clusters = list(buckets.values())
    clusters.sort(
        key=lambda grp: (
            -len(grp),
            -int(grp[0].get("cited_by_count") or 0),
            grp[0].get("cite_key", ""),
        )
    )
    for grp in clusters:
        grp.sort(
            key=lambda c: (
                -int(c.get("cited_by_count") or 0),
                c.get("cite_key", ""),
            )
        )
    return clusters


def subsection_intro(key: str) -> str:
    intros = {
        "mes": (
            "The MES strand covers electricity--heat--gas coupling, "
            "integrated dispatch and design."
        ),
        "moo": (
            "Multi-objective MES design most often couples surrogates "
            "with evolutionary Pareto search."
        ),
        "microgrid": (
            "Microgrid and energy-hub applications mix forecasting, "
            "scheduling, sizing and control."
        ),
        "dh": (
            "District heating work substitutes thermal metamodels "
            "inside operational models."
        ),
        "dispatch": (
            "Dispatch and unit commitment target repeated inner MILP/LP solves; "
            "stochastic and robust variants appear alongside deterministic dispatch."
        ),
        "opf": (
            "AC-OPF-focused work proxies nonlinear solves or propagates input "
            "uncertainty, including distribution-network planning and "
            "distributionally robust voltage control."
        ),
        "expansion": (
            "Expansion planning re-evaluates operational sub-models "
            "across investment candidates."
        ),
    }
    return intros.get(key, "")


def render_subsection_body(section: str, cards: List[Dict[str, str]]) -> List[str]:
    paragraphs: List[str] = []
    sent_idx = 0
    bridge_idx = 0
    for cluster in cluster_cards(cards):
        if len(cluster) >= MIN_CLUSTER_BRIDGE:
            paragraphs.append(render_cluster_bridge(cluster, section, bridge_idx))
            bridge_idx += 1
        for card in cluster:
            paragraphs.append(render_paper_sentence(card, sent_idx))
            sent_idx += 1
    return paragraphs


def render_subsection(key: str, title: str, label: str, data: dict) -> str:
    cards: List[Dict[str, str]] = data.get("cards", [])
    if not cards:
        return ""
    lines = [
        f"\\subsection{{{title}}}",
        f"\\label{{{label}}}",
        "",
        subsection_intro(key),
        "",
    ]
    for p in render_subsection_body(key, cards):
        lines.append(p)
        lines.append("")
    return "\n".join(lines) + "\n"


def main() -> int:
    data = json.loads(IN_JSON.read_text(encoding="utf-8"))
    parts = [INTRO]
    for key, title, label in SECTION_META:
        if key not in data or not data[key].get("cards"):
            continue
        block = render_subsection(key, title, label, data[key])
        if block:
            parts.append(block)
    parts.append(SYNTHESIS)
    OUT_TEX.write_text("".join(parts), encoding="utf-8")
    print(f"wrote {OUT_TEX.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
