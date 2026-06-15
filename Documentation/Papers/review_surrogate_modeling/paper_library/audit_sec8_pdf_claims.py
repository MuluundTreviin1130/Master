"""Audit Section~8 doe_prose and validation tags against accessible PDF text.

Run from review_surrogate_modeling root::
    py paper_library/audit_sec8_pdf_claims.py
"""
from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tables"))
import build_table_T6_evidence_map as t6  # noqa: E402

from build_sec8_evidence_cards import infer_doe_prose, infer_validation_prose  # noqa: E402

CARDS_CSV = ROOT / "paper_library" / "sec8_evidence_cards.csv"
PDF_MAP = ROOT / "_tmp_pdf_author_title_match_map.csv"
LIT = ROOT / "Literatur"
OUT_CSV = ROOT / "paper_library" / "sec8_pdf_audit.csv"
OUT_JSON = ROOT / "paper_library" / "sec8_pdf_audit_summary.json"

_SKIP_VAL = frozenset(
    {
        "Fit metrics",
        "Point metrics (RMSE/MAE/R²)",
        "Validation",
        "Uncertainty",
        "Uncertainty (problem UQ)",
    }
)


def load_pdf_paths() -> Dict[str, Path]:
    out: Dict[str, Path] = {}
    if not PDF_MAP.is_file():
        return out
    with PDF_MAP.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            key = (row.get("mapped_key") or "").strip()
            rel = (row.get("pdf_relpath") or "").strip().replace("\\", "/")
            if key and rel and key not in out:
                p = LIT / rel
                if p.is_file():
                    out[key] = p
    return out


def parse_val_tags(val: str) -> List[str]:
    if not val or val == "--":
        return []
    return [t.strip() for t in val.split(";") if t.strip()]


def pdf_blob(title: str, text: str, n: int = 25000) -> str:
    return f"{title} {text[:n]}".lower()


def check_doe_prose(prose: str, blob: str) -> str:
    if not prose:
        return "absent"
    checks: List[Tuple[str, Tuple[str, ...]]] = [
        ("Latin hypercube", ("latin hypercube", " lhs ", "lhs design", "lhs sampling")),
        (
            "sparse-grid or PCE",
            (
                "sparse grid",
                "sparse-grid",
                "collocation",
                "quadrature",
                "polynomial chaos",
                " pce",
                "chaos expansion",
                "galerkin",
            ),
        ),
        ("quasi-Monte Carlo", ("quasi-monte", "quasi monte", "sobol", "halton", "low-discrepancy")),
        ("factorial", ("factorial", "taguchi", "box-behnken", "box behnken")),
        (
            "design-of-experiments",
            ("design of experiments", "design of experiment", "experimental design"),
        ),
        (
            "response-surface fitting",
            ("response surface", "response-surface", "rsm"),
        ),
        ("infill", ("infill", "expected improvement", "efficient global optimization", "ego ")),
        (
            "surrogate-assisted search",
            ("kriging-assisted", "kriging assisted", "surrogate-assisted", "surrogate assisted"),
        ),
        ("active-learning", ("active learning", "acquisition function", "bayesian optimization")),
        ("multi-fidelity", ("multi-fidelity", "multi fidelity", "co-kriging", "cokriging")),
        ("historical", ("historical data", "historically observed", "measured data", "field data")),
        ("transfer learning", ("transfer learning",)),
    ]
    for label, keys in checks:
        if label.lower() in prose.lower():
            if any(k in blob for k in keys):
                return "pdf_supported"
            return "pdf_missing"
    return "unclassified_prose"


