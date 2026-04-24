| Date | Day type | Mean outdoor temperature [degC] | Cost change [%] | CO2 change [%] | Boiler energy change [%] | Boiler peak change [%] | Shifted heat [MWh] | Rebound heat [MWh] | Rebound / shifted [%] | Max T_in above setpoint [K] | Reading |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 2023-01-17 | cold contrast | 1.4 | -0.31 | -0.81 | -1.37 | 0.00 | 0.0 | 469.8 | n/a | 0.00 | Cold day with weak effect; savings mostly come from limited cutback rather than preheat. |
| 2023-02-21 | robust savings, peak kink | 8.7 | -2.50 | -6.37 | -21.54 | +3.68 | 2515.7 | 2171.1 | 86.3 | 2.76 | Strong savings despite a slightly higher boiler peak in another hour. |
| 2023-03-04 | robust savings | 7.8 | -2.08 | -4.94 | -14.81 | 0.00 | 2104.2 | 1768.0 | 84.0 | 2.59 | Clear preheat/release day after activation gating; savings remain robust but smaller than the pre-fix screen suggested. |
| 2023-03-16 | robust savings | 8.2 | -1.97 | -5.21 | -18.15 | 0.00 | 2489.3 | 1755.6 | 70.5 | 2.70 | Longer activation creates visible indoor charging and still reduces cost and CO2. |
| 2023-03-18 | robust savings | 7.6 | -2.16 | -5.01 | -15.16 | 0.00 | 2137.5 | 1768.0 | 82.7 | 2.39 | Strong joint savings without boiler-peak penalty. |
| 2023-03-23 | robust savings, peak kink | 9.0 | -1.69 | -4.23 | -13.61 | +11.57 | 2569.2 | 1470.5 | 57.2 | 2.79 | Savings remain positive although the absolute boiler peak moves upward in another hour. |
| 2023-04-03 | late-season CO2 kink | 12.9 | 0.00 | +0.18 | +0.88 | 0.00 | 2342.8 | 29.4 | 1.3 | 2.41 | Almost neutral cost impact, but late-season shifting becomes counterproductive for CO2. |
| 2023-04-04 | late-season CO2 kink | 13.4 | -0.01 | +0.19 | +1.45 | 0.00 | 3036.4 | 0.0 | 0.0 | 2.88 | Strong preheat without useful system benefit; boiler work and CO2 edge upward. |
| 2023-04-12 | late-season near-neutral day | 13.4 | -0.01 | +0.18 | +1.32 | 0.00 | 2952.2 | 0.0 | 0.0 | 2.88 | Late-season case with almost no net system value despite visible indoor charging. |
| 2023-11-04 | best joint savings day | 10.7 | -3.42 | -6.86 | -28.45 | -44.08 | 2545.7 | 2171.1 | 85.3 | 2.76 | Clean top-savings day with strong boiler and peak relief. |

Active case:
- `upper_only`
- `max_flex_duration_h = 24`
- `max_flex_events_per_day = 24`
- objective without `grid_export_revenue`
- post Thermflex activation-gate fix

Interpretation:
- These values are post activation-gate fix; older `dur24` screen values are superseded for final paper use.
- The strongest days are still mild winter / shoulder-winter days rather than the coldest days.
- The late-season April kinks are easier to read in table form than in the grouped bar plot because rebound, indoor charging, boiler work, cost, and CO2 do not all move in the same direction.
- Positive cost and CO2 savings can coexist with slight boiler-peak increases, which means the day-level benefit is not determined by the absolute peak hour alone.
