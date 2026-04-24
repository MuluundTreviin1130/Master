| Day | `upper_only` duration / events | Shifted heat [MWh] | Mean ΔT_in during active hours [K] | Max ΔT_in [K] | Boiler peak change vs. `dur0` [%] | Interpretation |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| 2023-03-04 | `1 h / 1` | 3626.2 | 0.000 | 0.000 | 0.00 | On this top-savings day the current `upper_only` duration cap is effectively non-binding. |
| 2023-03-04 | `4 h / 1` | 3626.2 | 0.000 | 0.000 | 0.00 | Same as `1 h`; extending duration does not unlock additional indoor-temperature or peak effect. |
| 2023-03-04 | `24 h / 24` | 3626.2 | 0.000 | 0.000 | 0.00 | Even the quasi-unbounded proxy does not materially change the result. |
| 2023-11-04 | `1 h / 1` | 4267.2 | 0.000 | 0.099 | 0.00 | Strong shift already achieved at `1 h`; indoor-temperature excursion remains very small. |
| 2023-11-04 | `4 h / 1` | 3713.1 | 0.000 | 3.859 | -1.55 | Longer duration changes the solution only slightly, with a somewhat larger but still limited `T_in` excursion. |
| 2023-11-04 | `24 h / 24` | 3722.0 | 0.000 | 3.379 | -1.55 | The active `upper_only` mechanism remains only weakly duration-sensitive on this day. |

Notes:
- The no-flex comparison path here is generated from the same `upper_only` configuration with `max_flex_duration_h = 0` and `max_flex_events_per_day = 0`, so member-level `T_in` remains available.
- The main result is methodological: `upper_only` is explicitly time-limited in the settings, but on the current top-savings days that limit is only weakly binding.
