# Results

The curated result layer for this paper now lives under:

- [results](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Papers/thermflex_paper/results)

Current structured blocks:

1. [core dispatch results](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Papers/thermflex_paper/results/01_core_dispatch_results.md)
2. [representative-day results](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Papers/thermflex_paper/results/02_representative_day_results.md)
3. [two-stage robustness results](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Papers/thermflex_paper/results/03_two_stage_results.md)
4. [cohort mechanism results](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Papers/thermflex_paper/results/04_cohort_mechanism_results.md)
5. [biobjective results](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Papers/thermflex_paper/results/05_biobjective_results.md)
6. [surrogate status](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Papers/thermflex_paper/results/06_surrogate_status.md)

Working interpretation:

- the strongest main-text story remains:
  - thermflex changes the Vienna DH dispatch materially
  - the value is day-type dependent
  - the cohort layer explains why the response is heterogeneous
- the `milp_two_stage` block now supports this story as a historical robustness
  layer rather than as the main search path
- the surrogate layer is useful for search support, but the current holdout
  evidence is not strong enough to replace gold evaluation for all main paper
  KPIs
