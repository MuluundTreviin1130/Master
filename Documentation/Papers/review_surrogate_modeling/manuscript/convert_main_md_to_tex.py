from __future__ import annotations

import csv
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REVIEW_ROOT = ROOT.parent
PAPER_LIBRARY_BIB = REVIEW_ROOT / "paper_library" / "review_paper_library.bib"
FRONTMATTER_SOURCE = ROOT / "00_title_abstract_keywords.tex"
ABSTRACT_SOURCE = ROOT / "00_abstract.tex"
KEYWORDS_SOURCE = ROOT / "00_keywords.tex"
MD_SOURCE = ROOT / "main.md"
TEX_OUT = ROOT / "Current_manuscript.tex"
AUDIT_OUT = REVIEW_ROOT / "_tmp_main_md_citation_audit.csv"

SECTION_FILES = [
    "01_introduction.tex",
    "02_methodology.tex",
    "03_bibliometrical_analysis.tex",
    "04_conceptual_foundations.tex",
    "05_taxonomy_surrogates.tex",
    "06_meta_review.tex",
    "07_training_data_doe.tex",
    "08_integration_patterns.tex",
    "09_validation_decision_aware.tex",
    "10_application_evidence_map.tex",
    "11_software_packages.tex",
    "12_open_challenges.tex",
    "13_conclusion.tex",
]

