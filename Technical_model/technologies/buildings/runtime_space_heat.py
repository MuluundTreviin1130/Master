from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from Technical_model.consumption.heating_anc_cooling_consumption.heating_control import (
    active_reference_heating_setpoint_k,
    design_indoor_temp_k,
    design_outdoor_temp_k,
    design_solar_gains_w_per_m2,
    design_internal_gains_w_per_m2,
    heating_hysteresis_bounds_k,
    heating_power_mode,
    max_heating_energy_wh,
    max_heating_power_multiplier,
)
from Technical_model.technologies.buildings.runtime_building_params import get_runtime_building_params


def _require_positive_float(value: Any, *, label: str) -> float:
    value_f = float(value)
    if value_f <= 0.0:
        raise ValueError(f"[runtime_space_heat] {label} must be > 0, got {value_f}.")
    return value_f


def _seasonal_internal_gains_w_m2(*, timestamps: pd.DatetimeIndex, usage_df: pd.DataFrame) -> np.ndarray:
    """Return the active internal-gain series used by the runtime building model.

    Why this helper exists:
    - The dispatch/runtime layer still consumes one explicit hourly internal-gain
      series per building member.
    - We keep the seasonal switch identical to the existing thermflex linear path
      so the replacement stays behaviorally comparable while removing the old
      `heating_and_cooling.py` dependency.
    """

    required = ("Qi Winter W/m2", "Qi Sommer W/m2")
    missing = [col for col in required if col not in usage_df.columns]
    if missing:
        raise KeyError(
            "[runtime_space_heat] usage_df is missing required internal-gain columns: "
            + ", ".join(missing)
        )
    winter = usage_df["Qi Winter W/m2"].to_numpy(dtype=float)
    summer = usage_df["Qi Sommer W/m2"].to_numpy(dtype=float)
    if len(winter) != len(timestamps) or len(summer) != len(timestamps):
        raise ValueError(
            "[runtime_space_heat] usage profile length must match timestamps for internal-gain construction."
        )
    winter_months = np.asarray(timestamps.month.isin([10, 11, 12, 1, 2, 3, 4]), dtype=bool)
    return np.where(winter_months, winter, summer).astype(float)


def _require_runtime_solar_mode(thermal_cfg: Any) -> str:
    if thermal_cfg is None or not hasattr(thermal_cfg, "runtime_solar_gains_mode"):
        raise ValueError(
            "[runtime_space_heat] thermal settings with runtime_solar_gains_mode are required."
        )
    mode = str(getattr(thermal_cfg, "runtime_solar_gains_mode")).strip().lower()
    if mode not in {"legacy_solargains_profile", "irradiance_window_transmission"}:
        raise ValueError(
            "[runtime_space_heat] Unsupported runtime_solar_gains_mode="
            f"'{mode}'. Expected 'legacy_solargains_profile' or 'irradiance_window_transmission'."
        )
    return mode


