"""Build PDF-backed evidence cards for Section 8 narrative (study-level).

Run from review_surrogate_modeling root::
    py paper_library/build_sec8_evidence_cards.py
"""
from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tables"))
import build_table_T6_evidence_map as t6  # noqa: E402

MANIFEST = ROOT / "paper_library" / "review_paper_library_manifest_T6_compact.csv"
T6_TEX = ROOT / "manuscript" / "appendix" / "table_T6_evidence_map.tex"
PDF_MAP = ROOT / "_tmp_pdf_author_title_match_map.csv"
LIT = ROOT / "Literatur"
BIB = ROOT / "references" / "review_mes_moo_surrogates.bib"
OUT_CSV = ROOT / "paper_library" / "sec8_evidence_cards.csv"
OUT_JSON = ROOT / "paper_library" / "sec8_by_subsection.json"

SECTION_ORDER = (
    "mes",
    "moo",
    "microgrid",
    "dh",
    "dispatch",
    "opf",
    "expansion",
    "stochastic",
)

SECTION_LABEL = {
    "mes": "Multi-energy and sector-coupled systems",
    "moo": "Multi-objective energy system design",
    "microgrid": "Microgrids and energy hubs",
    "dh": "District heating systems and thermal storage",
    "dispatch": "Economic dispatch and unit commitment",
    "opf": "Optimal power flow and AC relaxations",
    "expansion": "Capacity and generation expansion planning",
    "stochastic": "Stochastic and robust energy planning",
}

STRICT_MES_HINTS = (
    "multi-energy",
    "integrated energy",
    "integrated electricity",
    "integrated community energy",
    "sector-coupled",
    "electricity-heat",
    "electricity heat",
    "cchp",
    "combined cooling, heating",
    "power-to-x",
    "power to x",
    "multi-carrier",
    "regional integrated energy",
)

DETAIL_LIMIT = {"mes": 28, "moo": 22, "microgrid": 14, "dh": 6, "dispatch": 5, "opf": 5, "expansion": 5, "stochastic": 5}


def load_pdf_paths() -> Dict[str, Path]:
    out: Dict[str, Path] = {}
    if not PDF_MAP.is_file():
        return out
    with PDF_MAP.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            key = (row.get("mapped_key") or "").strip()
            rel = (row.get("pdf_relpath") or "").strip().replace("\\", "/")
            if key and key not in out and rel:
                p = LIT / rel
                if p.is_file():
                    out[key] = p
    return out


def parse_t6_table() -> Dict[str, Dict[str, str]]:
    text = T6_TEX.read_text(encoding="utf-8")
    rows: Dict[str, Dict[str, str]] = {}
    pat = re.compile(
        r"\\cite\{([^}]+)\}\s*&\s*(\d{4})\s*&\s*(.*?)\s*&\s*(.*?)\s*&\s*(.*?)\s*&\s*(.*?)\\\\",
        re.DOTALL,
    )
    for m in pat.finditer(text):
        key = m.group(1).strip()
        rows[key] = {
            "year": m.group(2).strip(),
            "topic": re.sub(r"\s+", " ", m.group(3)).strip(),
            "family": m.group(4).strip(),
            "doe": m.group(5).strip(),
            "validation": m.group(6).strip(),
        }
    return rows


def load_bib_authors() -> Dict[str, str]:
    if not BIB.is_file():
        return {}
    blob = BIB.read_text(encoding="utf-8", errors="replace")
    out: Dict[str, str] = {}
    for block in re.split(r"\n@", blob):
        km = re.search(r"\{([^,]+),", block)
        if not km:
            continue
        key = km.group(1).strip()
        am = re.search(r"author\s*=\s*\{", block, re.I)
        if not am:
            continue
        start = am.end()
        depth = 1
        i = start
        while i < len(block) and depth:
            if block[i] == "{":
                depth += 1
            elif block[i] == "}":
                depth -= 1
            i += 1
        author_field = block[start : i - 1]
        first = author_field.split(" and ")[0].strip()
        if "," in first:
            surname = first.split(",")[0].strip()
        else:
            parts = first.split()
            surname = parts[-1] if parts else key
        surname = re.sub(r"[{}\\]", "", surname)
        out[key] = f"{surname} et al."
    return out


