# Methods

## Case Boundary and Modeling Objective

The paper studies the operational effect of building-side thermal flexibility on
the Vienna district-heating (DH) dispatch. The scope is intentionally narrower
than the broader Vienna 2040 multi-energy-system research program. The present
study does not solve the full coupled electricity-heat-mobility design problem.
Instead, it isolates the DH dispatch layer, embeds a calibrated building-side
flexibility representation, and evaluates its effect through deterministic
day-ahead dispatch, representative-day sensitivity, a historical two-stage
robustness layer, and a surrogate-assisted exploration layer
([M1](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Papers/dh_thermflex_vienna.md)).

The Vienna case is implemented on repo-level settings and data layers that
contain the active district-heating technology assumptions, building-stock
scaling anchors, historical profiles, and dispatch-relevant market and
emissions inputs
([M2](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Sources/wien_und_dispatch_quellen.md),
[M3](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Settings/dispatch/dispatch.py)).
The core methodological question is not whether thermal flexibility exists in
principle, but whether a physics-grounded and computationally tractable
representation of that flexibility changes system operation in a way that
matters for cost, emissions, peak stress, and service quality.

## Data Basis and Literature Foundation

The data basis combines three source layers. First, official Vienna and Austria
sources provide case-specific anchors for the present-day DH system, connected
customer scale, energy balances, weather-related reference paths, and sectoral
electricity and heat context
([M2](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Sources/wien_und_dispatch_quellen.md)).
These sources include the Vienna energy report, Vienna heat-transition planning
documents, official generation and technology summaries, and further public
statistics used to anchor the 2023 reference case. Second, building and
calibration assumptions are grounded in Austrian and European building-typology
and simulation literature, especially TABULA/EPISCOPE, Austrian building
practice references, and the EnergyPlus-based calibration workflow documented in
the repo source notes
([M6](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Sources/building_calibration_quellen.md)).
Third, repo-internal single-source-of-truth files translate these external
sources into explicit model inputs, archetype parameters, and dispatch settings
([M3](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Settings/dispatch/dispatch.py),
[M4](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Data/building_stock/Vienna/building_stock.py),
[M5](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Data/thermal_archetypes/Vienna/thermal_archetypes.py)).

This distinction is important for the paper. Official sources anchor the Vienna
case, the building-simulation and typology literature anchor the physical
plausibility of the reduced-order building layer, and repo-internal files define
the exact active implementation used in the experiments. The detailed building
parameter documentation is summarized separately in the Vienna appendix
([M7](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Appendices/vienna_building_model_parameters_appendix.md)).

## Vienna Building Stock and Archetypes

The building side is represented through sector- and construction-period-specific
cohorts for residential and non-residential buildings. The Vienna stock layer
provides the scaling anchors required to couple buildings to the system model,
including represented gross floor area, represented volume, annual heat targets,
and load-profile assignment
([M4](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Data/building_stock/Vienna/building_stock.py)).
This cohort structure allows the model to preserve heterogeneity in thermal
behavior without moving to full building-by-building dispatch.

Residential archetypes are apartment-block-like reference buildings rather than
single-family houses. Their geometry ratios are based on Austrian TABULA
apartment-block averages, while their envelope values are seeded from
TABULA-informed construction-period assumptions
([M5](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Data/thermal_archetypes/Vienna/thermal_archetypes.py),
[M6](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Sources/building_calibration_quellen.md)).
This gives the residential layer a clearer physical basis than earlier stylized
defaults. By contrast, non-residential archetypes remain pragmatic V1 proxies,
which is acceptable for the present operational paper cut but remains a known
limitation
([M5](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Data/thermal_archetypes/Vienna/thermal_archetypes.py),
[M7](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Appendices/vienna_building_model_parameters_appendix.md)).

The active paper workflow uses the calibrated Vienna archetype export
`calibrated_v1`, which contains reduced-order thermal parameters and
event-response bounds derived from an offline teacher pipeline
([M8](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Data/thermal_archetypes/Vienna/calibrated_v1.py),
[M6](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Sources/building_calibration_quellen.md)).

