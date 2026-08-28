# Table: runtime for one Vienna city year

Eight `annual_reference_2023` cohorts, 8 x 8760 h. Diagnostic plots excluded.

| Path | Prepare [s] | EnergyPlus engine [s] | SQL extract [s] | Total [s] |
|---|---:|---:|---:|---:|
| EnergyPlus demand path | 27.5 | 24.8 | 14.8 | 67.1 |
| Surrogate inference | — | — | — | 1.73 |

Speedup (demand path / predict): **39×**.
One-time surrogate fit: 18.5 s.
