# EnergyPlus vs demand-surrogate runtime

One Vienna city year is eight `annual_reference_2023` cohort profiles (8 x 8760 h).
Diagnostic plots are excluded. EnergyPlus re-runs used a temporary directory and did not overwrite `_teacher_runs/`.
Surrogate inference was timed on an in-process refit of the published HistGradientBoosting spec; holdout accuracy remains `model_manifest.json`.

- Host: `SERVICE-22RILCT` / `AMD64` / `Intel64 Family 6 Model 142 Stepping 12, GenuineIntel`
- Python: `3.12.10`
- EnergyPlus engine repeats per cohort: `3`
- Surrogate predict repeats: `5`

| Quantity | Seconds |
|---|---:|
| EnergyPlus prepare (schedules + IDF), 8 cohorts | 27.505 |
| EnergyPlus engine wall-clock median sum, 8 cohorts | 24.786 |
| EnergyPlus engine `eplusout.end` median sum, 8 cohorts | 19.920 |
| EnergyPlus SQL extract, 8 cohorts | 14.808 |
| EnergyPlus demand-path total (prepare + engine wall + extract) | 67.099 |
| Surrogate load feature table | 2.710 |
| Surrogate fit both targets, one-time | 18.455 |
| Surrogate predict both targets, median | 1.7306 |
| Speedup, demand-path / predict | 38.8 |
| Speedup, engine wall / predict | 14.3 |

Repeated city-year evaluations after the surrogate is already loaded:

| Evaluations | EnergyPlus demand-path [s] | Surrogate predict [s] | Time saved [s] |
|---:|---:|---:|---:|
| 1 | 67.099 | 1.7306 | 65.369 |
| 10 | 670.992 | 17.3063 | 653.686 |
| 50 | 3354.960 | 86.5313 | 3268.428 |