def resolve_runtime_solar_gains_w_per_m2(
    *,
    legacy_solar_gains_w_m2,
    irradiance_w_m2,
    building_params: dict[str, Any],
    thermal_cfg: Any,
) -> np.ndarray:
    """Resolve the active runtime solar-gain series for one cohort/member.

    Why this helper exists:
    - The old runtime path consumed `Solar_gains.csv` directly as one global
      building-gain series for every cohort.
    - That file is explicitly documented as legacy and not as the active
      weather/solar SSOT for the new Vienna teacher/runtime chain.
    - The cohort runtime path therefore needs an explicit, settings-driven way
      to derive solar gains from the active irradiance profile and the cohort
      window parameters.

    What the default branch does:
    - starts from repo-local hourly global irradiance,
    - applies the cohort window-to-floor ratio,
    - applies the cohort glazing g-value,
    - applies documented TABULA common-calculation reduction factors
      (`Fsh`, `FF`, `FW`),
    - applies the existing orientation multipliers already stored with the
      runtime building params.

    This keeps the runtime solar term explicit and cohort-specific instead of
    silently reusing one legacy gain series for the whole stock.
    """

    mode = _require_runtime_solar_mode(thermal_cfg)
    legacy = np.asarray(legacy_solar_gains_w_m2, dtype=float)
    if mode == "legacy_solargains_profile":
        return legacy

    if irradiance_w_m2 is None:
        raise ValueError(
            "[runtime_space_heat] irradiance_w_m2 is required when "
            "runtime_solar_gains_mode='irradiance_window_transmission'."
        )
    irradiance = np.asarray(irradiance_w_m2, dtype=float)
    if irradiance.shape != legacy.shape:
        raise ValueError(
            "[runtime_space_heat] irradiance_w_m2 and legacy_solar_gains_w_m2 must share the same shape."
        )

    a_floor_m2 = _require_positive_float(building_params["A_floor"], label="A_floor")
    if "window_area_total_m2" in building_params:
        window_area_total_m2 = _require_positive_float(
            building_params["window_area_total_m2"],
            label="window_area_total_m2",
        )
    else:
        a_window = building_params.get("A_window")
        if not isinstance(a_window, dict) or not a_window:
            raise ValueError(
                "[runtime_space_heat] window area data is required for irradiance-based runtime solar gains."
            )
        window_area_total_m2 = _require_positive_float(
            sum(float(v) for v in a_window.values()),
            label="sum(A_window)",
        )
    g_glazing = _require_positive_float(
        building_params.get("window_g_value", building_params.get("g_glazing")),
        label="window_g_value/g_glazing",
    )

    solar_multipliers = building_params.get("solar_multipliers")
    if not isinstance(solar_multipliers, dict) or not solar_multipliers:
        raise ValueError(
            "[runtime_space_heat] solar_multipliers are required for irradiance-based runtime solar gains."
        )
    a_window = building_params.get("A_window")
    if not isinstance(a_window, dict) or not a_window:
        raise ValueError(
            "[runtime_space_heat] A_window orientation breakdown is required for irradiance-based runtime solar gains."
        )

    weighted_orientation_factor = 0.0
    for orientation, area_m2 in a_window.items():
        if orientation not in solar_multipliers:
            raise KeyError(
                "[runtime_space_heat] Missing solar multiplier for window orientation "
                f"'{orientation}'."
            )
        weighted_orientation_factor += float(area_m2) * float(solar_multipliers[orientation])
    weighted_orientation_factor /= window_area_total_m2

    frame_fraction = float(getattr(thermal_cfg, "runtime_solar_frame_fraction"))
    shading_factor = float(getattr(thermal_cfg, "runtime_solar_shading_factor"))
    non_perpendicular_factor = float(getattr(thermal_cfg, "runtime_solar_non_perpendicular_factor"))
    if not 0.0 <= frame_fraction < 1.0:
        raise ValueError(
            f"[runtime_space_heat] runtime_solar_frame_fraction must be within [0, 1), got {frame_fraction}."
        )
    for value, label in (
        (shading_factor, "runtime_solar_shading_factor"),
        (non_perpendicular_factor, "runtime_solar_non_perpendicular_factor"),
        (weighted_orientation_factor, "weighted_orientation_factor"),
    ):
        if value < 0.0:
            raise ValueError(f"[runtime_space_heat] {label} must be >= 0, got {value}.")

    solar_aperture_factor = (
        (window_area_total_m2 / a_floor_m2)
        * g_glazing
        * (1.0 - frame_fraction)
        * shading_factor
        * non_perpendicular_factor
        * weighted_orientation_factor
    )
    if solar_aperture_factor < 0.0:
        raise ValueError(
            f"[runtime_space_heat] Derived solar_aperture_factor must be >= 0, got {solar_aperture_factor}."
        )

    return np.maximum(0.0, irradiance * solar_aperture_factor).astype(float)


