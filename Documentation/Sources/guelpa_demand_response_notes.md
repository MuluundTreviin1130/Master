# Guelpa / Politecnico Demand-Response Notes

## Local PDFs reviewed

- `C:\Users\Philipp Thunshirn\Downloads\1-s2.0-S0360544221007210-main.pdf`
  - Capone, Guelpa, Verda (2021), *Multi-objective optimization of district energy systems with demand response*, Energy.
- `C:\Users\Philipp Thunshirn\Downloads\1-s2.0-S0306261919311481-main.pdf`
  - Guelpa, Verda (2019), *Thermal energy storage in district heating and cooling systems: A review*, Applied Energy.

## Points relevant for the Thermflex paper

- Demand response in district heating is framed as a way to reduce thermal peaks and fill valleys.
- The production-side motivation is explicit: CHP typically covers base load, while heat-only boilers cover peaks.
- The 2021 paper combines production optimization with demand-side management in a multi-energy setting, using operation cost and CO2 emissions as separate objectives.
- Their results explicitly show cost/CO2 trade-offs rather than guaranteed joint improvement; this supports our side-analysis of day types where not all KPIs improve.
- The review paper treats building heat capacity and network thermal inertia as alternative storage forms within DH systems.
- Reported literature ranges in the review include DH peak reductions from demand-response / load-shifting studies on the order of several percent up to substantially larger values depending on scenario and constraints.
- The review emphasizes that building-characteristic constraints matter, including building time constants, outdoor temperature, and current heat request.

## Methodological lessons for our analysis

- Do not report only shifted heat. Tie the shifted heat to system KPIs: cost, CO2, boiler energy, and boiler peak.
- Keep peak-boiler avoidance as a mechanism, but do not assume every peak reduction reduces CO2.
- Show trade-offs explicitly: cost-optimal and CO2-optimal operation can diverge.
- Treat building cohorts as thermal-storage classes: duration sensitivity and time constants are central, not only one-hour event energy.
- For the paper, a table is useful for trade-off days; an hourly plot is better for showing when preheat and release occur.

## Current repo implication

- The Thermflex activation gate must be enforced before final comparison to Guelpa-style demand-response results.
- Post-fix diagnostics should use:
  - member-level `q_heat - q_ref`
  - `therm_flex_active`
  - indoor-temperature rise above setpoint
  - boiler energy / peak
  - system cost and CO2