SOFTWARE_SECTION_TEX = r"""\section{Software-packages in surrogate modeling and multi-energy systems}
\label{sec:software}

This section reports only software mentions that were found in the review PDFs
scanned by \texttt{paper\_library/verify\_T8\_software\_cites.py}. The table is
therefore a conservative mention map, not a feature comparison, package
recommendation, maintenance audit, or proof that a package was used in the
primary studies. Packages without a review-PDF mention are omitted, even if
they are widely used in practice.

\begin{table*}[!t]
\centering
\scriptsize
\caption{Software packages and environments explicitly mentioned in the review PDFs scanned for this paper. The table records mention evidence only; it does not claim package maintenance status, GPU support, license, or built-in surrogate--MES integration.}
\label{tab:T8-software-packages}
\renewcommand{\arraystretch}{1.10}
\begin{tabularx}{\textwidth}{@{}L{0.20\textwidth} L{0.18\textwidth} L{0.34\textwidth} L{0.20\textwidth}@{}}
\toprule
Package / environment & Software block & Conservative use/context from review-PDF mentions & PDF-screen evidence \\
\midrule
\texttt{ALAMO}; \texttt{Eureqa}; Surrogates Toolbox; \texttt{SUMO}; \texttt{ARGONAUT}; \texttt{scikit-learn}; R-side packages &
Surrogate / ML software &
Surrogate modelling, validation, derivative-free optimization, and general ML regression in the surrogate-methodology review context. &
Bhosekar et al. mention these packages and toolboxes \cite{Bhosekar2018}. \\
\texttt{GPML}; \texttt{GPy}; \texttt{GPflow}; \texttt{GPyTorch}; \texttt{BoTorch}; \texttt{PyMC3}; \texttt{Pyro} &
GP / probabilistic software &
Gaussian-process modelling, probabilistic programming, and Bayesian-optimization-related tooling in a GP-for-power-systems review context. &
Tan et al. mention these GP and probabilistic software packages \cite{Tan2026}. \\
\texttt{XGBoost}; \texttt{LightGBM}; \texttt{TensorFlow}; \texttt{PyTorch}; \texttt{MATLAB} &
ML / engineering environments &
Learning-assisted power-system models, building-energy or HRES surrogate contexts, digital-twin workflows, and general engineering optimization environments, depending on the review. &
PDF-screen mentions in learning-assisted power, surrogate, digital-twin, building-energy and HRES reviews \cite{Khaloie2025,Conti2026,Zhang2026_building,Lim2025,Elwy2024,Tan2026,FernandezGodino2023,Westermann2019,Li2025_hydrogen,Etghani2025}. \\
\texttt{SMT} &
Surrogate toolbox &
Surrogate-modelling toolbox mentioned in energy-related surrogate or digital-twin review contexts. &
PDF-screen mentions in Westermann et al. and Khan et al. \cite{Westermann2019,Khan2024_DT}. \\
\texttt{GAMS}; \texttt{Gurobi}; \texttt{CPLEX}; \texttt{Mosek}; \texttt{IPOPT}; \texttt{BARON} &
Modelling language / solvers &
Algebraic modelling and mathematical optimization backends in ESM, MES, power-system learning, or surrogate-optimization review contexts. This does not imply a surrogate-specific interface. &
PDF-screen mentions in ESM, MES, power-system learning and surrogate-methodology reviews \cite{Fattahi2020,Klemm2021,Manco2024,Lim2025,Khaloie2025,Westermann2019,Bhosekar2018,Mylonopoulos202332697}. \\
\texttt{PyPSA}; \texttt{oemof}; \texttt{Calliope}; \texttt{OSeMOSYS}; \texttt{TIMES}; \texttt{MARKAL}; \texttt{REMix} &
Energy-system modelling tools &
MES, district-scale, national, or long-term energy-system modelling frameworks discussed as host modelling tools. The screen does not show native surrogate interfaces. &
PDF-screen mentions in MES and national/long-term ESM reviews \cite{Klemm2021,Fattahi2020,ChenRenZhou2023}. \\
\texttt{HOMER}; \texttt{iHOGA}; \texttt{RETScreen} &
Microgrid / HRES tools &
Microgrid, hybrid-renewable-system, ship-energy, hydrogen, or broader energy-system assessment and optimization contexts. &
PDF-screen mentions in microgrid, HRES, hydrogen and broader energy-review PDFs \cite{agha_kassab_comprehensive_2024,Mylonopoulos202332697,nallolla_multi-objective_2023,velasquez_intelligence_2023,arar_tahir_scientific_2023,batista_optimizing_2023,Klemm2021,Li2025_hydrogen,ChenRenZhou2023}. \\
\texttt{EnergyPlus}; \texttt{TRNSYS}; \texttt{Modelica/Dymola} &
Simulation environments &
Building-energy, transient HVAC/renewable-system, thermal-system or multi-physics simulation contexts that can act as high-fidelity models in surrogate workflows. &
PDF-screen mentions in building-surrogate, MES-tool, HRES and thermal-system review PDFs \cite{Westermann2019,Klemm2021,Zhang2026_building,Elsheikh2019622,batista_optimizing_2023,Li2025_hydrogen,Etghani2025,Elwy2024}. \\
\bottomrule
\end{tabularx}
\end{table*}

Two cautious observations follow from this evidence. First, the review-level
software evidence is fragmented: surrogate-methodology reviews discuss
surrogate and GP software, whereas MES and HRES reviews mostly discuss
modelling environments, simulators and optimization solvers. Second, the
scanned reviews do not provide enough evidence to claim a mature,
standardized interface between surrogate libraries, multi-objective decision
workflows and energy-system modelling tools. For this reason, the open
challenge is not that a specific package is missing, but that
review-documented evidence for reproducible surrogate--MES toolchain
integration remains limited.
"""


SPLIT_CITE_REPLACEMENTS = {
    "Aghaei; @Pour2022303": "Aghaei Pour2022303",
    "De; @Castro20247710": "De Castro20247710",
    "El; @Mestari2025": "El Mestari2025",
    "Van; @Acker2022": "Van Acker2022",
}


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def load_frontmatter_tex() -> str:
    text = read_text(FRONTMATTER_SOURCE)
    match = re.search(r"\\begin\{frontmatter\}.*?\\end\{frontmatter\}", text, flags=re.S)
    if not match:
        raise RuntimeError(f"Missing frontmatter block in {FRONTMATTER_SOURCE}")
    frontmatter = match.group(0)
    end_marker = r"\end{frontmatter}"
    abstract = read_text(ABSTRACT_SOURCE).strip()
    keywords = read_text(KEYWORDS_SOURCE).strip()
    return frontmatter.replace(
        end_marker,
        f"{abstract}\n\n{keywords}\n\n{end_marker}",
    )


def load_paper_library_keys() -> set[str]:
    bib = read_text(PAPER_LIBRARY_BIB)
    return set(re.findall(r"@\w+\s*\{\s*([^,]+)", bib))