def is_strict_mes(buckets: Set[str], title: str) -> bool:
    t = title.lower()
    hint = any(h in t for h in STRICT_MES_HINTS)
    # B21 alone is noisy (OpenAlex topic); require a sector-coupling title signal too.
    if "B21_mes_sector_coupling" in buckets:
        return hint
    return hint


def primary_section(raw: Dict[str, str], bucket_index: Dict[str, List[str]]) -> str:
    buckets = set(t6.paper_buckets(raw, bucket_index))
    title = (raw.get("title") or "").lower()
    task = t6.infer_task(title, list(buckets))
    moo_title = any(k in title for k in ("multi-objective", "pareto", "nsga"))

    # Microgrid/hub before broad MES title hints (many HRES papers mention ``microgrid'').
    if "B22_microgrid_hub" in buckets or "microgrid" in title or "energy hub" in title:
        if ("B23_moo_design" in buckets or task == "MOO design") and moo_title:
            return "moo"
        return "microgrid"
    if task == "MOO design" or "B23_moo_design" in buckets:
        return "moo"
    if is_strict_mes(buckets, title):
        if ("B23_moo_design" in buckets) and moo_title:
            return "moo"
        return "mes"
    if task == "DH" or "B20_district_heating" in buckets:
        return "dh"
    if task == "ED / UC" or "B17_ed_uc" in buckets:
        return "dispatch"
    if task == "OPF" or "B18_opf" in buckets:
        return "opf"
    if task == "CapEx" or "B19_capacity_expansion" in buckets:
        return "expansion"
    if task == "Stoch / robust" or "B24_stochastic_robust" in buckets:
        t_low = title.lower()
        if any(
            k in t_low
            for k in (
                "distribution network",
                "voltage",
                "opf",
                "optimal power",
                "power flow",
                "conservation voltage",
            )
        ):
            return "opf"
        if any(k in t_low for k in ("dispatch", "unit commitment", "economic dispatch")):
            return "dispatch"
        if task == "CapEx" or "expansion" in t_low or "capacity" in t_low:
            return "expansion"
        return "opf"
    if "district heating" in title or "district cooling" in title:
        return "dh"
    return "dispatch"


def infer_pattern(title: str, buckets: List[str]) -> str:
    role = t6.infer_role(title, buckets, t6.infer_task(title, buckets))
    if role in {"P1", "P1/P3"}:
        return "P1"
    if role == "P2":
        return "P2"
    if role == "P5":
        return "P5"
    if role == "P4":
        return "P4"
    return role or "--"


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
    """Drop trailing title fragments left incomplete by length cuts."""
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


def short_system(title: str) -> str:
    """Compact study label for Section~8 (no trailing ellipsis)."""
    t = re.sub(r"\s+", " ", (title or "").strip())
    if len(t) > 120:
        for sep in (". ", ": ", " — ", " - "):
            idx = t.find(sep)
            if 20 < idx <= 120:
                t = t[:idx]
                break
        else:
            t = t[:120].rsplit(" ", 1)[0]
    t = _strip_dangling_title(t)
    return t6.latex_escape(t)


