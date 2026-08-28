# Figures

Three paper-facing figures for the EnergyPlus demand-surrogate conference paper.

- `fig_01_teacher_flow_day.png` — EnergyPlus teacher heat-balance flows, four residential periods
- `fig_02_city_holdout_seasonal_weeks.png` — city EnergyPlus vs surrogate in peak heating/cooling weeks plus spring and autumn
- `fig_03_temperature_response.png` — city heating/cooling versus outdoor temperature

Runtime is `../results/table_01_runtime.md`, not a figure.

Rebuild:

```text
python Documentation/Papers/energyplus_demand_surrogate_vienna/figures/runners/build_paper_figures.py
```