def derive_runtime_max_heating_power_w_per_m2(
    *,
    building_params: dict[str, Any],
    usage_df: pd.DataFrame,
    heating_control: Any,
) -> float:
    """Derive an explicit runtime heating-power cap without the legacy helper.

    Why this helper exists:
    - The old `heating_and_cooling.py` implementation mixed two responsibilities:
      building dynamics and design-power derivation.
    - The runtime path only needs a simple, explicit cap derived from the active
      calibrated total-loss coefficient and the heating-control SSOT.
    - This keeps the cap in the active teacher-derived runtime path and avoids
      silently reaching back into the deprecated module.
    """

    a_floor_m2 = _require_positive_float(building_params["A_floor"], label="A_floor")
    total_loss_w_per_k = _require_positive_float(
        building_params["effective_total_loss_coefficient_w_per_k"],
        label="effective_total_loss_coefficient_w_per_k",
    )
    mode = heating_power_mode(heating_control)
    if mode == "fixed":
        return float(max(0.0, float(heating_control.max_heating_power_w_per_m2)))

    delta_t_k = max(0.0, float(design_indoor_temp_k(heating_control) - design_outdoor_temp_k(heating_control)))
    q_design_w_per_m2 = max(
        0.0,
        (total_loss_w_per_k * delta_t_k) / a_floor_m2
        - float(design_internal_gains_w_per_m2(heating_control))
        - float(design_solar_gains_w_per_m2(heating_control)),
    )
    return float(q_design_w_per_m2 * max_heating_power_multiplier(heating_control))