def infer_doe_prose(
    title: str, family: str, doe_bucket: str, pdf_text: str = ""
) -> str:
    """Study-level training-point statement aligned with Section~5 (fail closed).

    T6 buckets such as ``LHS / quasi-MC`` group *different* static designs;
    this function must not collapse them into ``LHS or quasi-MC'' unless the
    accessible text supports one regime.
    """
    if doe_bucket == "--" or not doe_bucket:
        return ""

    blob = f"{title} {pdf_text[:20000]}".lower()

    def has(*keys: str) -> bool:
        return any(k in blob for k in keys)

    if doe_bucket == "Historical data":
        if has("historical", "measured data", "operating data", "field data"):
            return "The emulator is trained from historically observed operating data."
        return ""

    if doe_bucket == "Transfer learning":
        if has("transfer learning", "transferred knowledge"):
            return "Emulator training transfers information across related datasets."
        return ""

    if doe_bucket == "Multi-fidelity":
        if has("multi-fidelity", "multi fidelity", "co-kriging", "cokriging"):
            return "Training combines multiple fidelity levels of the expensive model."
        return ""

    if doe_bucket == "Active learning":
        if has("bayesian optimization", "acquisition function", "expected improvement"):
            return (
                "Further simulation runs are chosen by Bayesian optimization "
                "(acquisition-driven active learning)."
            )
        if has("active learning", "informativeness", "vote-by-committee"):
            return "Further simulation runs are chosen by an active-learning rule."
        return ""

    if doe_bucket == "Adaptive sampling":
        # Section~5: infill during surrogate-assisted search — not generic ``DoE''.
        lhs_init = has("latin hypercube", " lhs ", "lhs design", "lhs sampling")
        infill = has(
            "infill",
            "infill criterion",
            "infill point",
            "expected improvement",
            "efficient global optimization",
            "ego ",
            "trust-region",
            "trust region",
        )
        if lhs_init and infill:
            return (
                "Training starts with Latin hypercube samples; further points are "
                "added by infill rules during surrogate-assisted search."
            )
        if infill or has("kriging-assisted", "kriging assisted"):
            return (
                "Training points are added sequentially by infill rules during "
                "surrogate-assisted search."
            )
        if has("adaptive sampling", "sequential design", "adaptive design of experiments"):
            return (
                "Training points are added sequentially during surrogate-assisted "
                "search (adaptive sampling)."
            )
        if lhs_init:
            return "Training inputs are placed by Latin hypercube sampling."
        return ""

    if doe_bucket == "Factorial / DoE":
        if has("box-behnken", "box behnken"):
            return "Training runs follow a Box--Behnken design over factor levels."
        if has("factorial", "taguchi", "fractional factorial", "full factorial"):
            return "Training runs follow factorial designs over discrete factor levels."
        if has("design of experiments", "design of experiment", "experimental design"):
            return "Training runs follow structured design-of-experiments grids."
        if has("response surface", "response-surface", " rsm", "rsm "):
            return (
                "Training runs explore discrete factor combinations for "
                "response-surface fitting."
            )
        return ""

    if doe_bucket == "LHS / quasi-MC":
        lhs = has("latin hypercube", " lhs ", "lhs design", "lhs sampling")
        sobol = has("sobol", "halton", "low-discrepancy", "low discrepancy")
        qmc = has("quasi-monte", "quasi monte", "quasimonte")
        sparse = has(
            "sparse grid",
            "sparse-grid",
            "collocation",
            "quadrature",
            "galerkin projection",
            "galerkin",
        )
        pce_collocation = has(
            "polynomial chaos",
            "pce",
            "chaos expansion",
            "sparse grid",
            "sparse-grid",
            "collocation",
            "quadrature",
            "galerkin",
        )

        if lhs and not (sobol or qmc or sparse or pce_collocation):
            return "Training inputs are placed by Latin hypercube sampling over the planning box."
        if (sobol or qmc) and not lhs:
            return (
                "Uncertain inputs are represented by quasi-Monte Carlo "
                "(low-discrepancy) sample sets."
            )
        if sparse or pce_collocation:
            return (
                "Uncertain inputs are represented by sparse-grid or PCE collocation nodes "
                "(quasi-Monte Carlo / quadrature family)."
            )
        if lhs and (sobol or qmc or sparse):
            return ""
        return ""

    return ""


