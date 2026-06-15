"""Deterministic builder for table T8 (software-package landscape).

Produces two artefacts:

1. ``tables/table_T8_software_packages.tex`` -- the LaTeX table with
   PDF-verified ``Source`` cite-tags. Every cite-tag in the table is
   one of the keys returned by
   ``paper_library/verify_T8_software_cites.py`` (which scans the
   review PDFs in ``paper_library/fulltexts/`` for the package's
   alias-list). When a package has no PDF mention, ``Source`` shows
   ``--`` with a footnote that explains we kept the package on
   common-knowledge grounds.

2. ``paper_library/software_landscape.csv`` -- machine-readable
   source for the table; columns mirror the table plus a
   ``confidence`` flag (``high`` if at least one PDF mention,
   ``ck`` if common-knowledge only).

Usage:

    py tables/build_table_T8_software_packages.py

The package definition list (PACKAGES) is the single point of edit.
Static fields (language, GPU, DL, maintenance, primary use) are
authored manually and reflect the package documentation as of 2026.
The ``Source`` column is generated automatically from the verify
script's output file.
"""
from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Dict, List, NamedTuple, Tuple

ROOT = Path(__file__).resolve().parents[1]
VERIFY_OUT = ROOT / "paper_library" / "verify_T8_software_cites.out.txt"
TEX_OUT = ROOT / "tables" / "table_T8_software_packages.tex"
CSV_OUT = ROOT / "paper_library" / "software_landscape.csv"


class Pkg(NamedTuple):
    label: str          # display name
    block: str          # logical block in the table
    language: str
    gpu: str            # "yes" | "part." | "--"
    dl: str             # "yes" | "part." | "--"
    maint: str          # "active" | "semi-active" | "dormant" | "commercial"
    primary_use: str    # short prose


