# Introduction

District heating is expected to remain a central decarbonization lever in Vienna.
Official city strategy documents target a major expansion of district heating
towards 2040, with district heating intended to cover roughly 56% of the demand
for space heating and domestic hot water in the city
([S1](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Sources/wien_und_dispatch_quellen.md)).
At the same time, the current Vienna heat system still relies on a mixed supply
portfolio that includes combined heat and power, boilers, waste heat, waste
incineration, biomass, and emerging large-scale heat pumps
([S1](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Sources/wien_und_dispatch_quellen.md)).
This makes operational flexibility valuable, but also means that the value of any
single flexibility option depends on heat-system conditions, market signals, and
building demand patterns.

Building thermal flexibility is one of the most discussed demand-side options for
future heat and power systems. In practice, however, many system-level studies
either treat buildings as static heat sinks or represent thermal flexibility using
very coarse stylized assumptions. That is not sufficient for the present case. In
district-heating dispatch, the operational value of thermal flexibility depends on
how much building heat demand can actually be shifted, how strong the rebound is,
and whether flexibility alleviates or worsens system stress on specific day types.
For Vienna, this is especially relevant because a large existing building stock,
heterogeneous heating conditions, and a central district-heating system meet in a
single urban case.

The methodological challenge is therefore twofold. First, the building model must
be physically plausible enough to represent indoor-temperature dynamics,
preheating, cutback, and rebound effects. Second, it must remain tractable enough
to be embedded in system-level dispatch optimization. The approach developed in
this repo addresses that trade-off through a multi-fidelity pipeline: detailed
offline building simulations are used as a teacher, their response is exported
into a reduced-order archetype representation, and this reduced-order
representation is then embedded in the district-heating dispatch model
([S2](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Sources/building_calibration_quellen.md),
[S3](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Appendices/vienna_building_model_parameters_appendix.md)).

Within that setup, the present paper focuses on an operational question rather
than a whole-system design question: what is the dispatch value of
building-side thermal flexibility in the Vienna district-heating system, and how
robust is that value across day types and historical uncertainty? The current
results already show that the answer is not a simple universal cost reduction.
Thermal flexibility can shift several gigawatt-hours of space-heating demand,
reduce peak demand, and remove unserved heat in stressed dispatch situations, but
the benefit is day-type dependent and does not translate into the same ranking
for cost, CO2, and shifted energy on every day
([S4](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/run/results/Vienna/gold/constant_thermflex_representative_day_summary_20260403/representative_day_case_summary.md),
[S5](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Papers/dh_thermflex_vienna.md)).

This paper therefore pursues three linked research questions. First, how much and
in what form can building-side thermal flexibility alter the Vienna
district-heating dispatch under a calibrated reduced-order building
representation? Second, how strongly does that value depend on day type and on
simple global policy parameters such as comfort lower bound, maximum flex
duration, and event frequency? Third, can a historical two-stage stochastic
dispatch confirm that promising thermal-flexibility settings remain operationally
relevant when evaluated against reduced historical uncertainty scenarios rather
than a single deterministic case
([S5](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Papers/dh_thermflex_vienna.md))?

The contribution of the paper is not to claim a universally optimal thermal
flexibility policy. The stronger contribution is more specific: it shows how a
physics-grounded, EnergyPlus-calibrated, yet tractable building-flexibility
representation can be embedded into Vienna district-heating dispatch analysis; it
demonstrates that the operational value of thermal flexibility is strongly
day-type dependent; and it clarifies which parts of that value appear as peak
relief, load shifting, service improvement, and emissions effects rather than
only as direct operating-cost changes.

## Source Basis

- [S1] Vienna and dispatch source notes:
  [wien_und_dispatch_quellen.md](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Sources/wien_und_dispatch_quellen.md)
- [S2] Building calibration source notes:
  [building_calibration_quellen.md](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Sources/building_calibration_quellen.md)
- [S3] Vienna building appendix:
  [vienna_building_model_parameters_appendix.md](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Appendices/vienna_building_model_parameters_appendix.md)
- [S4] Representative-day result summary:
  [representative_day_case_summary.md](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/run/results/Vienna/gold/constant_thermflex_representative_day_summary_20260403/representative_day_case_summary.md)
- [S5] Paper scope note:
  [dh_thermflex_vienna.md](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Papers/dh_thermflex_vienna.md)