The Citiwatts toolbox was used as a spatially informed top-down input based on
Geographic Information System (GIS) data. Annual total heat demand, gross floor
area, building volume, and construction-period shares were extracted for the
Vienna area. The stock was differentiated into four construction periods
(\(<1975\), 1975--1990, 1990--2000, and 2000--2014) and into residential and
non-residential buildings, yielding eight cohort-archetype groups. Based on
these data, an aggregated representation of the Vienna building stock was
reconstructed by distributing the sector totals across these cohort groups
according to the reported construction-period shares. In compact form, the
cohort scaling variables were defined as

\[
A_{s,p} = A_s^{\mathrm{tot}} \alpha_{s,p}, \qquad
V_{s,p} = V_s^{\mathrm{tot}} \alpha_{s,p}, \qquad
Q_{s,p}^{\mathrm{heat,ann}} = Q_s^{\mathrm{heat,ann}} \alpha_{s,p},
\]

where \(s\) denotes the sector, \(p\) the construction period,
\(\alpha_{s,p}\) the normalized stock share, \(A\) gross floor area, \(V\)
building volume, and \(Q^{\mathrm{heat,ann}}\) annual heat demand. This
reconstruction step ensured that the thermal archetype layer reflects the size
and composition of the actual Vienna building stock while remaining
computationally tractable for subsequent calibration and district-heating
dispatch optimization.

The resulting district-heating demand was derived from the annual total building
heat demand and the assumed district-heating connection share, and was
subsequently decomposed into space-heating and domestic-hot-water components.
Since the original heat-demand input was treated as annual total building heat
demand, the separation was required to distinguish between thermally flexible
space-heating demand and non-flexible hot-water demand within the building stock
model. For the residential sector, annual domestic-hot-water demand was derived
from a floor-area-based intensity:

\[
Q_{\mathrm{DHW}}^{\mathrm{res}} = A^{\mathrm{res}} I_{\mathrm{DHW}},
\]

where \(I_{\mathrm{DHW}}\) denotes the assumed annual domestic-hot-water
intensity in \(\mathrm{kWh\,m^{-2}\,a^{-1}}\). Residential annual space-heating
demand was then obtained as

\[
Q_{\mathrm{SH}}^{\mathrm{res}} =
Q_{\mathrm{heat}}^{\mathrm{res}} - Q_{\mathrm{DHW}}^{\mathrm{res}}.
\]

For the current non-residential V1 representation, domestic hot water was not
modeled explicitly, so that

\[
Q_{\mathrm{DHW}}^{\mathrm{nonres}} = 0, \qquad
Q_{\mathrm{SH}}^{\mathrm{nonres}} = Q_{\mathrm{heat}}^{\mathrm{nonres}}.
\]

## EnergyPlus Teacher and Reduced-Order Calibration

The high-fidelity teacher layer is based on offline EnergyPlus simulations. The
teacher is not used as the online dispatch model. Its role is to identify a
reduced representation that preserves the building dynamics most relevant for DH
dispatch decisions, namely heat-loss behavior, effective thermal inertia,
preheating potential, cutback potential, rebound, and recovery
([M6](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Sources/building_calibration_quellen.md)).

The calibration workflow consists of three linked steps. First, weather,
archetype, and experiment inputs are prepared for the teacher simulations.
Second, reduced-order thermal parameters such as effective total loss
coefficient, effective heat capacity, and thermal time constant are fitted from
the teacher outputs. Third, event-response quantities such as preheat energy,
cutback energy, rebound energy, and recovery duration are fitted and exported
for later runtime use
([M6](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Sources/building_calibration_quellen.md),
[M8](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Data/thermal_archetypes/Vienna/calibrated_v1.py)).

This teacher-to-reduced-order bridge is central to the paper. It avoids treating
buildings as purely static heat sinks, but also avoids embedding a full
simulation model inside the dispatch optimization. The resulting reduced-order
representation is therefore intended as a decision-relevant approximation of
building flexibility rather than as a generic thermal-comfort simulator.

The hourly reference space-heating demand of each cohort was then derived with a
stateful reduced-order building model. In the active runtime representation, the
indoor temperature evolves as a first-order energy balance driven by heat losses,
internal gains, solar gains, and heating input:

\[
T_{i,t+1} =
T_{i,t} + \frac{-U_i (T_{i,t} - T_t^{\mathrm{out}})
+ G_{i,t}^{\mathrm{int}} + G_{i,t}^{\mathrm{sol}} + 1000\,q_{i,t}^{\mathrm{heat}}}{C_i},
\]

