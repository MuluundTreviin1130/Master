from __future__ import annotations

"""Central target matrix for the current surrogate stack.

Why this exists:
- the repo now has multiple learning layers with different row semantics,
- the user explicitly wants the models improved on their own terms, not only
  through paper-specific tables or figures,
- we therefore keep one explicit target matrix that states which layer is
  responsible for which KPI family and what the current preferred path is.

This module is intentionally static and explicit:
- it does not auto-discover models,
- it does not silently infer preferred paths from filenames,
- it is a lightweight SSOT for current learning intent and target ownership.
"""

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class TargetMatrixEntry:
    layer: str
    family: str
    target_group: str
    primary_targets: tuple[str, ...]
    current_role: str
    preferred_model_id: str | None
    preferred_postprocessor_profile: str | None
    notes: str


TARGET_MATRIX: tuple[TargetMatrixEntry, ...] = (
    TargetMatrixEntry(
        layer="thermflex_system_results",
        family="dispatch_kpi_paper",
        target_group="system_cost_co2_core",
        primary_targets=(
            "dispatch_heat_operating_cost_eur",
            "fuel_cost_eur",
            "co2_cost_eur",
            "co2_emissions_total_t",
        ),
        current_role="primary",
        preferred_model_id="thermflex_system_results_xgb_dispatch_kpi_paper_612be5461a30",
        preferred_postprocessor_profile=None,
        notes=(
            "Preferred path for aggregated system KPIs, especially cost/CO2/sum-like "
            "outputs. This path is already strong and should not be destabilized by "
            "hourly mechanism experiments."
        ),
    ),
    TargetMatrixEntry(
        layer="thermflex_daily_results",
        family="daily_kpi_core",
        target_group="day_level_cost_co2_boiler",
        primary_targets=(
            "dispatch_operating_cost_pct_change",
            "co2_emissions_total_pct_change",
            "district_gas_boiler_peak_kw_delta",
            "district_gas_boiler_generation_kwh_delta",
        ),
        current_role="primary",
        preferred_model_id="thermflex_daily_results_xgb_table_09_paper_29cc229d5820",
        preferred_postprocessor_profile=None,
        notes=(
            "Daily path is the home for generic day-level KPI deltas. Cost is already "
            "strong here, CO2 and boiler are usable but still improvable."
        ),
    ),
    TargetMatrixEntry(
        layer="thermflex_daily_results",
        family="daily_mechanism_direct",
        target_group="day_level_shifted_rebound",
        primary_targets=(
            "thermflex_shifted_space_heat_kwh",
            "thermflex_rebound_kwh",
        ),
        current_role="secondary",
        preferred_model_id="thermflex_daily_results_xgb_shifted_rebound_only_2b65d41fa479",
        preferred_postprocessor_profile=None,
        notes=(
            "Useful for diagnosis only. Current evidence says the direct daily path is "
            "not the preferred final home for the actual mechanism quantities."
        ),
    ),
    TargetMatrixEntry(
        layer="thermflex_hourly_mechanism",
        family="day_night_only",
        target_group="hourly_mechanism_day_night",
        primary_targets=(
            "thermflex_shifted_space_heat_kwh",
            "thermflex_rebound_kwh",
            "thermflex_peak_change_kw",
        ),
        current_role="primary",
        preferred_model_id="thermflex_hourly_mechanism_xgb_mechanism_energy_intensive_9a6779e1b8e6",
        preferred_postprocessor_profile=None,
        notes=(
            "Solved family for hourly mechanism. Preferred path whenever the regime is "
            "day-night thermflex."
        ),
    ),
    TargetMatrixEntry(
        layer="thermflex_hourly_mechanism",
        family="constant_evt24_lower_relax_only",
        target_group="hourly_mechanism_lower_relax",
        primary_targets=(
            "thermflex_shifted_space_heat_kwh",
            "thermflex_rebound_kwh",
            "thermflex_peak_change_kw",
        ),
        current_role="primary",
        preferred_model_id="thermflex_hourly_mechanism_xgb_mechanism_energy_intensive_4335e9b1c5cd",
        preferred_postprocessor_profile="lower_relax_evt24_conservative_v1",
        notes=(
            "Preferred lower-relax hourly mechanism path. Shifted and peak are already "
            "strong. Rebound currently requires the explicit "
            "`lower_relax_evt24_conservative_v1` rebound postprocessor."
        ),
    ),
    TargetMatrixEntry(
        layer="thermflex_hourly_mechanism",
        family="constant_evt24_lower_relax_tau4_only",
        target_group="hourly_mechanism_lower_relax_tau4",
        primary_targets=(
            "thermflex_shifted_space_heat_kwh",
            "thermflex_rebound_kwh",
            "thermflex_peak_change_kw",
        ),
        current_role="candidate",
        preferred_model_id="thermflex_hourly_mechanism_xgb_mechanism_energy_intensive_74d382eb0b73",
        preferred_postprocessor_profile="tau4_lower_relax_shifted_daily_state_xgb_v1",
        notes=(
            "Tau4-specific lower-relax candidate trained on the expanded 27-day "
            "truth basis with month-stratified grouped holdout. The shifted KPI "
            "uses the explicit daily state-XGB shifted postprocessor; rebound is "
            "best kept raw for this candidate. Peak remains the open KPI gap."
        ),
    ),
    TargetMatrixEntry(
        layer="thermflex_hourly_mechanism",
        family="constant_evt24_upper_only",
        target_group="hourly_mechanism_upper_only",
        primary_targets=(
            "thermflex_shifted_space_heat_kwh",
            "thermflex_rebound_kwh",
            "thermflex_peak_change_kw",
        ),
        current_role="experimental",
        preferred_model_id="thermflex_hourly_mechanism_xgb_mechanism_energy_intensive_dea7aac98eb2",
        preferred_postprocessor_profile=None,
        notes=(
            "Still truth-limited. Current evidence says further postprocessing on the "
            "existing truth is not the main lever; new independent truth days are more "
            "important."
        ),
    ),
    TargetMatrixEntry(
        layer="thermflex_hourly_mechanism",
        family="constant_evt24_only",
        target_group="hourly_peak_mixed_evt24",
        primary_targets=("thermflex_peak_change_kw",),
        current_role="primary",
        preferred_model_id="thermflex_hourly_mechanism_xgb_mechanism_energy_intensive_f8ac31dca29b",
        preferred_postprocessor_profile="mixed_evt24_peak_negative_scale_v1",
        notes=(
            "Treat the mixed evt24 slice as a peak-focused path. The explicit "
            "`mixed_evt24_peak_negative_scale_v1` peak postprocessor currently lifts "
            "holdout peak fit while shifted/rebound remain too heterogeneous."
        ),
    ),
    TargetMatrixEntry(
        layer="thermflex_hourly_mechanism",
        family="active_paper_hourly_outputs",
        target_group="hourly_dh_and_state_paths",
        primary_targets=(
            "hourly_dh_heat_demand_path",
            "hourly_indoor_temperature_path",
        ),
        current_role="gap",
        preferred_model_id=None,
        preferred_postprocessor_profile=None,
        notes=(
            "Active paper figures and comfort tables need reusable hourly demand/state "
            "paths, not only reaggregated daily KPIs. No preferred production model is "
            "registered yet; keep this gap visible when improving the hourly surrogate."
        ),
    ),
    TargetMatrixEntry(
        layer="thermflex_hourly_mechanism",
        family="active_paper_hourly_dispatch",
        target_group="hourly_source_dispatch_stack",
        primary_targets=("hourly_source_dispatch_stack",),
        current_role="gap",
        preferred_model_id=None,
        preferred_postprocessor_profile=None,
        notes=(
            "Dispatch-stack figures currently rely on Gold/replay CSV artifacts. A "
            "future surrogate contract should either learn the source stack directly or "
            "derive it from a validated low-dimensional dispatch response model."
        ),
    ),
    TargetMatrixEntry(
        layer="families",
        family="thermflex_policy_state_axes",
        target_group="family_and_state_drivers",
        primary_targets=(
            "policy_tau_h",
            "policy_duration_h",
            "policy_upper_lower_relaxation",
            "residential_cohort_axis",
            "weather_state_features",
        ),
        current_role="supporting_axis",
        preferred_model_id=None,
        preferred_postprocessor_profile=None,
        notes=(
            "These are not standalone prediction targets, but they are mandatory "
            "family/state axes for day-specific and hourly KPI quality. Tau, duration, "
            "relaxation regime, cohort mix, and weather/state features must stay "
            "explicit in datasets and holdout grouping instead of being folded into "
            "unlabeled mixed training pools."
        ),
    ),
)


def iter_target_matrix() -> Iterable[TargetMatrixEntry]:
    yield from TARGET_MATRIX


def find_entries_by_target(target: str) -> tuple[TargetMatrixEntry, ...]:
    """Return every explicit ownership entry for one exact target name.

    The lookup is deliberately strict:
    - no fuzzy matching,
    - no alias fallback,
    - callers must use the canonical target column name.
    """

    return tuple(
        entry
        for entry in TARGET_MATRIX
        if target in entry.primary_targets
    )


def get_primary_entry_for_target(target: str) -> TargetMatrixEntry:
    """Return the single primary owner for one exact target name.

    Fail fast on:
    - missing ownership,
    - ambiguous primary ownership.
    """

    matches = tuple(
        entry
        for entry in find_entries_by_target(target)
        if entry.current_role == "primary"
    )
    if not matches:
        raise KeyError(
            f"No primary target-matrix entry registered for target '{target}'."
        )
    if len(matches) > 1:
        raise ValueError(
            f"Multiple primary target-matrix entries registered for target '{target}'."
        )
    return matches[0]
