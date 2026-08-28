# Building Demand Surrogate

This layer owns EnergyPlus-informed surrogate preparation, training and
validation for Vienna building heating and cooling demand.

It is distinct from `Learning/building_response/`, which targets stateful
building-response and future flexibility behavior. The demand surrogate
supplies physically informed useful-heating and useful-cooling profiles to the
energy-system model; it is not an active load-shifting optimizer.

Reusable teacher and model artifacts must be registered through
`Learning/datasets/` and must retain their cohort, weather and EnergyPlus-run
provenance.

## Active Annual Reference

`annual_reference_2023` is the active full-year EnergyPlus teacher family for
the eight registered Vienna cohorts. Its raw annual energies are teacher output,
not scenario demand anchors. The active PyPSA bundle normalizes the teacher
profiles and applies the separately sourced transformation-year totals.

`train_annual_reference_demand_surrogate.py` trains separate useful-heating and
useful-cooling hurdle emulators on this family. Each target has an on/off gate
plus a magnitude model, setpoint/UA drive features, and monotonic outdoor-
temperature constraints. Full-calendar-week holdouts stay on the fixed cohort
set. The model does not include building flexibility or load shifting. The
direct teacher profile remains the active 2023 reference shape; the learned
model is the fast path for later declared cohort or weather sensitivity runs.
Active bundle: `vienna_building_demand_annual_reference_2023_v2`. v1 remains
on disk as the previous squared-error-only baseline.

`benchmark_annual_reference_runtime.py` measures wall-clock time for the
EnergyPlus demand path versus surrogate inference on the same eight annual
cohorts. Paper-facing outputs are written to
`Documentation/Papers/energyplus_demand_surrogate_vienna/results/`.