where \(T_{i,t}\) is the indoor temperature of cohort \(i\) at hour \(t\),
\(U_i\) is the effective total loss coefficient in \(\mathrm{W\,K^{-1}}\),
\(C_i\) is the effective heat capacity in \(\mathrm{Wh\,K^{-1}}\),
\(T_t^{\mathrm{out}}\) is outdoor temperature, \(G_{i,t}^{\mathrm{int}}\) and
\(G_{i,t}^{\mathrm{sol}}\) are internal and solar gains in W, and
\(q_{i,t}^{\mathrm{heat}}\) is the delivered heating energy in
\(\mathrm{kWh\,h^{-1}}\). The hourly heating demand is therefore the amount of
heat required to keep the indoor temperature within the comfort band around the
prescribed reference setpoint.

More specifically, heating is activated when the indoor temperature falls below
the lower hysteresis bound of the reference setpoint and remains active until
the upper bound is reached. The delivered hourly heat is thus computed as

\[
q_{i,t}^{\mathrm{heat}} =
\min \left(
\max \left(0,\,(T_{i,t}^{\mathrm{up}} - T_{i,t}^{\ast}) C_i \right),
q_{i}^{\mathrm{heat,max}}
\right) / 1000,
\]

where \(T_{i,t}^{\ast}\) is the free-running indoor temperature after losses and
gains, \(T_{i,t}^{\mathrm{up}}\) is the upper hysteresis temperature associated
with the active setpoint, and \(q_i^{\mathrm{heat,max}}\) is the maximum
admissible heating energy per hour. This formulation ensures that older
cohorts, which have higher effective loss coefficients and lower thermal
performance, produce higher hourly heating requirements than newer cohorts under
the same weather and control conditions. The district-heating demand of the
stock is then obtained by aggregating the cohort-level heating and hot-water
loads:

\[
q_t^{\mathrm{DH,tot}} = \sum_i
\left(q_{i,t}^{\mathrm{SH}} + q_{i,t}^{\mathrm{DHW}}\right).
\]

## Thermflex Formulation

Thermal flexibility is represented through explicit comfort, duration, event, and
event-response bounds. In the constant-control cases used for the core
comparisons, the main global policy parameters are `constant_setpoint_c`,
`constant_lower_bound_c`, `max_flex_duration_h`, `max_flex_events_per_day`, and
`constrain_upper_temperature`
([M9](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Settings/technical/heating_control.py),
[M10](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Settings/constraints/thermflex.py)).
These global settings define the admissible operating envelope of the policy,
while cohort-specific teacher-derived bounds restrict what is physically usable
for each cohort
([M8](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Data/thermal_archetypes/Vienna/calibrated_v1.py)).

At dispatch level, thermflex modifies the thermal demand seen by the DH system.
In simplified form, the coupling can be written as

\[
D_t^{\mathrm{heat}} =
D_t^{\mathrm{base}} + \Delta_t^{\mathrm{preheat}}
- \Delta_t^{\mathrm{cutback}} + \Delta_t^{\mathrm{rebound}},
\]

where \(D_t^{\mathrm{base}}\) is the baseline cohort-aggregated heat demand,
\(\Delta_t^{\mathrm{preheat}}\) denotes additional heat intake ahead of a flex
event, \(\Delta_t^{\mathrm{cutback}}\) denotes temporarily avoided demand during
a flex event, and \(\Delta_t^{\mathrm{rebound}}\) captures the later recovery of
the building state.
The active flexibility signal is constrained by both global policy parameters and
cohort-specific event-response envelopes.

To keep the policy physically and operationally interpretable, the number of
event starts and their duration are bounded:

\[
\sum_{t \in T} y_t \le N^{\mathrm{max}}_{\mathrm{events}},
\]

\[
\ell_e \le H^{\mathrm{max}}_{\mathrm{flex}} \qquad \forall e,
\]

where \(y_t\) is an event-start indicator and \(\ell_e\) is the duration of
event e. The case naming used throughout the analysis encodes these policy
parameters directly. For example, `lb21p0_dur24_evt1` denotes a constant-control
case with a lower comfort bound of `21.0 C`, a maximum flex duration of `24 h`,
and at most one event start per day
([M1](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Papers/dh_thermflex_vienna.md)).