def check_validation_tag(tag: str, blob: str) -> str:
    if tag in _SKIP_VAL:
        return "narrative_skipped"
    mapping = {
        "Decision-aware (regret/gap)": ("regret", "optimality gap", "decision-aware"),
        "Decision-aware": ("regret", "optimality gap", "decision-aware"),
        "Feasibility rate": (
            "feasibility rate",
            "feasibility of",
            "constraint violation",
            "violation severity",
        ),
        "Feasibility": (
            "feasibility rate",
            "feasibility of",
            "constraint violation",
            "violation severity",
        ),
        "Stress test": ("stress test", "stress-test", "extreme scenario", "extreme event"),
        "OOD / policy shift": (
            "out-of-distribution",
            "out of distribution",
            " ood ",
            "policy shift",
        ),
        "OOD": ("out-of-distribution", "out of distribution", " ood ", "policy shift"),
        "Interval calibration": (
            "prediction interval",
            "interval coverage",
            "coverage probability",
            "calibration plot",
            "reliability diagram",
        ),
        "Calibration": (
            "prediction interval",
            "interval coverage",
            "calibration plot",
            "reliability diagram",
        ),
    }
    keys = mapping.get(tag)
    if not keys:
        return "unknown_tag"
    if any(k in blob for k in keys):
        return "pdf_supported"
    return "pdf_missing"


def audit_card(card: Dict[str, str], pdf: Optional[Path]) -> Dict[str, str]:
    title = card.get("system", "").replace("...", "")
    text = t6.extract_pdf_text(pdf) if pdf else ""
    blob = pdf_blob(title, text)

    doe_prose = (card.get("doe_prose") or "").strip()
    doe_reinfer = infer_doe_prose(
        title, card.get("family", "--"), card.get("doe", "--"), text
    )
    doe_status = check_doe_prose(doe_prose, blob) if doe_prose else "absent"
    if doe_prose and doe_prose != doe_reinfer and doe_reinfer:
        doe_status = f"{doe_status};reinfer_diff"

    val_tags = parse_val_tags(card.get("validation", ""))
    narrative_tags = [t for t in val_tags if t not in _SKIP_VAL]
    val_prose = (card.get("validation_prose") or "").strip() or infer_validation_prose(
        title, text
    )
    tag_checks = {t: check_validation_tag(t, blob) for t in narrative_tags}

    false_val = [t for t, s in tag_checks.items() if s == "pdf_missing"]
    missed_val = []
    if infer_validation_prose(title, text) and not val_prose:
        missed_val.append("pdf_has_beyond_point")

    return {
        "cite_key": card["cite_key"],
        "section": card.get("section", ""),
        "doe_bucket": card.get("doe", ""),
        "doe_prose": doe_prose,
        "doe_audit": doe_status,
        "validation_t6": card.get("validation", ""),
        "validation_narrative_tags": ";".join(narrative_tags),
        "validation_prose": val_prose,
        "validation_false_positive": ";".join(false_val),
        "validation_pdf_extra": ";".join(missed_val),
        "has_pdf_text": "yes" if len(text) > 200 else "no",
    }


def main() -> int:
    pdf_paths = load_pdf_paths()
    rows: List[Dict[str, str]] = []
    with CARDS_CSV.open(encoding="utf-8", newline="") as f:
        cards = list(csv.DictReader(f))

    for card in cards:
        pdf = pdf_paths.get(card["cite_key"])
        rows.append(audit_card(card, pdf))

    fields = list(rows[0].keys()) if rows else []
    with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    summary = {
        "n_cards": len(rows),
        "doe_prose_present": sum(1 for r in rows if r["doe_prose"]),
        "doe_pdf_missing": sum(1 for r in rows if r["doe_audit"] == "pdf_missing"),
        "doe_unclassified": sum(1 for r in rows if r["doe_audit"] == "unclassified_prose"),
        "val_false_positive_rows": sum(1 for r in rows if r["validation_false_positive"]),
        "val_narrative_would_add": sum(1 for r in rows if r["validation_prose"]),
        "no_pdf_text": sum(1 for r in rows if r["has_pdf_text"] == "no"),
        "doe_missing_samples": [
            r["cite_key"] for r in rows if r["doe_audit"] == "pdf_missing"
        ][:25],
        "val_fp_samples": [
            (r["cite_key"], r["validation_false_positive"])
            for r in rows
            if r["validation_false_positive"]
        ][:25],
    }
    OUT_JSON.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"wrote {OUT_CSV.name}, {OUT_JSON.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