def normalize_citation_spans(md: str) -> str:
    for split_key, normalized in SPLIT_CITE_REPLACEMENTS.items():
        md = md.replace(f"@{split_key}", f"@{normalized}")
    return md


def keys_from_span(span: str) -> list[str]:
    keys = []
    for part in span.strip("[]").split(";"):
        part = part.strip()
        if "@" in part:
            keys.append(part.split("@", 1)[1].strip())
    return keys


def extract_citation_keys(md: str) -> list[str]:
    keys: list[str] = []
    for span in re.findall(r"\[[^\]]*@[^\]]*\]", md):
        keys.extend(keys_from_span(span))
    return sorted(set(keys))


def citation_audit(md: str, bib_keys: set[str]) -> None:
    with AUDIT_OUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["cite_key", "in_review_paper_library_bib"])
        writer.writeheader()
        for key in extract_citation_keys(md):
            writer.writerow({"cite_key": key, "in_review_paper_library_bib": int(key in bib_keys)})


def convert_inline(text: str) -> str:
    text = text.replace("Ã‚\xa0", "~").replace("\xa0", "~")
    text = re.sub(
        r"\[\[([^\]]+)\]\]\(#([^)]+)\)\{reference-type=\"ref\"\s+reference=\"([^\"]+)\"\}",
        lambda m: r"\ref{" + m.group(3) + "}",
        text,
    )
    text = re.sub(
        r"\[([^\]]*?)\]\(#([^)]+)\)\{reference-type=\"ref\"\s+reference=\"([^\"]+)\"\}",
        lambda m: r"\ref{" + m.group(3) + "}",
        text,
    )
    text = re.sub(r"\[([0-9]+)\]\(#([^)]+)\)", lambda m: r"\ref{" + m.group(2) + "}", text)
    text = re.sub(r"\[([^\]]*?)\]\(#([^)]+)\)", lambda m: (m.group(1) or r"\ref{" + m.group(2) + "}"), text)

    def repl_cites(match: re.Match[str]) -> str:
        keys = keys_from_span(match.group(0))
        return r"\cite{" + ",".join(keys) + "}" if keys else match.group(0)

    text = re.sub(r"\[[^\]]*@[^\]]*\]", repl_cites, text)
    text = re.sub(r"`([^`]+)`", r"\\texttt{\1}", text)
    return text


def table_spec(line: str) -> str:
    spec = line.strip().removeprefix(r"\@").removesuffix("@").strip()
    pieces = []
    for token in spec.split():
        if token.startswith(("L", "C")) and len(token) > 1:
            pieces.append(f"{token[0]}{{{token[1:]}\\textwidth}}")
        else:
            pieces.append(token)
    return "@{}" + " ".join(pieces) + "@{}"


def html_figure_to_tex(block: list[str]) -> list[str] | None:
    text = "\n".join(block)
    src_match = re.search(r"<img\s+src=\"([^\"]+)\"", text)
    if not src_match:
        return None
    caption_match = re.search(r"<figcaption>(.*?)</figcaption>", text, flags=re.S)
    id_match = re.search(r"<figure\s+id=\"([^\"]+)\"", text)
    caption = convert_inline((caption_match.group(1).strip() if caption_match else "").replace("\n", " "))
    label = id_match.group(1) if id_match else "fig:todo"
    return [
        r"\begin{figure*}[!t]",
        r"\centering",
        rf"\includegraphics[width=\textwidth]{{{src_match.group(1)}}}",
        rf"\caption{{{caption}}}",
        rf"\label{{{label}}}",
        r"\end{figure*}",
    ]


def markdown_figure_to_tex(block: list[str]) -> list[str] | None:
    text = "\n".join(block).strip()
    match = re.match(r"!\[(.*?)\]\((.*?)\)\s*(?:\{#([^}\s]+).*?\})?", text, flags=re.S)
    if not match:
        return None
    caption = convert_inline(match.group(1)).replace("\n", " ")
    return [
        r"\begin{figure*}[!t]",
        r"\centering",
        rf"\includegraphics[width=\textwidth]{{{match.group(2)}}}",
        rf"\caption{{{caption}}}",
        rf"\label{{{match.group(3) or 'fig:todo'}}}",
        r"\end{figure*}",
    ]


