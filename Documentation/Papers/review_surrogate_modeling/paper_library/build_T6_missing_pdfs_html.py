"""Build clickable HTML table of T6 entries missing a PDF."""
from __future__ import annotations

import csv
import html
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "paper_library" / "review_paper_library_manifest.csv"
MISSING_CSV = ROOT / "_tmp_T6_compact_pdf_missing.csv"
OUT_HTML = ROOT / "paper_library" / "T6_missing_pdfs_download.html"


def main() -> None:
    manifest: dict[str, dict[str, str]] = {}
    with MANIFEST.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            manifest[row["cite_key"]] = row

    rows: list[dict[str, str | int]] = []
    with MISSING_CSV.open(encoding="utf-8", newline="") as f:
        for raw in csv.DictReader(f):
            m = manifest.get(raw["cite_key"], raw)
            cite = int(m["cited_by_count"]) if str(m.get("cited_by_count", "")).isdigit() else 0
            doi = (raw.get("doi") or m.get("doi") or "").strip()
            rows.append(
                {
                    "key": raw["cite_key"],
                    "year": raw.get("year") or m.get("year", ""),
                    "cite": cite,
                    "doi": doi,
                    "title": (raw.get("title") or m.get("title") or "")[:220],
                    "topic": (m.get("primary_topic") or "")[:90],
                }
            )
    rows.sort(key=lambda x: (-int(x["cite"]), str(x["key"])))

    body_rows: list[str] = []
    for i, r in enumerate(rows, 1):
        doi = str(r["doi"])
        link = f"https://doi.org/{doi}" if doi else ""
        doi_cell = (
            f'<a href="{html.escape(link)}" target="_blank" rel="noopener">'
            f"{html.escape(doi)}</a>"
            if link
            else "—"
        )
        tr_class = ' class="prio"' if int(r["cite"]) >= 10 else ""
        body_rows.append(
            f"<tr{tr_class}><td>{i}</td><td><code>{html.escape(str(r['key']))}</code></td>"
            f"<td>{html.escape(str(r['year']))}</td><td class=\"num\">{r['cite']}</td>"
            f"<td>{doi_cell}</td><td class=\"title\">{html.escape(str(r['title']))}</td>"
            f"<td class=\"topic\">{html.escape(str(r['topic']))}</td></tr>"
        )

    n = len(rows)
    doc = f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>T6 — fehlende PDFs ({n})</title>
<style>
  :root {{ font-family: "Segoe UI", system-ui, sans-serif; font-size: 14px; }}
  body {{ max-width: 1280px; margin: 2rem auto; padding: 0 1rem; color: #1a1a1a; }}
  h1 {{ font-size: 1.4rem; font-weight: 600; }}
  p.meta {{ color: #555; margin-bottom: 1.5rem; line-height: 1.5; }}
  table {{ width: 100%; border-collapse: collapse; box-shadow: 0 1px 4px rgba(0,0,0,.1); }}
  th {{ background: #1e3a5f; color: #fff; text-align: left; padding: 10px 12px; position: sticky; top: 0; z-index: 1; }}
  td {{ padding: 8px 12px; border-bottom: 1px solid #e8e8e8; vertical-align: top; }}
  tr.prio td {{ background: #fffde7; }}
  tr:hover td {{ background: #e8f0fa !important; }}
  .num {{ text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }}
  .title {{ max-width: 380px; line-height: 1.35; }}
  .topic {{ max-width: 220px; font-size: 12px; color: #444; }}
  a {{ color: #1565c0; font-weight: 500; }}
  a:hover {{ text-decoration: underline; }}
  code {{ font-size: 12px; background: #f0f0f0; padding: 2px 5px; border-radius: 3px; }}
</style>
</head>
<body>
<h1>Fehlende PDFs — T6 Evidence Map</h1>
<p class="meta"><strong>{n}</strong> Einträge ohne PDF in <code>Literatur/</code>.
Zeilen mit Cit.&nbsp;≥&nbsp;10 sind gelb markiert.
Klick auf die DOI-Spalte öffnet den Publisher über <a href="https://doi.org/">doi.org</a>.</p>
<table>
<thead><tr>
<th>#</th><th>cite_key</th><th>Jahr</th><th>Cit.</th><th>DOI (Download)</th><th>Titel</th><th>Topic (OpenAlex)</th>
</tr></thead>
<tbody>
{chr(10).join(body_rows)}
</tbody>
</table>
</body>
</html>"""
    OUT_HTML.write_text(doc, encoding="utf-8")
    print(OUT_HTML)


if __name__ == "__main__":
    main()
