"""Inline every table reference inside the section files under
``manuscript/`` with the literal contents of the corresponding
``tables/<name>.tex`` file.

Background:  Overleaf's compiler does not handle
``\\input{../tables/...}`` paths reliably when the user pastes a
single section body into the single-file Overleaf template
(``main_overleaf_rser.tex``). Inlining the tables makes every
section file self-contained and Overleaf-pastable.

This script is **idempotent**: it can be re-run safely after a
table rebuild. Each inlined region is delimited by

    % BEGIN inlined table <name>
    ... table body ...
    % END inlined table <name>

so that subsequent runs simply re-fill the body between the markers
with the current ``tables/<name>.tex`` content. Lines that still
look like ``\\input{../tables/<name>}`` (i.e. that have not yet been
inlined at all) are converted to a BEGIN/END region on first run.

Re-run after rebuilding any auto-generated table file
(``tables/build_table_T6_evidence_map.py``,
``tables/build_table_T8_software_packages.py``).
"""
from __future__ import annotations

import re
from pathlib import Path

# ``__file__`` lives in ``tables/`` so the paper root is one level up.
ROOT = Path(__file__).resolve().parents[1]
MAN = ROOT / "manuscript"
TBL = ROOT / "tables"

# Group 1 = leading whitespace, group 2 = table name.
INPUT_RE = re.compile(
    r"^([ \t]*)\\input\{\.\./tables/([^}]+)\}[ \t]*\n?",
    re.MULTILINE,
)

# Group 1 = leading whitespace, group 2 = table name. The body
# between markers is matched non-greedily.
BEGIN_END_RE = re.compile(
    r"^([ \t]*)% BEGIN inlined table ([^\n]+)\n"
    r".*?"
    r"^[ \t]*% END inlined table \2\n",
    re.MULTILINE | re.DOTALL,
)


def _strip_table_header_comments(body: str) -> str:
    """Drop the leading ``%``-comment block from a table file so the
    inlined region stays compact. Preserves the actual LaTeX content.
    """

    out: list[str] = []
    in_header = True
    for line in body.splitlines():
        if in_header and (line.startswith("%") or line.strip() == ""):
            continue
        in_header = False
        out.append(line)
    return "\n".join(out).rstrip()


def _render(name: str, indent: str) -> str:
    target = TBL / f"{name}.tex"
    if not target.exists():
        raise FileNotFoundError(f"missing referenced table {target}")
    body = _strip_table_header_comments(target.read_text(encoding="utf-8"))
    if indent:
        body = "\n".join(indent + ln if ln else ln for ln in body.splitlines())
    return (
        f"{indent}% BEGIN inlined table {name}\n"
        f"{body}\n"
        f"{indent}% END inlined table {name}\n"
    )


def inline_one(path: Path) -> tuple[int, int]:
    """Return (n_input_replaced, n_blocks_resynced)."""

    text = path.read_text(encoding="utf-8")

    n_blocks = 0

    def repl_block(match: re.Match) -> str:
        nonlocal n_blocks
        n_blocks += 1
        return _render(match.group(2), match.group(1))

    text = BEGIN_END_RE.sub(repl_block, text)

    n_inputs = len(INPUT_RE.findall(text))

    def repl_input(match: re.Match) -> str:
        return _render(match.group(2), match.group(1))

    text = INPUT_RE.sub(repl_input, text)

    path.write_text(text, encoding="utf-8")
    return n_inputs, n_blocks


def main() -> None:
    total_inputs = 0
    total_blocks = 0
    for tex in sorted(MAN.glob("*.tex")):
        n_in, n_bl = inline_one(tex)
        if n_in or n_bl:
            print(
                f"{tex.name:<40} inputs={n_in} blocks_resynced={n_bl}"
            )
        total_inputs += n_in
        total_blocks += n_bl
    print(
        f"\ndone. {total_inputs} \\input replacements, "
        f"{total_blocks} BEGIN/END blocks resynced."
    )


if __name__ == "__main__":
    main()