def cleanup_generated_tex(full_tex: str) -> str:
    full_tex = re.sub(
        r"\[([^\]]*?)\]\(#([^)]+)\)\{reference-type=\"(ref|eqref)\"\s*reference=\"([^\"]+)\"\}",
        lambda m: (r"\eqref{" if m.group(3) == "eqref" else r"\ref{") + m.group(4) + "}",
        full_tex,
        flags=re.S,
    )
    full_tex = re.sub(
        r"\[\\\[(.*?)\\\]\]\(#([^)]+)\)",
        lambda m: (r"\eqref{" if m.group(2).startswith("eq:") else r"\ref{") + m.group(2) + "}",
        full_tex,
        flags=re.S,
    )
    full_tex = re.sub(
        r"\\ref\{([^}]+)\}\{reference-type=\"ref\"\s*reference=\"([^\"]+)\"\}",
        lambda m: r"\ref{" + m.group(1) + "}",
        full_tex,
        flags=re.S,
    )
    full_tex = re.sub(r"\{reference-type=\"[^\"]+\"\s*reference=\"[^\"]+\"\}", "", full_tex, flags=re.S)
    full_tex = full_tex.replace(r"\ref{PRISMA_chart}", r"\ref{fig1}")
    full_tex = full_tex.replace(r"\ref{sec:background}", r"\ref{sec:optimization-bottlenecks}")
    return full_tex


def convert_md_to_tex(md: str) -> str:
    out: list[str] = []
    in_frontmatter = False
    in_table = False
    pending_table = False
    pending_tabular = False
    in_html_figure = False
    html_figure_block: list[str] = []
    in_markdown_figure = False
    markdown_figure_block: list[str] = []
    saw_top_section = False
    frontmatter_tex = load_frontmatter_tex()

    out.append(
        r"""\documentclass[final,5p,times,twocolumn]{elsarticle}
\usepackage{amssymb}
\usepackage{amsmath}
\usepackage{booktabs}
\usepackage{tabularx}
\usepackage{array}
\usepackage{longtable}
\usepackage{graphicx}
\usepackage[hidelinks]{hyperref}

\newcolumntype{L}[1]{>{\raggedright\arraybackslash}p{#1}}
\newcolumntype{C}[1]{>{\centering\arraybackslash}p{#1}}

\journal{Renewable and Sustainable Energy Reviews}

\begin{document}
"""
    )
    out.append(frontmatter_tex)
    out.append("")

    for raw in md.splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        if in_markdown_figure:
            markdown_figure_block.append(line)
            if stripped.endswith("}") or stripped.endswith(")"):
                figure_tex = markdown_figure_to_tex(markdown_figure_block)
                out.extend(figure_tex or markdown_figure_block)
                in_markdown_figure = False
                markdown_figure_block = []
            continue
        if in_html_figure:
            html_figure_block.append(line)
            if "</figure>" in stripped:
                figure_tex = html_figure_to_tex(html_figure_block)
                out.extend(figure_tex or html_figure_block)
                in_html_figure = False
                html_figure_block = []
            continue
        if stripped.startswith("::::") and "frontmatter" in stripped:
            in_frontmatter = True
            continue
        if in_frontmatter and stripped.startswith("::::") and "frontmatter" not in stripped:
            in_frontmatter = False
            continue
        if in_frontmatter or stripped in {":::", "::::", ":::::", "::::::", ":::::::"}:
            if in_table and stripped in {"::::", ":::::"}:
                out.append(r"\end{tabularx}")
                out.append(r"\end{table*}")
                in_table = False
            continue
        if stripped.startswith("::::") and "table*" in stripped:
            pending_table = True
            continue
        if pending_table and stripped == "::: tabularx":
            pending_tabular = True
            pending_table = False
            continue
        if pending_tabular:
            out.extend([r"\begin{table*}[!t]", r"\centering", r"\scriptsize"])
            out.append(r"\begin{tabularx}{\textwidth}{" + table_spec(stripped) + "}")
            out.append(r"\toprule")
            pending_tabular = False
            in_table = True
            continue
        if stripped.startswith("<figure"):
            in_html_figure = True
            html_figure_block = [line]
            if "</figure>" in stripped:
                figure_tex = html_figure_to_tex(html_figure_block)
                out.extend(figure_tex or html_figure_block)
                in_html_figure = False
                html_figure_block = []
            continue
        if stripped.startswith("!["):
            if ")" not in stripped or ("{" in stripped and "}" not in stripped):
                in_markdown_figure = True
                markdown_figure_block = [line]
                continue
            match = re.match(r"!\[(.*?)\]\((.*?)\)(?:\{#([^}\s]+).*?\})?", stripped)
            if match:
                out.extend(
                    [
                        r"\begin{figure*}[!t]",
                        r"\centering",
                        rf"\includegraphics[width=\textwidth]{{{match.group(2)}}}",
                        rf"\caption{{{convert_inline(match.group(1)).replace(chr(10), ' ')}}}",
                        rf"\label{{{match.group(3) or 'fig:todo'}}}",
                        r"\end{figure*}",
                    ]
                )
                continue
        heading = re.match(r"^(#{1,4})\s+(.+?)(?:\s+\{#([^}]+)\})?$", stripped)
        if heading:
            level = len(heading.group(1))
            if not saw_top_section and level == 2:
                out.extend([r"\section{Introduction}", r"\label{sec:introduction}"])
                saw_top_section = True
            command = {1: "section", 2: "subsection", 3: "subsubsection", 4: "paragraph"}[level]
            out.append(rf"\{command}{{{convert_inline(heading.group(2))}}}")
            if heading.group(3):
                out.append(rf"\label{{{heading.group(3)}}}")
            continue
        if in_table:
            if stripped == "\\":
                out.append(r"\\")
            elif stripped:
                out.append(convert_inline(line))
            continue
        out.append(convert_inline(line) if stripped else "")

    out.extend([r"\bibliographystyle{elsarticle-num}", r"\bibliography{review_paper_library}", r"\end{document}"])
    full_tex = replace_software_section("\n".join(out) + "\n")
    return cleanup_generated_tex(full_tex)


