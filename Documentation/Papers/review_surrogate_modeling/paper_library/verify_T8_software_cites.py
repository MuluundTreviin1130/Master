"""Verify the cite tags in tables/table_T8_software_packages.tex
against the actual review-paper PDFs in paper_library/fulltexts/.

For each (package, alias-list) pair in PACKAGES, the script extracts
the text of every PDF and reports which PDFs explicitly mention the
package (case-insensitive whole-word for short tokens, substring for
long unambiguous tokens).

The mapping PDF-filename -> cite-key is taken from the README in
paper_library/fulltexts/. For each package the script then prints
the cite-keys whose source PDFs mention the package, so the table
T8 cite-tags can be replaced 1:1 with what is actually documented.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple

ROOT = Path(__file__).resolve().parents[1]
FULLTEXTS = Path(__file__).resolve().parent / "fulltexts"


# Mapping cite-key -> PDF filename (kept in sync with fulltexts/README.md).
# Files for the 17 originally-T7 reviews use the original ScienceDirect
# names; the 14 externally-supplied PDFs use the ASCII names we copied
# them under.
CITE_TO_PDF = {
    # original Scopus T7 set (17 reviews, file names mirror ScienceDirect IDs)
    "vahidinasab_overview_2020": "vahidinasab_overview_2020.pdf",
    "Elsheikh2019622": "Elsheikh2019622.pdf",
    "Khaloie2025": "Khaloie2025.pdf",
    "Tan2026": "Tan2026.pdf",
    "Zhou2024__2": "Zhou2024__2.pdf",
    "agha_kassab_comprehensive_2024": "agha_kassab_comprehensive_2024.pdf",
    "Mylonopoulos202332697": "Mylonopoulos202332697.pdf",
    "malla_sg_optimization_2024": "malla_sg_optimization_2024.pdf",
    "nallolla_multi-objective_2023": "nallolla_multi-objective_2023.pdf",
    "velasquez_intelligence_2023": "velasquez_intelligence_2023.pdf",
    "Lim2025": "Lim2025.pdf",
    "Conti2026": "Conti2026.pdf",
    "salgueiro_multi-objective_2019": "salgueiro_multi-objective_2019.pdf",
    "Ruan2021221": "Ruan2021221.pdf",
    "Starke2025214": None,        # PDF not in the user's folder
    "arar_tahir_scientific_2023": "main_unknown1.pdf",
    "batista_optimizing_2023": "main_unknown2.pdf",
    # 15 externally-supplied reviews
    "Bhosekar2018": "Bhosekar2018.pdf",
    "Westermann2019": "Westermann2019.pdf",
    "Manco2024": "Manco2024.pdf",
    "Fattahi2020": "Fattahi2020.pdf",
    "Klemm2021": "Klemm2021.pdf",
    "Li2025_hydrogen": "Li2025_hydrogen.pdf",
    "Khan2024_DT": "Khan2024_DT.pdf",
    "DiazManriquez2016": "DiazManriquez2016.pdf",
    "FernandezGodino2023": "FernandezGodino2016.pdf",
    "Sahoo2025": "Sahoo2025.pdf",
    "Etghani2025": "TSP_EE_70668.pdf",
    "Mohammadi2024": "Sustainability2024.pdf",
    "ChenRenZhou2023": "Ruan2021221_alt.pdf",
    "Elwy2024": "main_unknown3.pdf",
    "Zhang2026_building": "S0378778826002987.pdf",
}


# (package label in T8, list of regex patterns to match in PDF text)
# Patterns are intentionally strict: short alphanumeric tokens use word
# boundaries; multi-word names match case-insensitively.
PACKAGES: List[Tuple[str, List[str]]] = [
    ("scikit-learn",      [r"\bscikit-learn\b", r"\bsklearn\b"]),
    ("XGBoost",           [r"\bXGBoost\b"]),
    ("LightGBM",          [r"\bLightGBM\b"]),
    ("TensorFlow",        [r"\bTensorFlow\b"]),
    ("PyTorch",           [r"\bPyTorch\b"]),
    ("Keras",             [r"\bKeras\b"]),
    ("JAX",               [r"\bJAX\b"]),
    ("SMT",               [r"\bSMT\b", r"Surrogate Modeling Toolbox"]),
    ("GPy",               [r"\bGPy\b(?!Torch)"]),
    ("GPyTorch",          [r"\bGPyTorch\b"]),
    ("botorch",           [r"\bbotorch\b", r"BoTorch"]),
    ("scikit-optimize",   [r"\bscikit-optimize\b", r"\bskopt\b"]),
    ("emukit",            [r"\bemukit\b"]),
    ("chaospy",           [r"\bchaospy\b"]),
    ("OpenTURNS",         [r"\bOpenTURNS\b"]),
    ("SALib",             [r"\bSALib\b"]),
    ("Modulus",           [r"\bNVIDIA Modulus\b", r"\bModulus\b"]),
    ("DeepXDE",           [r"\bDeepXDE\b"]),
    ("pymoo",             [r"\bpymoo\b"]),
    ("DEAP",              [r"\bDEAP\b"]),
    ("PyGMO",             [r"\bPyGMO\b", r"\bpagmo\b"]),
    ("Platypus",          [r"\bPlatypus\b"]),
    ("pyDecision",        [r"\bpyDecision\b"]),
    ("Pyomo",             [r"\bPyomo\b"]),
    ("JuMP",              [r"\bJuMP\b"]),
    ("CVXPY",             [r"\bCVXPY\b"]),
    ("GAMS",              [r"\bGAMS\b"]),
    ("AMPL",              [r"\bAMPL\b"]),
    ("Gurobi",            [r"\bGurobi\b"]),
    ("CPLEX",             [r"\bCPLEX\b"]),
    ("Mosek",             [r"\bMosek\b"]),
    ("IPOPT",             [r"\bIPOPT\b"]),
    ("BARON",             [r"\bBARON\b"]),
    ("Couenne",           [r"\bCouenne\b"]),
    ("PyPSA",             [r"\bPyPSA\b"]),
    ("oemof",             [r"\boemof\b"]),
    ("Calliope",          [r"\bCalliope\b"]),
    ("OSeMOSYS",          [r"\bOSeMOSYS\b"]),
    ("HOMER",             [r"\bHOMER\b"]),
    # "TIMES" alone matches the English word; require context that
    # disambiguates it as the IEA-ETSAP energy-system model.
    ("TIMES",             [
        r"\bIEA[-\s]TIMES\b",
        r"\bTIMES\s+(?:model|framework|tool|simulation|family|generator|database|Austria|Italy|Norway|Global|Italy|EU|UK|MARKAL|/)",
        r"\bMARKAL[-/\s]TIMES\b",
        r"TIMES-(?:Austria|Italy|UK|EU|Global|Norway)",
    ]),
    ("MARKAL",            [r"\bMARKAL\b"]),
    ("REMix",             [r"\bREMix\b"]),
    ("GenX",              [r"\bGenX\b"]),
    ("PowerModels.jl",    [r"\bPowerModels\.jl\b", r"\bPowerModels\b"]),
    ("EnergyPlus",        [r"\bEnergyPlus\b"]),
    ("TRNSYS",            [r"\bTRNSYS\b"]),
    ("Modelica/Dymola",   [r"\bModelica\b", r"\bDymola\b"]),
    ("MATLAB",            [r"\bMATLAB\b"]),
]


def extract_text(pdf: Path) -> str:
    """Extract plain text from a PDF in-process.

    PyMuPDF (``fitz``) handles the broadest set of scientific PDFs;
    ``pypdf`` is the fallback. Running in-process avoids the Windows
    cp1252 stdout-encoding problem we hit when piping through a
    subprocess.
    """

    if not pdf.exists():
        return ""
    try:
        import fitz  # PyMuPDF

        with fitz.open(str(pdf)) as doc:
            return "\n".join(page.get_text() for page in doc)
    except Exception:
        try:
            from pypdf import PdfReader

            r = PdfReader(str(pdf))
            return "\n".join((p.extract_text() or "") for p in r.pages)
        except Exception:
            return ""


def main() -> None:
    out_path = Path(__file__).with_suffix(".out.txt")
    lines: List[str] = []
    cache: dict[str, str] = {}
    for cite, fname in CITE_TO_PDF.items():
        if fname is None:
            lines.append(f"[skip] {cite:<35} no PDF on disk")
            continue
        path = FULLTEXTS / fname
        text = extract_text(path)
        cache[cite] = text
        lines.append(f"[load] {cite:<35} {len(text):>7} chars  ({fname})")
    lines.append("")

    rows = []
    for label, patterns in PACKAGES:
        compiled = [re.compile(p, re.IGNORECASE) for p in patterns]
        hits: List[str] = []
        for cite, text in cache.items():
            if not text:
                continue
            for cp in compiled:
                if cp.search(text):
                    hits.append(cite)
                    break
        rows.append((label, hits))

    lines.append(f"{'Package':<22} | hits | cite-keys")
    lines.append("-" * 80)
    for label, hits in rows:
        cites = ", ".join(hits) if hits else "(no PDF mentions found)"
        lines.append(f"{label:<22} | {len(hits):>4} | {cites}")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
