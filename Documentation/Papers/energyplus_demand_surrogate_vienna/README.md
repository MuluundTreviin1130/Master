# EnergyPlus Demand Surrogate, Vienna

Conference-paper workspace for the EnergyPlus-trained Vienna heating and
cooling demand surrogate. Scope is the teacher-to-surrogate demand layer only:
no district-heating flexibility, no PyPSA, no system-design optimisation.

English draft: `manuscript/manuscript.md`.

## Active result

One 2023 city year (eight `annual_reference_2023` cohorts): EnergyPlus demand
path `67.1 s` versus surrogate prediction `1.73 s` (`38.8 x`). Details:

- `results/runtime_benchmark.md`
- `results/runtime_benchmark.json`
- `results/runtime_benchmark.csv`

Rebuild with:

```text
python Learning/building_demand_surrogate/benchmark_annual_reference_runtime.py
```

The benchmark copies registered IDFs into a temporary directory. It does not
overwrite `Technical_model/technologies/buildings/calibration/_teacher_runs/`.