def replace_software_section(full_tex: str) -> str:
    pattern = re.compile(
        r"(?ms)^\\section\{Software-packages in surrogate modeling and multi-energy systems\}.*?(?=^\\section\{Open challenges and research directions\})"
    )
    replaced, count = pattern.subn(lambda _match: SOFTWARE_SECTION_TEX.strip() + "\n\n", full_tex)
    if count != 1:
        raise RuntimeError(f"Expected to replace one software section, replaced {count}")
    return replaced


def split_current_sections(full_tex: str) -> None:
    begin_marker = r"\end{frontmatter}"
    end_marker = r"\bibliographystyle{elsarticle-num}"
    body = full_tex.split(begin_marker, 1)[1].split(end_marker, 1)[0].strip()
    starts = [match.start() for match in re.finditer(r"(?m)^\\section\{", body)]
    sections = []
    for index, start in enumerate(starts):
        end = starts[index + 1] if index + 1 < len(starts) else len(body)
        sections.append(body[start:end].strip() + "\n")
    if len(sections) != len(SECTION_FILES):
        raise RuntimeError(f"Expected {len(SECTION_FILES)} sections, found {len(sections)}")
    for filename, section in zip(SECTION_FILES, sections):
        write_text(ROOT / filename, section)


def main() -> None:
    bib_keys = load_paper_library_keys()
    md = normalize_citation_spans(read_text(MD_SOURCE))
    citation_audit(md, bib_keys)
    full_tex = convert_md_to_tex(md)
    write_text(TEX_OUT, full_tex)
    split_current_sections(full_tex)
    missing = [key for key in extract_citation_keys(md) if key not in bib_keys]
    print(f"wrote {TEX_OUT}")
    print(f"wrote {len(SECTION_FILES)} section files")
    print(f"wrote {AUDIT_OUT}")
    print(f"citation_keys={len(extract_citation_keys(md))}")
    print(f"missing_in_review_paper_library_bib={len(missing)}")
    for key in missing:
        print(key)


if __name__ == "__main__":
    main()