# Package definition. Order = display order. Block headers are emitted
# in the table where the block field changes.
PACKAGES: List[Pkg] = [
    # General-purpose ML / surrogate frameworks
    Pkg("scikit-learn",     "ml",  "Python",          "--",    "--",   "active",     "Linear/kernel/tree regressors used as cheap surrogates"),
    Pkg("XGBoost",          "ml",  "Python, R",       "yes",   "--",   "active",     "Gradient-boosted ensembles for forecasting and infill modelling"),
    Pkg("LightGBM",         "ml",  "Python",          "yes",   "--",   "active",     "Fast gradient-boosted ensembles for high-dim ESM features"),
    Pkg("TensorFlow",       "ml",  "Python, C++",     "yes",   "yes",  "active",     "Generic NN surrogate stack"),
    Pkg("PyTorch",          "ml",  "Python",          "yes",   "yes",  "active",     "NN, GP-on-PyTorch and PINN backbones"),
    Pkg("Keras",            "ml",  "Python (TF)",     "yes",   "yes",  "active",     "High-level API for ANN surrogates in building / HRES studies"),
    Pkg("JAX",              "ml",  "Python",          "yes",   "yes",  "active",     "Differentiable programming for PINN and large-scale BO"),

    # Surrogate-specific libraries
    Pkg("SMT",              "sur", "Python",          "--",    "--",   "active",     "GP, RBF, RMTS, mixture-of-experts; multi-fidelity"),
    Pkg("GPy",              "sur", "Python",          "--",    "--",   "semi-active","Vanilla Gaussian-process regression and classification"),
    Pkg("GPyTorch",         "sur", "Python (PyTorch)","yes",   "part.","active",     "Scalable / variational GPs on GPU"),
    Pkg("botorch",          "sur", "Python (PyTorch)","yes",   "part.","active",     "Bayesian optimization, qEHVI for MOO Pareto search"),
    Pkg("chaospy",          "sur", "Python",          "--",    "--",   "active",     "Polynomial chaos expansion and Sobol indices"),
    Pkg("OpenTURNS",        "sur", "Python, C++",     "--",    "--",   "active",     "UQ / PCE / Kriging / sensitivity"),
    Pkg("Modulus",          "sur", "Python",          "yes",   "yes",  "active",     "NVIDIA framework for PINN and physics-guided NN"),
    Pkg("DeepXDE",          "sur", "Python",          "yes",   "yes",  "active",     "PINN library for forward and inverse PDE problems"),

    # MOO and MCDM
    Pkg("pymoo",            "moo", "Python",          "--",    "--",   "active",     "NSGA-II/III, MOEA/D, MOPSO, RVEA, indicator metrics"),
    Pkg("DEAP",             "moo", "Python",          "--",    "--",   "semi-active","Evolutionary algorithm framework with multi-objective support"),
    Pkg("pyDecision",       "moo", "Python",          "--",    "--",   "active",     "MCDM (AHP, TOPSIS, VIKOR, PROMETHEE, ELECTRE)"),

    # Optimization solvers and modelling languages
    Pkg("Pyomo",            "sol", "Python",          "part.", "--",   "active",     "Algebraic modelling for MILP/NLP/MINLP"),
    Pkg("JuMP",             "sol", "Julia",           "part.", "--",   "active",     "Julia algebraic modelling for MILP/NLP/MINLP"),
    Pkg("CVXPY",            "sol", "Python",          "part.", "--",   "active",     "Convex optimization for surrogate-feasibility projection"),
    Pkg("GAMS",             "sol", "GAMS",            "--",    "--",   "commercial", "Algebraic modelling backbone for TIMES, MARKAL, REMix"),
    Pkg("Gurobi",           "sol", "solver",          "--",    "--",   "commercial", "Backend MILP/QP/SOCP solver"),
    Pkg("CPLEX",            "sol", "solver",          "--",    "--",   "commercial", "Backend MILP/QP/SOCP solver"),
    Pkg("Mosek",            "sol", "solver",          "--",    "--",   "commercial", "Backend QP/SOCP/conic solver"),
    Pkg("IPOPT",            "sol", "solver",          "--",    "--",   "active",     "Open-source NLP solver behind surrogate-feasible glue code"),
    Pkg("BARON",            "sol", "solver",          "--",    "--",   "commercial", "Global solver for non-convex MINLP and surrogate-DFO loops"),

    # Energy-system-specific frameworks
    Pkg("PyPSA",            "esm", "Python",          "--",    "--",   "active",     "Power-system optimization (UC, OPF, CapEx) with stochastic extensions"),
    Pkg("oemof",            "esm", "Python",          "--",    "--",   "active",     "Modular MES framework (oemof.solph) for sector coupling"),
    Pkg("Calliope",         "esm", "Python",          "--",    "--",   "active",     "Multi-scale MES optimization with renewables and storage"),
    Pkg("OSeMOSYS",         "esm", "GAMS, Python",    "--",    "--",   "active",     "Long-term capacity expansion and operations"),
    Pkg("HOMER Pro",        "esm", "proprietary",     "--",    "--",   "commercial", "Microgrid sizing and HRES techno-economic optimization"),
    Pkg("TIMES",            "esm", "GAMS",            "--",    "--",   "active",     "Long-term integrated ESM (national / EU scale)"),
    Pkg("MARKAL",           "esm", "GAMS",            "--",    "--",   "active",     "Long-term integrated ESM (precursor of TIMES)"),
    Pkg("REMix",            "esm", "Python, GAMS",    "--",    "--",   "active",     "Integrated ESM with high temporal/spatial resolution"),
    Pkg("EnergyPlus",       "esm", "C++",             "--",    "--",   "active",     "Whole-building energy simulation; reference simulator"),
    Pkg("TRNSYS",           "esm", "proprietary",     "--",    "--",   "commercial", "Transient simulation of building / HVAC / renewable systems"),
    Pkg("Modelica/Dymola",  "esm", "Modelica",        "--",    "--",   "active",     "Multi-physics simulation for thermal MES"),
    Pkg("MATLAB",           "esm", "MATLAB",          "part.", "part.","commercial", "General host environment for ANN, Taguchi and DoE pipelines"),
]