def build_reference_space_heat_profile_kwh(
    *,
    timestamps,
    t_outdoor_k,
    solar_gains_w_m2,
    usage_df: pd.DataFrame,
    building_params: dict[str, Any],
    heating_control: Any,
) -> np.ndarray:
    """Build teacher-derived hourly reference space-heat demand in kWh_th.

    Why this is dynamic instead of a one-step residual:
    - A pure `max(0, losses - gains)` residual can collapse to zero whenever
      short-term gains exceed short-term losses.
    - For the Vienna cohort aggregate this created implausible winter daylight
      zero-demand hours, because the building thermal state and hysteresis were
      ignored.
    - The runtime baseline therefore needs the same kind of stateful heating
      response as the former helper: losses and gains change the indoor state,
      and heating responds when that state drops below the reference comfort
      band.

    What this helper now does:
    - uses the calibrated teacher-derived total-loss coefficient and heat
      capacity,
    - keeps the active internal-gain construction from the runtime path,
    - interprets `solar_gains_w_m2` exactly as the runtime profile already
      provides it,
    - simulates one explicit indoor-temperature trajectory with reference
      heating hysteresis,
    - returns the resulting whole-building hourly heating demand in kWh_th.
    """

    idx = pd.DatetimeIndex(pd.to_datetime(timestamps))
    if len(idx) == 0:
        raise ValueError("[runtime_space_heat] timestamps must not be empty.")

    t_outdoor_k = np.asarray(t_outdoor_k, dtype=float)
    solar_gains_w_m2 = np.asarray(solar_gains_w_m2, dtype=float)
    if len(t_outdoor_k) != len(idx) or len(solar_gains_w_m2) != len(idx):
        raise ValueError(
            "[runtime_space_heat] timestamps, outdoor temperature and solar gains must share the same length."
        )

    a_floor_m2 = _require_positive_float(building_params["A_floor"], label="A_floor")
    c_eff_wh_per_k = _require_positive_float(building_params["heat_capacity"], label="heat_capacity")
    total_loss_w_per_k = _require_positive_float(
        building_params["effective_total_loss_coefficient_w_per_k"],
        label="effective_total_loss_coefficient_w_per_k",
    )

    internal_gains_w_m2 = _seasonal_internal_gains_w_m2(timestamps=idx, usage_df=usage_df)
    # Gains stay on whole-building level because the calibrated thermal capacity
    # and total-loss coefficient are also whole-building parameters.
    internal_gains_w = internal_gains_w_m2 * a_floor_m2
    solar_gains_w = solar_gains_w_m2 * a_floor_m2

    # The reference path follows the reference heating schedule, not the active
    # thermflex schedule. That keeps `q_heat_ref_kwh` as the thermflex baseline.
    t_ref_k = np.array(
        [active_reference_heating_setpoint_k(int(ts.hour), heating_control) for ts in idx],
        dtype=float,
    )
    t_indoor_k = np.zeros(len(idx), dtype=float)
    q_heat_kwh = np.zeros(len(idx), dtype=float)

    # Start the dynamic reference trajectory at the first reference setpoint so
    # the simulation begins from a consistent occupied comfort state.
    t_indoor_k[0] = float(t_ref_k[0])
    heating_on = False

    # The heating cap must stay explicit and settings-driven. We derive the
    # design-based power once, then convert it to an hourly energy cap.
    q_heat_max_w_per_m2 = derive_runtime_max_heating_power_w_per_m2(
        building_params=building_params,
        usage_df=usage_df,
        heating_control=heating_control,
    )
    q_heat_max_wh = float(max_heating_energy_wh(a_floor_m2, 1.0, heating_control))
    if q_heat_max_w_per_m2 > 0.0:
        q_heat_max_wh = min(q_heat_max_wh, q_heat_max_w_per_m2 * a_floor_m2)

    # We intentionally mirror the old dynamic reference idea:
    # 1. propagate indoor temperature under losses/gains only,
    # 2. update hysteresis state at the reference setpoint,
    # 3. inject heating if the reference band requires it.
    for t in range(1, len(idx)):
        delta_t_k = float(t_indoor_k[t - 1] - float(t_outdoor_k[t]))

        loss_w = total_loss_w_per_k * delta_t_k
        gain_w = float(internal_gains_w[t] + solar_gains_w[t])
        net_wh = (-loss_w + gain_w) * 1.0
        t_indoor_k[t] = t_indoor_k[t - 1] + net_wh / c_eff_wh_per_k

        ref_setpoint_k = float(t_ref_k[t])
        lower_k, upper_k = heating_hysteresis_bounds_k(ref_setpoint_k, heating_control)
        if t_indoor_k[t] < lower_k:
            heating_on = True
        elif t_indoor_k[t] >= upper_k:
            heating_on = False

        if heating_on and t_indoor_k[t] < upper_k:
            q_heat_wh = min(max(0.0, (upper_k - t_indoor_k[t]) * c_eff_wh_per_k), q_heat_max_wh)
            q_heat_kwh[t] = q_heat_wh / 1000.0
            t_indoor_k[t] = min(upper_k, t_indoor_k[t] + q_heat_wh / c_eff_wh_per_k)

    return q_heat_kwh


def require_live_hvac_internal_gains_w_m2(*, timestamps, usage_df: pd.DataFrame) -> np.ndarray:
    """Return the hourly internal-gain series used by live RC HVAC.

    Why this wrapper exists:
    - Precompute, the thermflex linear model, and EnergyPlus mapping already
      switch `Qi Winter W/m2` / `Qi Sommer W/m2` by month.
    - EC_FLEX / IES heuristic HVAC previously kept winter Qi all year and
      silently used `0.0` when the winter column was missing.
    - Live Gold/teacher heating therefore did not share the runtime SSOT.
    """

    idx = pd.DatetimeIndex(timestamps)
    return _seasonal_internal_gains_w_m2(timestamps=idx, usage_df=usage_df)


