| Day | Midday preheat window | Midday preheat [MWh] | Evening release window | Evening release [MWh] | Cost change with solar [%] | Cost change without solar [%] | CO₂ change with solar [%] | CO₂ change without solar [%] | Interpretation |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | --- |
| 2023-03-04 | 10:00-14:00 | 1507.7 | 18:00-22:00 | 2324.7 | -4.33 | -0.73 | -10.70 | -1.93 | Strong midday preheat followed by strong evening release; removing solar almost collapses the effect. |
| 2023-11-04 | 10:00-14:00 | 2078.8 | 18:00-22:00 | 2731.2 | -5.23 | -0.79 | -10.49 | -1.83 | Same pattern as 2023-03-04, with even stronger midday loading and evening release; solar materially enables the shift. |

Notes:
- `Midday preheat [MWh]` is the positive `dh_total_demand` delta of `UPPER_1H` vs. reference summed over `10:00-14:00`.
- `Evening release [MWh]` is the absolute negative `dh_total_demand` delta of `UPPER_1H` vs. reference summed over `18:00-22:00`.
- `without solar` is the counterfactual with `thermal.runtime_solar_shading_factor = 0.0`, keeping the dispatch case otherwise unchanged.