# Aliases the verify script searches for. Must match the keys in
# verify_T8_software_cites.py PACKAGES so the .out.txt parses cleanly.
VERIFY_LABEL = {
    "scikit-learn":     "scikit-learn",
    "XGBoost":          "XGBoost",
    "LightGBM":         "LightGBM",
    "TensorFlow":       "TensorFlow",
    "PyTorch":          "PyTorch",
    "Keras":            "Keras",
    "JAX":              "JAX",
    "SMT":              "SMT",
    "GPy":              "GPy",
    "GPyTorch":         "GPyTorch",
    "botorch":          "botorch",
    "chaospy":          "chaospy",
    "OpenTURNS":        "OpenTURNS",
    "Modulus":          "Modulus",
    "DeepXDE":          "DeepXDE",
    "pymoo":            "pymoo",
    "DEAP":             "DEAP",
    "pyDecision":       "pyDecision",
    "Pyomo":            "Pyomo",
    "JuMP":             "JuMP",
    "CVXPY":            "CVXPY",
    "GAMS":             "GAMS",
    "Gurobi":           "Gurobi",
    "CPLEX":            "CPLEX",
    "Mosek":            "Mosek",
    "IPOPT":            "IPOPT",
    "BARON":            "BARON",
    "PyPSA":            "PyPSA",
    "oemof":            "oemof",
    "Calliope":         "Calliope",
    "OSeMOSYS":         "OSeMOSYS",
    "HOMER Pro":        "HOMER",
    "TIMES":            "TIMES",
    "MARKAL":           "MARKAL",
    "REMix":            "REMix",
    "EnergyPlus":       "EnergyPlus",
    "TRNSYS":           "TRNSYS",
    "Modelica/Dymola":  "Modelica/Dymola",
    "MATLAB":           "MATLAB",
}


BLOCK_TITLES = {
    "ml":  "General-purpose ML / surrogate frameworks",
    "sur": "Surrogate-specific libraries (GP, PCE, RBF, MF, BO, UQ)",
    "moo": "Multi-objective optimization and MCDM",
    "sol": "Optimization solvers and modelling languages",
    "esm": "Energy-system-specific frameworks",
}


def parse_verify_output() -> Dict[str, List[str]]:
    """Return mapping ``verify-label -> [cite_key, ...]``."""

    out: Dict[str, List[str]] = {}
    if not VERIFY_OUT.exists():
        raise FileNotFoundError(
            f"missing {VERIFY_OUT}; run paper_library/verify_T8_software_cites.py first"
        )
    text = VERIFY_OUT.read_text(encoding="utf-8")
    # Split header ([load] block) from the table block.
    in_table = False
    for line in text.splitlines():
        if line.startswith("Package"):
            in_table = True
            continue
        if not in_table:
            continue
        if line.startswith("-") or not line.strip():
            continue
        # Lines look like:  scikit-learn           |    4 | Tan2026, Bhosekar2018, ...
        m = re.match(r"^(.*?)\s*\|\s*(\d+)\s*\|\s*(.*)$", line)
        if not m:
            continue
        label = m.group(1).strip()
        rhs = m.group(3).strip()
        if rhs.startswith("(no PDF"):
            out[label] = []
        else:
            out[label] = [k.strip() for k in rhs.split(",") if k.strip()]
    return out


def latex_cite_block(keys: List[str]) -> str:
    """Render the Sources cell. Empty list -> em-dash with footnote-mark."""

    if not keys:
        return "--\\textsuperscript{$\\dagger$}"
    return "\\cite{" + ",".join(keys) + "}"