def build_live_hvac_solar_gains_member_2d(
    *,
    profiles: dict[str, Any],
    members: Any,
    settings_obj: Any,
    n_steps: int,
    n_members: int,
) -> np.ndarray:
    """Resolve per-member solar gains for live RC HVAC from the runtime SSOT.

    Why this helper exists:
    - Default `thermal.runtime_solar_gains_mode` is `irradiance_window_transmission`.
    - Precompute already derives cohort-specific W/m2 gains from irradiance,
      window geometry, g-value, and TABULA reduction factors.
    - Live EC_FLEX / IES heuristic HVAC previously injected the global legacy
      `solargains` profile into every member. That file is documented as not
      being the active solar SSOT and is several times larger than the
      settings-selected term (Vienna mean ~9.6 vs ~2.5 W/m2 for residential).
    - Gold/teacher default `system_id='ec_flex'` with `district_heating.share=0`
      takes all space-heat electricity from this live RC path, so the mismatch
      directly biases HVAC electricity, grid import, NPC, and climate_change.

    Resolution order:
    1. Reuse `profiles['space_heat_solar_member_2d']` when precompute already
       built the SSOT series for this member axis.
    2. Otherwise resolve each member with `resolve_runtime_solar_gains_w_per_m2`.
    Missing members, shape drift, or irradiance-mode gaps fail fast.
    """

    n_steps = int(n_steps)
    n_members = int(n_members)
    if n_steps <= 0:
        raise ValueError("[runtime_space_heat] n_steps must be > 0 for live HVAC solar gains.")
    if n_members < 0:
        raise ValueError("[runtime_space_heat] n_members must be >= 0 for live HVAC solar gains.")
    if n_members == 0:
        return np.zeros((n_steps, 0), dtype=float)

    cached = profiles.get("space_heat_solar_member_2d") if isinstance(profiles, dict) else None
    if cached is not None:
        arr = np.asarray(cached, dtype=float)
        if arr.ndim != 2 or arr.shape != (n_steps, n_members):
            raise ValueError(
                "[runtime_space_heat] profiles['space_heat_solar_member_2d'] must have shape "
                f"({n_steps}, {n_members}), got {arr.shape}."
            )
        return arr

    if settings_obj is None or not hasattr(settings_obj, "thermal"):
        raise ValueError(
            "[runtime_space_heat] settings_obj.thermal is required to resolve live HVAC solar gains."
        )
    member_rows = getattr(members, "members", None) if members is not None else None
    if not member_rows:
        raise ValueError(
            "[runtime_space_heat] engine members are required to resolve per-member live HVAC solar gains. "
            "The global legacy solargains profile is not an allowed fallback when "
            "runtime_solar_gains_mode is settings-selected."
        )
    if "solargains" not in profiles:
        raise KeyError("[runtime_space_heat] profiles['solargains'] is required as the legacy solar input.")

    out = np.zeros((n_steps, n_members), dtype=float)
    col = 0
    for member in member_rows:
        count = int(getattr(member, "count", 0))
        if count <= 0:
            continue
        building_params = get_runtime_building_params(member, settings_obj=settings_obj)
        series = np.asarray(
            resolve_runtime_solar_gains_w_per_m2(
                legacy_solar_gains_w_m2=profiles["solargains"],
                irradiance_w_m2=profiles.get("irradiance"),
                building_params=building_params,
                thermal_cfg=settings_obj.thermal,
            ),
            dtype=float,
        ).reshape(-1)
        if series.size != n_steps:
            raise ValueError(
                "[runtime_space_heat] Resolved live HVAC solar series length "
                f"{series.size} does not match n_steps={n_steps}."
            )
        for _ in range(count):
            if col >= n_members:
                raise ValueError(
                    "[runtime_space_heat] Member expansion exceeds live HVAC member axis "
                    f"n_members={n_members}."
                )
            out[:, col] = series
            col += 1
    if col != n_members:
        raise ValueError(
            "[runtime_space_heat] Member expansion produced "
            f"{col} live HVAC solar columns, expected n_members={n_members}."
        )
    return out
