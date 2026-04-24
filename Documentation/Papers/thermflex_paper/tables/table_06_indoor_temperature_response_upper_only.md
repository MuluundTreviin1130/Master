| Day | Case | Active member-hours [h] | Shifted heat [MWh] | Rebound heat [MWh] | Max T_in above setpoint [K] | Mean positive T_in above setpoint [K] | Interpretation |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| 2023-01-17 | `UPPER_24H`, activation-gated | 8 | 0.0 | 469.8 | 0.00 | 0.00 | Cold contrast day; almost no preheat, but small cutback is possible without visible indoor-temperature lift. |
| 2023-03-04 | `UPPER_24H`, activation-gated | 75 | 2104.2 | 1768.0 | 2.59 | 0.33 | Clear indoor-state charging after the activation-gate fix; the old near-zero result was a diagnostic artefact of inactive shifting. |
| 2023-11-04 | `UPPER_24H`, activation-gated | 81 | 2545.7 | 2171.1 | 2.76 | 0.46 | Strong top-savings day; preheat is now visible as a real indoor-temperature excursion. |

Notes:
- The earlier `UPPER_1H` table showed almost no `T_in` response because the dispatch could shift `q_heat` while `therm_flex_active = 0`.
- The MILP now gates any `q_heat - q_ref` deviation through `therm_flex_active`, so duration/event limits and indoor-temperature diagnostics are aligned.
- `Shifted heat` and `rebound heat` here use the direct member-level `q_heat - q_ref` balance.
