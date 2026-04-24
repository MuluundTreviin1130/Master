# Figure and Table Plan

## Figure 0: Teacher Reference Flow Comparison

- asset:
  - [fig_00_teacher_reference_flow_comparison.png](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Papers/thermflex_paper/figures/fig_00_teacher_reference_flow_comparison.png)
- figure note:
  - [fig_00_teacher_reference_flow_comparison.md](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Papers/thermflex_paper/figures/fig_00_teacher_reference_flow_comparison.md)
- raw source bundle:
  - [teacher_runs](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Technical_model/technologies/buildings/calibration/_teacher_runs)
- message:
  - the four residential period archetypes are compared in a compact grid
  - the plot focuses on heating, total gains, and losses without the temperature panel
- role in manuscript:
  - strong early Results figure or Methods/Results bridge
- next refinement:
  - decide whether the main cut should stay on the current representative winter day
    or whether a second appendix variant for another day type should be added

## Figure 1: Core Deterministic Dispatch Comparison

- asset:
  - [fig_01_core_dispatch_comparison.png](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Papers/thermflex_paper/figures/fig_01_core_dispatch_comparison.png)
- curated source:
  - [01_core_dispatch_results.md](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Papers/thermflex_paper/results/01_core_dispatch_results.md)
- raw source bundle:
  - [paper_dispatch_comparison_20260403_131344](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/run/results/Vienna/gold/paper_dispatch_comparison_20260403_131344)
- message:
  - thermflex changes the Vienna DH dispatch materially
  - the main gain is not only cost, but also elimination of unserved heat,
    shifted space heat, rebound management, and peak relief
- role in manuscript:
  - main-text core figure

## Figure 1b: Use-Case Shift and Gas-Boiler Comparison

- asset:
  - [fig_01_use_case_shift_boiler.png](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Papers/thermflex_paper/figures/fig_01_use_case_shift_boiler.png)
- figure note:
  - [fig_01_use_case_shift_boiler.md](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Papers/thermflex_paper/figures/fig_01_use_case_shift_boiler.md)
- message:
  - the reference case stays embedded as the gray line in each panel
  - upper-only preheating already shifts district space heat and changes gas-boiler dispatch
  - a lean full thermflex case (`dur1`) extends the same mechanism
- role in manuscript:
  - likely stronger than the old constant isolation bar plot
  - candidate main-text mechanism figure

## Figure 2: Representative-Day Comparison

- asset:
  - [fig_02_representative_day_summary.png](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Papers/thermflex_paper/figures/fig_02_representative_day_summary.png)
- curated source:
  - [02_representative_day_results.md](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Papers/thermflex_paper/results/02_representative_day_results.md)
- raw source bundle:
  - [constant_thermflex_representative_day_summary_20260403](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/run/results/Vienna/gold/constant_thermflex_representative_day_summary_20260403)
- message:
  - thermflex value is strongly day-type dependent
  - no single global policy dominates every relevant operating context
- role in manuscript:
  - main-text supporting figure

## Figure 3: Cohort Mechanism

- asset:
  - [fig_03_cohort_mechanism.png](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Papers/thermflex_paper/figures/fig_03_cohort_mechanism.png)
- curated source:
  - [04_cohort_mechanism_results.md](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Papers/thermflex_paper/results/04_cohort_mechanism_results.md)
- raw source bundle:
  - [paper_dispatch_comparison_20260403_131344](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/run/results/Vienna/gold/paper_dispatch_comparison_20260403_131344)
- message:
  - cohort-level heterogeneity explains why a global thermflex policy does not
    produce uniform use across the building stock
- role in manuscript:
  - main-text mechanism figure

## Figure 4: Optional Two-Stage Robustness Summary

- current status:
  - concept only; no dedicated final paper asset yet
- curated source:
  - [03_two_stage_results.md](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Papers/thermflex_paper/results/03_two_stage_results.md)
- possible message:
  - the historical stochastic robustness layer is operational and no longer
    blocked by a broken `day_ahead -> two_stage` bridge
- role in manuscript:
  - optional compact main-text or appendix figure/table

## Table 1: Case Definition

- status:
  - to build
- intended contents:
  - reference cases
  - policy-code naming
  - representative-day set
- role:
  - main-text setup table

## Table 2: Core KPI Comparison

- status:
  - to build from the deterministic core dispatch block
- source:
  - [01_core_dispatch_results.md](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Papers/thermflex_paper/results/01_core_dispatch_results.md)
- intended KPI set:
  - `dispatch_operating_cost_eur`
  - `co2_emissions_total_t`
  - `dh_unserved_heat_kwh`
  - `thermflex_shifted_space_heat_kwh`
  - `thermflex_rebound_kwh`
  - `thermflex_peak_change_kw`
- role:
  - main-text KPI table

## Table 3: Representative-Day Summary

- status:
  - to build
- source:
  - [02_representative_day_results.md](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Papers/thermflex_paper/results/02_representative_day_results.md)
- intended message:
  - which policy performs best on which day type
- role:
  - main-text or appendix, depending on journal page pressure

## Table 4: Reduced-Scenario Sensitivity

- status:
  - not yet produced
- intended contents:
  - `n_reduced = 1, 2, 3, 6` comparison for the same two-stage candidate
- role:
  - appendix or supplementary material

## Table 5: Surrogate Status

- status:
  - optional note or appendix table
- source:
  - [06_surrogate_status.md](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Papers/thermflex_paper/results/06_surrogate_status.md)
- intended message:
  - surrogate is useful for search acceleration
  - gold runs remain the truth layer for final claims