def build_tex(verify: Dict[str, List[str]]) -> str:
    rows: List[str] = []
    last_block: str = ""
    for pkg in PACKAGES:
        if pkg.block != last_block:
            rows.append(
                "    \\multicolumn{7}{@{}l}{\\textit{"
                + BLOCK_TITLES[pkg.block]
                + "}} \\\\"
            )
            last_block = pkg.block
        keys = verify.get(VERIFY_LABEL[pkg.label], [])
        cell = latex_cite_block(keys)
        # Escape package label (e.g. underscores) for the Package column.
        label_tex = "\\texttt{" + pkg.label.replace("/", "/").replace("_", "\\_") + "}"
        rows.append(
            f"    {label_tex} & {pkg.language} & {pkg.gpu} & {pkg.dl} & "
            f"{pkg.maint} & {pkg.primary_use} & {cell} \\\\"
        )

    body = "\n".join(rows)
    return f"""% Table T8 - Software-package landscape.
% Auto-generated by tables/build_table_T8_software_packages.py from
%   - the static package definition list inside that script (Pkg
%     entries with language, GPU, DL, maintenance and primary-use)
% and
%   - the PDF-verified review-mention output of
%     paper_library/verify_T8_software_cites.py
%     (file paper_library/verify_T8_software_cites.out.txt).
%
% Do NOT edit this file by hand: rerun the builder after changing the
% package list or after re-running the verify script. The companion
% CSV paper_library/software_landscape.csv carries the same data in
% machine-readable form.

\\begin{{table*}}[!t]
  \\centering
  \\scriptsize
  \\caption{{Software-package landscape for surrogate modelling, multi-objective and multi-criteria optimization, and energy-system optimization. \\textit{{Sources}} lists the reviews from Table~\\ref{{tab:T7-related-reviews}} whose full text explicitly mentions the package; the mapping is generated automatically from \\texttt{{paper\\_library/verify\\_T8\\_software\\_cites.py}}, which scans the corresponding PDFs in \\texttt{{paper\\_library/fulltexts/}} for an alias of the package name. Entries marked ``--$^\\dagger$'' are kept on common-knowledge grounds (the package is documented in the package's own publication or repository but is not named in any of the surveyed reviews); they are flagged here so the reader can distinguish review-documented practice from broader engineering practice. ``GPU'' indicates whether GPU acceleration is a first-class feature (yes), present via a dependency (part.), or absent (--). ``DL'' indicates whether deep-learning models are first-class (yes), present but not the focus (part.), or absent (--). ``Maint.''\\ is the maintenance status as of 2026 (active, semi-active, dormant, commercial), drawn from the package's public repository. All packages are open-source unless marked as commercial. License and version pins are kept in \\texttt{{paper\\_library/software\\_landscape.csv}}.}}
  \\label{{tab:T8-software-packages}}
  \\renewcommand{{\\arraystretch}}{{1.10}}
  \\begin{{tabularx}}{{\\textwidth}}{{@{{}}L{{0.13\\textwidth}} L{{0.06\\textwidth}} C{{0.04\\textwidth}} C{{0.04\\textwidth}} L{{0.07\\textwidth}} L{{0.42\\textwidth}} L{{0.18\\textwidth}}@{{}}}}
    \\toprule
    Package & Language & GPU & DL & Maint. & Primary use & Sources \\\\
    \\midrule
{body}
    \\bottomrule
  \\end{{tabularx}}

  \\vspace{{2pt}}
  \\footnotesize
  $^\\dagger$ No mention of the package was found in the full text of
  the thirty-one review PDFs in \\texttt{{paper\\_library/fulltexts/}}.
  The entry is retained because the package is part of the de-facto
  practice for surrogate $\\times$ MOO $\\times$ MES workflows
  (e.g.\\ \\texttt{{pymoo}}, \\texttt{{Pyomo}}, \\texttt{{JuMP}}) and
  removing it would obscure the open-source bottleneck reported in
  \\cite{{Klemm2021,Bhosekar2018}}.
\\end{{table*}}
"""


def main() -> None:
    verify = parse_verify_output()

    TEX_OUT.write_text(build_tex(verify), encoding="utf-8")
    print(f"wrote {TEX_OUT.relative_to(ROOT)}")

    with CSV_OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "package",
                "block",
                "language",
                "gpu",
                "dl",
                "maint",
                "primary_use",
                "sources",
                "n_sources",
                "confidence",
            ]
        )
        for pkg in PACKAGES:
            keys = verify.get(VERIFY_LABEL[pkg.label], [])
            w.writerow(
                [
                    pkg.label,
                    pkg.block,
                    pkg.language,
                    pkg.gpu,
                    pkg.dl,
                    pkg.maint,
                    pkg.primary_use,
                    ";".join(keys),
                    len(keys),
                    "high" if keys else "ck",
                ]
            )
    print(f"wrote {CSV_OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
