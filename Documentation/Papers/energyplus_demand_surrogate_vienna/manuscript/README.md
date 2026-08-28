# Manuscript

English conference draft for the Vienna EnergyPlus demand surrogate. Keep
ThermFlex dispatch and MES optimisation out of this text.

- `manuscript_ieee.tex` — active IEEEtran conference manuscript
- `manuscript_ieee.pdf` — locally compiled IEEE preview
- `references.bib` — paper-specific BibTeX metadata retained as a reusable
  library; the active IEEE file also contains the formatted references inline
- `manuscript.tex` / `manuscript.pdf` — earlier generic two-column version
- `manuscript.md` — earlier text-first working draft
- Figures: `../figures/png/`
- Runtime table: `../results/table_01_runtime.md`

`manuscript_ieee.tex` is self-contained apart from its three PNG figures and
can be pasted directly into Overleaf. Upload the figures to the project root
or a `figures/` folder. Build locally with:

```text
pdflatex manuscript_ieee.tex
pdflatex manuscript_ieee.tex
```
