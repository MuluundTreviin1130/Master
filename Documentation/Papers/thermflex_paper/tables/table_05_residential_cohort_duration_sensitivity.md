| Residential cohort | Annual space heat [kWh/m2a] | Design heat load [W/m2] | C_eff 1 K charge [Wh/m2] | tau [h] | Retained 1 h [Wh/m2] | Retained 4 h [Wh/m2] | Retained 12 h [Wh/m2] | Retained 24 h [Wh/m2] | Realized shifted 24 h [Wh/m2] | Realized release 24 h [Wh/m2] | Active 24 h [h] | Max T_in +24 h [K] | Reading |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| pre1975 | 145.7 | 43.0 | 25.02 | 19.79 | 23.8 | 20.4 | 13.6 | 7.4 | 79.0 | 69.3 | 18 | 2.76 | Highest short-term heat demand and high 1 K charge, but the stored state decays fastest. |
| 1975-1990 | 111.3 | 35.5 | 22.25 | 21.30 | 21.2 | 18.5 | 12.7 | 7.2 | 54.8 | 43.3 | 16 | 2.22 | Similar old-stock behavior with slightly better persistence than pre1975. |
| 1990-2000 | 76.3 | 26.9 | 20.43 | 25.83 | 19.7 | 17.5 | 12.8 | 8.1 | 12.4 | 19.7 | 8 | 0.59 | Lower short-term charge than old stock, but better long-duration retention. |
| 2000-2014 | 31.7 | 16.3 | 21.20 | 44.31 | 20.7 | 19.4 | 16.2 | 12.3 | 9.1 | 0.0 | 3 | 0.44 | Best long-duration retention; low reference heat demand limits realized system use on this day. |

Notes:
- `C_eff 1 K charge` is the effective heat stored per square metre for a normalized 1 K indoor-state increase in the active reduced-order model.
- `Retained h = C_eff * exp(-h / tau)`. This is the clean cohort-persistence metric: old stock can hold more at very short horizons, while the modern cohort retains more after long delays.
- `Realized shifted/release` are not pure physical storage capacities. They come from a targeted post-fix `upper_only`, `max_flex_duration_h = 24`, `max_flex_events_per_day = 24` Gold evaluation for `2023-11-04`.
- `Realized shifted = sum(max(q_heat - q_ref, 0)) / DH-connected GFA`.
- `Realized release = sum(max(q_ref - q_heat, 0)) / DH-connected GFA`; this is useful later reduction of reference heating, not a cohort-specific cost or CO2 saving.
- `Active hours` counts member-hours in which the MILP allowed that cohort to deviate from its reference heat path. It is a control-use diagnostic, not a savings KPI.
- System-level context for the `2023-11-04` realized case from the current trade-off table: cost `-3.42%`, CO2 `-6.86%`, boiler energy `-28.45%`, boiler peak `-44.08%`.