## Deterministic Day-Ahead Dispatch

The primary truth path of the paper is the deterministic `milp_day_ahead`
dispatch. It is used for the isolated no-thermflex versus thermflex comparison,
for the policy sensitivity over lower bound, duration, and event settings, for
the representative-day comparison, and for the cohort-level mechanism analysis
([M1](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Papers/dh_thermflex_vienna.md)).
This path is not claimed to be the universal final operations model for all
future use cases. It is the main paper path because it is stable, interpretable,
and strong enough for the core mechanism claims.

In compact form, the deterministic dispatch minimizes operating, import, and
penalty costs over the planning horizon:

\[
\min \sum_{t \in T}
\left(C_t^{\mathrm{gen}} + C_t^{\mathrm{import}} + C_t^{\mathrm{penalty}}\right).
\]

The central DH balance can be summarized as

\[
\sum_{u \in U} Q_{u,t}^{\mathrm{gen}}
+ Q_t^{\mathrm{discharge}} - Q_t^{\mathrm{charge}} + Q_t^{\mathrm{unserved}}
= D_t^{\mathrm{heat}},
\]

where \(Q_{u,t}^{\mathrm{gen}}\) is the heat generation of technology \(u\),
\(Q_t^{\mathrm{discharge}}\) and \(Q_t^{\mathrm{charge}}\) represent storage
interaction, \(Q_t^{\mathrm{unserved}}\) is penalized unmet demand, and
\(D_t^{\mathrm{heat}}\) is the
thermflex-adjusted demand introduced above. Technology-specific capacity,
storage, and commitment constraints are handled in the detailed dispatch model,
but the paper focuses on the role of the building-side flexibility signal within
that system balance.

## Representative-Day Analysis

To avoid over-interpreting a single day, the paper uses a representative-day
selection step based on Vienna 2023 reference data. The day set combines
rule-based extremes and medoid-like typical days. The active day types are
winter peak heat day, winter price spike day, winter sunny heat day, winter
typical day, and shoulder typical day
([M11](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/run/results/Vienna/gold/dh_thermflex_run_20260403_140316/representative_days/representative_days.md),
[M15](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/run/results/Vienna/gold/constant_thermflex_representative_day_summary_20260403/representative_day_case_summary.md)).

The selection is based on aggregated daily features including DH demand, outdoor
temperature, solar-related proxies, and market variables. The purpose of this
layer is not to replace annual analysis. Instead, representative days act as a
mechanism and policy screen that reveals whether a thermflex setting is robust
across materially different operating contexts. This is especially important in
the present case, because the system value of thermflex is strongly day-type
dependent.

## Historical Two-Stage Robustness Layer

To move beyond a single deterministic day, the paper additionally uses
`milp_two_stage` as a historical robustness check. Its role is not to replace
the deterministic search path, but to test whether promising design and policy
points remain relevant when re-optimized against a reduced set of historical
uncertainty scenarios
([M1](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Papers/dh_thermflex_vienna.md),
[M12](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/dispatch/scenarios/historical_data.py)).

In this paper, a candidate means the same design and policy point, not the same
hourly dispatch schedule. The two-stage problem is formulated as an expected-value
scenario model with first-stage decisions \(x\) and scenario-dependent recourse:

\[
\min \; c^\top x + \sum_{\omega \in \Omega} p_\omega Q(x,\omega),
\]

where \(p_\omega\) is the probability of scenario \(\omega\) and \(Q(x,\omega)\)
is the second-stage operating cost for that scenario. This layer is therefore
better described as a scenario-based historical expected-value robustness check
than as a generic robust optimization model.

The scenario library is built from aligned historical weather, price, and
system-level driver series
([M12](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/dispatch/scenarios/historical_data.py)).
Scenario features and reduction settings are explicitly driven by the dispatch
configuration
([M3](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Settings/dispatch/dispatch.py)).
The active default reduction feature space is
`ambient_temperature_c`, `grid_import_price`,
`district_space_heat_demand`, and `co2_price_eur_per_tco2`, and the feature
distance metric is passed explicitly into the reduction workflow rather than
being a decorative setting
([M13](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/dispatch/scenarios/historical.py),
[M14](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/dispatch/scenarios/reduction.py)).