def infer_validation_prose(title: str, pdf_text: str) -> str:
    """Section~7 validation beyond point metrics; PDF-grounded, fail-closed."""
    blob = f"{title} {pdf_text[:25000]}".lower()

    def has(*keys: str) -> bool:
        return any(k in blob for k in keys)

    if has(
        "regret",
        "optimality gap",
        "suboptimality",
        "decision-aware",
        "decision aware",
    ):
        return (
            "Validation reports regret or optimality-gap checks, not only fit error."
        )

    if has(
        "feasibility rate",
        "feasibility of",
        "constraint violation",
        "violation severity",
        "violation rate",
        "feasible rate",
        "probability of feasibility",
    ):
        return (
            "Validation reports feasibility or constraint violations on the host problem."
        )

    if has("stress test", "stress-test", "extreme scenario", "extreme event"):
        return "Validation includes stress-test blocks."

    if has(
        "out-of-distribution",
        "out of distribution",
        " ood ",
        "policy shift",
        "distribution shift",
    ):
        return "Validation tests out-of-distribution or policy-shift behaviour."

    if has(
        "prediction interval",
        "interval coverage",
        "coverage probability",
        "calibration plot",
        "reliability diagram",
        "pit histogram",
    ) or (
        has("calibration")
        and has("interval", "quantile", "posterior", "uncertainty band")
    ):
        return "Validation assesses prediction-interval calibration."

    return ""


def pdf_claim_snippets(text: str) -> Dict[str, str]:
    low = text.lower()[:25000]
    out: Dict[str, str] = {}
    if re.search(r"order[s]?\s+of\s+magnitude|100\s*[×x]\s*faster|two orders", low):
        out["speed"] = "large reported speed-up"
    elif re.search(r"speed[- ]?up|runtime reduction|computational time", low):
        out["speed"] = "reported runtime reduction"
    if re.search(r"regret|optimality gap|suboptimality", low):
        out["decision"] = "decision-aware metric"
    if re.search(r"pareto|non-dominated|nsga", low):
        out["moo"] = "Pareto-front search"
    return out


def doe_phrase(doe: str) -> str:
    if doe == "--" or not doe:
        return "DoE practice is not stated clearly in the accessible text"
    if "sampling" in doe.lower():
        return f"training follows {doe} (Section~\\ref{{sec:doe}})"
    return f"training follows {doe} sampling (Section~\\ref{{sec:doe}})"


def validation_phrase(val: str) -> str:
    if val == "--" or not val:
        return "validation detail is limited in the accessible text (Section~\\ref{{sec:validation}})"
    tags = val.replace("; ", ", ")
    return f"reported validation: {tags} (Section~\\ref{{sec:validation}})"


def family_phrase(fam: str) -> str:
    if fam == "--" or not fam:
        return "a surrogate class that is not tagged clearly in Table~\\ref{{tab:T6-evidence-map}}"
    return f"a {fam} surrogate (Section~\\ref{{sec:taxonomy}}, Table~\\ref{{tab:T6-evidence-map}})"


def pattern_phrase(pat: str) -> str:
    m = {
        "P1": "Pattern~P1 (substitute inner solver/simulator, Section~\\ref{sec:integration})",
        "P2": "Pattern~P2 (accelerate outer search, Section~\\ref{sec:integration})",
        "P5": "Pattern~P5 (uncertainty propagation or chance constraints, Section~\\ref{sec:integration})",
        "P4": "Pattern~P4 (decomposition layer, Section~\\ref{sec:integration})",
    }
    return m.get(pat, "an integration pattern aligned with Section~\\ref{sec:integration}")


def build_card(
    raw: Dict[str, str],
    t6_row: Dict[str, str],
    pdf: Optional[Path],
    authors: Dict[str, str],
    bucket_index: Dict[str, List[str]],
) -> Dict[str, str]:
    key = raw["cite_key"]
    title = raw.get("title") or ""
    buckets = list(t6.paper_buckets(raw, bucket_index))
    pdf_text = t6.extract_pdf_text(pdf) if pdf else ""
    claims = pdf_claim_snippets(pdf_text) if pdf_text else {}

    doe_bucket = t6_row.get("doe", "--")
    return {
        "cite_key": key,
        "author_label": authors.get(key, "Authors"),
        "year": raw.get("year", t6_row.get("year", "")),
        "section": primary_section(raw, bucket_index),
        "tier": "detail",
        "has_pdf": "yes" if pdf else "no",
        "system": short_system(title),
        "topic": t6_row.get("topic", raw.get("primary_topic", "")),
        "family": t6_row.get("family", "--"),
        "doe": doe_bucket,
        "doe_prose": infer_doe_prose(
            title, t6_row.get("family", "--"), doe_bucket, pdf_text
        ),
        "validation": t6_row.get("validation", "--"),
        "validation_prose": infer_validation_prose(title, pdf_text),
        "pattern": infer_pattern(title, buckets),
        "pdf_claims": ";".join(claims.values()),
        "cited_by_count": raw.get("cited_by_count", ""),
    }


