# Match PDF ↔ Zitationen (vier Kern-Sections)

Diese Notiz bezieht sich auf die vier Manuskript-Dateien, die im Matcher fest mit `Literatur/`-Ordnern verknüpft sind:

| Manuskript | Literatur-Unterordner (Matcher) |
| ---------- | ------------------------------- |
| `manuscript/02_related_reviews.tex` | Reviews |
| `manuscript/04_taxonomy_surrogates.tex` | Taxonomy |
| `manuscript/05_training_data_doe.tex` | Training and DoE |
| `manuscript/06_integration_patterns.tex` | Integration patterns |

Auswertungsbasis (Stand wie letzter Matcher-Lauf):

- `_tmp_manuscript_cite_pdf_coverage.csv` („verifiziert“ = DOI-/Text-/Autoren-Nachweis wie im Skript `paper_library/match_literatur_pdfs_to_bib.py`)
- Zitations-Extraktion: `\cite...{key1,key2,...}` analog zum Matcher (`\cite`, optional `p`/`t`, optional `*`)

## Ergebnis über alle vier Dateien zusammen

| Kennzahl | Wert |
| -------- | -----: |
| Eindeutige `\cite`-Keys in diesen vier `.tex`-Dateien | **190** |
| Davon mit mindestens einem **verifizierten** PDF (`verified_pdf_count ≥ 1`) | **165** |
| Keys **ohne** verifizierte PDF-Zuordnung | **25** |

Einzelne Keys können **mehrere** PDFs haben (`multiple_pdf_collision=yes` in der CSV); sie zählen trotzdem zu den 165 „mit PDF“.

## Aufteilung pro Datei

(Eindeutige Keys pro Datei = jeder cite-Key höchstens einmal gezählt, unabhängig davon wie oft `\cite{...}` ihn nutzt.)

| Datei | Eindeutige Keys in dieser `.tex` | Davon ohne verifiziertes PDF |
| ----- | --------------------------------: | ----------------------------: |
| `02_related_reviews.tex` | 32 | 4 |
| `04_taxonomy_surrogates.tex` | 96 | 8 |
| `05_training_data_doe.tex` | 93 | 12 |
| `06_integration_patterns.tex` | 104 | 12 |

„Ohne PDF“: Key kommt in der Datei vor **und** in `_tmp_manuscript_cite_pdf_coverage.csv` ist `verified_pdf_count = 0`.

## Die 25 Keys ohne verifiziertes PDF (nur Kern-Sections)

Diese Liste ist die Schnittmenge „wird in einem der vier obigen `.tex` zitiert“ ∩ „kein verifiziertes PDF im Matcher-Ergebnis“:

- Abedinia20161511  
- Amaral20251156  
- Amoedo2023929  
- Bayani20231024  
- Bianchi2020244  
- Ceylan2020944  
- ChenRenZhou2023  
- Giorgetti2020  
- Granacher20221573  
- Guan2025  
- Jia2022553  
- Khan2024_DT  
- Khayambashi202453  
- Li2021  
- Ma2022737  
- Meng20191219  
- Morakinyo201973  
- Prusty2025  
- Reynolds2017704  
- Schulte2016104  
- Simonson202036  
- Starke2025214  
- Wang2021  
- Zulfiqar20211026  
- salgueiro_multi-objective_2019  

**Einordnung:** Im gesamten Manuskript+Tabellen sind deutlich mehr Keys ohne PDF gelistet (Report-Feld `cites_without_verified_pdf`); die **25** betreffen nur die vier Kern-Sections.

---

## Können wir trotzdem noch „alle“ zuordnen?

**Nein — aus dem Zahlenstreifen allein lässt sich nicht sagen, dass „eindeutig nur noch Dateien fehlen“.** `verified_pdf_count = 0` heißt nur: Mit den **aktuellen** PDFs unter `Literatur/**` hat der Matcher **keinen bestätigten** Treffer gebildet. Typische Ursachen (oft mehrere möglich):

1. **PDF fehlt** im `Literatur`-Baum oder liegt nur außerhalb des Review-Projekts.  
2. **PDF ist da**, aber unter anderem Namen/Ordner; der Abgleich scheitert (schlechte Erstextraktion, kein gut lesbarer DOI im Snippet).  
3. **Strikte Verifikation:** Heuristik findet einen Kandidaten, Stufe-2-Verifikation lehnt ab → in der Zuordnungstabelle eher `unmatched`/`verification_rejected`, nicht „Key mit PDF“.  
4. **Bib/Daten:** fehlende oder falsche DOI-Zeile, Tippfehler im Key — dann hilft Datenfix statt weiterer PDF-Jagd.

**Praktisches Vorgehen, um die Zuordnung ohne Raten weiterzubringen:**
- Für jeden der 25 Keys: Bib-Eintrag (DOI?) prüfen, dann `_tmp_pdf_author_title_match_map.csv` nach **unmatched**-Zeilen durchsuchen, ob ein PDF mit gleicher DOI schon vorliegt.  
- Fehlenden Download beschaffen oder PDF in den passenden Section-Ordner legen (`Other` hilft beim Sammeln, Matching nutzt dort aber das **globale** Zitationsuniversum).  
- Bei Bedarf Matcher mit mehr `--extract-pages` erneut laufen oder Text manuell im PDF kontrollieren.  
- Wenn ihr bewusst **manuelle Overrides** erlauben wollt (z. B. YAML „Key → relativer Pfad“), müsste das **explizit** im Skript ergänzt werden — aktuell gibt es keine stille Zuordnung.

**Fazit:** Die **25 Einträge markieren Arbeitspunkte**, nicht zwingend „ein fehlender Bestandteil“ pro Key. Zuordnung ist oft noch **machbar**, erfordert aber **pro Key** Datenlage (PDF da? DOI? Zeilen in `_tmp_pdf_author_title_match_*`?) — ohne diese Prüfung ist nicht „eindeutig“, dass nur Downloads fehlen.
