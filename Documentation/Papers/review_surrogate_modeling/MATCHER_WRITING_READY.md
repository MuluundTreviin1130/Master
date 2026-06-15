# Literatur-Matcher: Schreib-Readiness (lokaler Stand)

Letzter Lauf: 2026-05-14, Befehl aus `review_surrogate_modeling`:

`py -3 paper_library/match_literatur_pdfs_to_bib.py`

## Kennzahlen (Ausgabe `_tmp_pdf_author_title_match_report.json` / Konsole)

| Kennzahl | Wert |
| -------- | ---- |
| PDFs im Literatur-Baum | 320 |
| Zitierte Keys (Manuskript + `tables/*.tex`) | 285 |
| Verifizierte DOI-Zuordnungen | 283 |
| Verifizierte section-fuzzy | 11 |
| `unmatched` (PDF ohne sichere Bib-Zeile) | 24 |
| `matched_ambiguous` (echte DOI-Kollision, nicht auflösbar) | 2 |
| Keys mit **mehreren** verifizierten PDFs (`key_collisions`) | 81 |
| Zitierte Keys **ohne** verifiziertes PDF | 120 |
| Keys fehlen in der gemergten Bib | 0 |

**Hinweis:** „120 ohne PDF“ betrifft das Zitationsuniversum; viele Keys sind nie als Datei im `Literatur/`-Ordner vorhanden oder liegen unter anderem Dateinamen ohne Treffer.

## Verbleibende `matched_ambiguous` (manuell prüfen)

1. `Other/1-s2.0-S2666955226000213-main.pdf` — `doi_collision` u. a. Jahangiri2023, Jahangiri20244849, Prina2024, …; vermutlich **Sammelband/Kapitel-PDF** mit vielen Literatur-DOIs.
2. `Reviews/A. Khan - Digital Twin and Artificial Intelligence Incorporated With Surrogate Modeling for Hybrid and Sustainable Energy Systems .pdf` — Kollision Perera2017187, Sun2018, Sun20191497.

## Nächste Schritte fürs genaue Zitieren im Text

- Für die **81** Multi-PDF-Keys: in `_tmp_manuscript_cite_pdf_coverage.csv` Spalte `multiple_pdf_collision=yes` filtern und pro Key **eine** Kanon-Datei festlegen (Archiv-Duplikate aus `Other/` etc.).
- **24** `unmatched`: fehlender Download, falscher Ordner, oder Scan/Metadaten — gezielt nach DOI im PDF suchen und ggf. Bib-Eintrag prüfen.
- Die **2** Ambiguous-Fälle nur nach manueller Sichtung zuordnen; nicht raten.

Kein Eintrag im globalen `Documentation/worklog.md` (Review-themenspezifisch).