def render_detail_sentence(card: Dict[str, str]) -> str:
    key = card["cite_key"]
    extra = card.get("pdf_claims", "")
    speed = ""
    if "large reported speed-up" in extra:
        speed = " They report order-of-magnitude runtime gains."
    elif "reported runtime reduction" in extra:
        speed = " They report reduced runtime versus repeated truth-model solves."
    if "decision-aware metric" in extra:
        speed += " Decision-quality metrics accompany the fit scores."
    if "Pareto-front search" in extra and card["section"] in {"moo", "mes", "microgrid"}:
        speed += " The study targets Pareto-efficient alternatives."

    # Concatenate: nested LaTeX \\ref{...} in family_phrase must not pass through f-strings.
    return (
        card["author_label"]
        + "~\\cite{"
        + key
        + "} address "
        + card["system"]
        + ". The work uses "
        + family_phrase(card["family"])
        + " under "
        + pattern_phrase(card["pattern"])
        + "; "
        + doe_phrase(card["doe"])
        + "; "
        + validation_phrase(card["validation"])
        + "."
        + speed
    )


def render_compact_sentence(card: Dict[str, str]) -> str:
    key = card["cite_key"]
    return (
        f"{card['author_label']}~\\cite{{{key}}} "
        f"({card['family']}, {card['pattern']}; {card['doe']}; {card['validation']})."
    )


def main() -> int:
    bucket_index = t6.load_bucket_index()
    pdf_paths = load_pdf_paths()
    t6_rows = parse_t6_table()
    authors = load_bib_authors()

    cards: List[Dict[str, str]] = []
    with MANIFEST.open(encoding="utf-8", newline="") as f:
        for raw in csv.DictReader(f):
            if t6.is_review_paper(raw, bucket_index):
                continue
            key = raw["cite_key"]
            pdf = pdf_paths.get(key)
            if not pdf:
                continue
            cards.append(
                build_card(raw, t6_rows.get(key, {}), pdf, authors, bucket_index)
            )

    by_sec: Dict[str, List[Dict[str, str]]] = {s: [] for s in SECTION_ORDER}
    for c in cards:
        by_sec.setdefault(c["section"], []).append(c)

    for sec in by_sec:
        by_sec[sec].sort(
            key=lambda x: (
                -int(x["cited_by_count"]) if str(x["cited_by_count"]).isdigit() else 0,
                x["cite_key"],
            )
        )
        limit = DETAIL_LIMIT.get(sec, 5)
        for i, c in enumerate(by_sec[sec]):
            c["tier"] = "detail" if i < limit else "compact"

    with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(cards[0].keys()))
        w.writeheader()
        for sec in SECTION_ORDER:
            w.writerows(by_sec.get(sec, []))

    narrative: Dict[str, object] = {}
    for sec in SECTION_ORDER:
        items = by_sec.get(sec, [])
        narrative[sec] = {
            "label": SECTION_LABEL[sec],
            "cards": items,
            "n": len(items),
        }

    OUT_JSON.write_text(json.dumps(narrative, indent=2), encoding="utf-8")
    print(f"wrote {len(cards)} PDF-backed cards to {OUT_CSV.name}")
    for sec in SECTION_ORDER:
        d = sum(1 for c in by_sec.get(sec, []) if c["tier"] == "detail")
        print(f"  {sec}: {len(by_sec.get(sec, []))} ({d} detail)")
    print(f"wrote {OUT_JSON.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