At the present paper stage, this two-stage path is methodologically important
but still secondary to `milp_day_ahead`. The current evidence is sufficient to
state that the historical two-stage bridge is operational and can support a
compact robustness claim, but it is not the primary search and interpretation
layer of the manuscript
([M17](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Papers/thermflex_paper/results/03_two_stage_results.md)).

## Surrogate-Assisted Exploration

The paper also uses a surrogate-assisted exploration layer to accelerate search
and candidate ranking. Its role is supportive rather than evidential. The
current strongest paper-relevant slice uses an `xgb` surrogate trained on a
limited teacher sample, with a feasible/infeasible split that is itself
informative about the admissible design space
([M16](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Papers/thermflex_paper/results/06_surrogate_status.md)).

Methodologically, this surrogate is useful because it predicts several
dispatch-mix and emissions targets reasonably well, which makes it suitable for
exploration and pre-screening. However, its holdout quality is currently weak on
some of the most paper-facing targets, especially operating cost and shifted heat
([M16](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Papers/thermflex_paper/results/06_surrogate_status.md)).
For that reason, surrogate outputs are used here to support search acceleration
and candidate ranking, not to replace gold-run evaluation for the main claims.

## Evaluation Metrics

The paper focuses on a compact KPI set that captures operational,
environmental, and thermflex-specific effects:

- `dispatch_operating_cost_eur`
- `co2_emissions_total_t`
- `dh_unserved_heat_kwh`
- `thermflex_shifted_space_heat_kwh`
- `thermflex_rebound_kwh`
- `thermflex_peak_change_kw`

This KPI set is chosen because thermal flexibility in the present case cannot be
reduced to a single operating-cost outcome. `dispatch_operating_cost_eur` captures
direct operating consequences, while `co2_emissions_total_t` tracks environmental
effects of changed technology use. `dh_unserved_heat_kwh` reflects service
adequacy under system stress. `thermflex_shifted_space_heat_kwh`,
`thermflex_rebound_kwh`, and `thermflex_peak_change_kw` are needed because the
operational value of thermflex often appears through timing, rebound, and peak
relief rather than through universal cost reductions alone
([M15](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/run/results/Vienna/gold/constant_thermflex_representative_day_summary_20260403/representative_day_case_summary.md)).

## Source Basis

- [M1] paper scope note:
[dh_thermflex_vienna.md](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Papers/dh_thermflex_vienna.md)
- [M2] Vienna and dispatch source notes:
[wien_und_dispatch_quellen.md](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Sources/wien_und_dispatch_quellen.md)
- [M3] dispatch settings:
[dispatch.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Settings/dispatch/dispatch.py)
- [M4] Vienna building stock:
[building_stock.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Data/building_stock/Vienna/building_stock.py)
- [M5] Vienna thermal archetypes:
[thermal_archetypes.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Data/thermal_archetypes/Vienna/thermal_archetypes.py)
- [M6] building calibration source notes:
[building_calibration_quellen.md](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Sources/building_calibration_quellen.md)
- [M7] Vienna building appendix:
[vienna_building_model_parameters_appendix.md](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Appendices/vienna_building_model_parameters_appendix.md)
- [M8] calibrated Vienna archetypes:
[calibrated_v1.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Data/thermal_archetypes/Vienna/calibrated_v1.py)
- [M9] heating control settings:
[heating_control.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Settings/technical/heating_control.py)
- [M10] thermflex constraint settings:
[thermflex.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Settings/constraints/thermflex.py)
- [M11] representative-day definition:
[representative_days.md](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/run/results/Vienna/gold/dh_thermflex_run_20260403_140316/representative_days/representative_days.md)
- [M12] historical scenario data builder:
[historical_data.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/dispatch/scenarios/historical_data.py)
- [M13] historical scenario builder:
[historical.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/dispatch/scenarios/historical.py)
- [M14] scenario reduction:
[reduction.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/dispatch/scenarios/reduction.py)
- [M15] representative-day result summary:
[representative_day_case_summary.md](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/run/results/Vienna/gold/constant_thermflex_representative_day_summary_20260403/representative_day_case_summary.md)
- [M16] surrogate status:
[06_surrogate_status.md](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Papers/thermflex_paper/results/06_surrogate_status.md)
- [M17] two-stage robustness summary:
[03_two_stage_results.md](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Papers/thermflex_paper/results/03_two_stage_results.md)

