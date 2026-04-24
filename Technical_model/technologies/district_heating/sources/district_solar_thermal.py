from __future__ import annotations

from functools import lru_cache
from typing import Any, Dict

import numpy as np
import pandas as pd
from oemof.thermal import solar_thermal_collector as solar_thermal_collector_oemof
from pvlib import irradiance as pvlib_irradiance
from pvlib import solarposition as pvlib_solarposition


CP_WATER_KJ_PER_KG_K = 4.186


def _require_config_value(config: Any, attr: str) -> float:
    if config is None or not hasattr(config, attr):
        raise ValueError(f"[district_solar_thermal] Missing required config attribute '{attr}'.")
    value = getattr(config, attr)
    if value is None:
        raise ValueError(f"[district_solar_thermal] Config attribute '{attr}' must not be None.")
    return float(value)


def _require_config_string(config: Any, attr: str) -> str:
    if config is None or not hasattr(config, attr):
        raise ValueError(f"[district_solar_thermal] Missing required config attribute '{attr}'.")
    value = getattr(config, attr)
    if value is None:
        raise ValueError(f"[district_solar_thermal] Config attribute '{attr}' must not be None.")
    out = str(value).strip()
    if not out:
        raise ValueError(f"[district_solar_thermal] Config attribute '{attr}' must not be empty.")
    return out


def _require_supported_config_string(config: Any, attr: str, *, expected: str) -> str:
    value = _require_config_string(config, attr)
    if value != expected:
        raise ValueError(
            f"[district_solar_thermal] Unsupported {attr}='{value}'. "
            f"Only '{expected}' is supported in the current production path."
        )
    return value


def _collector_area_m2(installed_kw_th: float, specific_nominal_capacity_kw_per_m2: float) -> float:
    if specific_nominal_capacity_kw_per_m2 <= 0.0:
        raise ValueError("[district_solar_thermal] specific_nominal_capacity_kw_per_m2 must be > 0.")
    return float(installed_kw_th) / float(specific_nominal_capacity_kw_per_m2)


def _resolve_flat_plate_config(config: Any) -> dict[str, float | str]:
    collector_model = _require_supported_config_string(config, "collector_model", expected="oemof_flat_plate")
    irradiance_input_type = _require_supported_config_string(config, "irradiance_input_type", expected="ghi")
    irradiance_decomposition_model = _require_supported_config_string(
        config,
        "irradiance_decomposition_model",
        expected="erbs",
    )
    temp_collector_inlet_mode = _require_supported_config_string(
        config,
        "temp_collector_inlet_mode",
        expected="dh_return_bus",
    )
    if collector_model != "oemof_flat_plate" or irradiance_input_type != "ghi" or irradiance_decomposition_model != "erbs":
        raise AssertionError("[district_solar_thermal] Unsupported solar-thermal configuration unexpectedly passed validation.")
    if temp_collector_inlet_mode != "dh_return_bus":
        raise AssertionError("[district_solar_thermal] Unsupported temp_collector_inlet_mode unexpectedly passed validation.")
    return {
        "collector_model": collector_model,
        "irradiance_input_type": irradiance_input_type,
        "irradiance_decomposition_model": irradiance_decomposition_model,
        "temp_collector_inlet_mode": temp_collector_inlet_mode,
        "reference_latitude_deg": _require_config_value(config, "reference_latitude_deg"),
        "reference_longitude_deg": _require_config_value(config, "reference_longitude_deg"),
        "collector_tilt_deg": _require_config_value(config, "collector_tilt_deg"),
        "collector_azimuth_deg": _require_config_value(config, "collector_azimuth_deg"),
        "eta_0": _require_config_value(config, "eta_0"),
        "a_1": _require_config_value(config, "a_1"),
        "a_2": _require_config_value(config, "a_2"),
        "specific_nominal_capacity_kw_per_m2": _require_config_value(config, "specific_nominal_capacity_kw_per_m2"),
    }


@lru_cache(maxsize=65536)
def _oemof_flat_plate_density_cached(
    timestamp_iso: str,
    ghi_w_per_m2: float,
    ambient_temp_c: float,
    collector_inlet_temp_c: float,
    target_source_supply_temp_c: float,
    latitude_deg: float,
    longitude_deg: float,
    collector_tilt_deg: float,
    collector_azimuth_deg: float,
    eta_0: float,
    a_1: float,
    a_2: float,
) -> tuple[float, float, float, float, float]:
    timestamp = pd.Timestamp(timestamp_iso)
    index = pd.DatetimeIndex([timestamp])
    ghi = max(0.0, float(ghi_w_per_m2))
    if ghi <= 0.0:
        return 0.0, 0.0, 0.0, 0.0, 0.0

    ghi_series = pd.Series([ghi], index=index, dtype=float)
    ambient_series = pd.Series([float(ambient_temp_c)], index=index, dtype=float)
    inlet_series = pd.Series([float(collector_inlet_temp_c)], index=index, dtype=float)
    delta_temp_n_c = max(0.0, 0.5 * (float(target_source_supply_temp_c) - float(collector_inlet_temp_c)))

    solar_pos = pvlib_solarposition.get_solarposition(index, latitude=float(latitude_deg), longitude=float(longitude_deg))
    erbs = pvlib_irradiance.erbs(
        ghi=ghi_series,
        zenith=solar_pos["apparent_zenith"],
        datetime_or_doy=index,
    )
    dhi_series = pd.Series(erbs["dhi"], index=index, dtype=float).clip(lower=0.0).fillna(0.0)

    out = solar_thermal_collector_oemof.flat_plate_precalc(
        lat=float(latitude_deg),
        long=float(longitude_deg),
        collector_tilt=float(collector_tilt_deg),
        collector_azimuth=float(collector_azimuth_deg),
        eta_0=float(eta_0),
        a_1=float(a_1),
        a_2=float(a_2),
        temp_collector_inlet=inlet_series,
        delta_temp_n=float(delta_temp_n_c),
        irradiance_global=ghi_series,
        irradiance_diffuse=dhi_series,
        temp_amb=ambient_series,
    )

    collector_heat_w_per_m2 = max(0.0, float(out["collectors_heat"].iloc[0]))
    collector_irradiance_w_per_m2 = max(0.0, float(out["col_ira"].iloc[0]))
    effective_efficiency = max(0.0, float(out["eta_c"].iloc[0]))
    diffuse_irradiance_w_per_m2 = max(0.0, float(dhi_series.iloc[0]))
    return (
        collector_heat_w_per_m2,
        collector_irradiance_w_per_m2,
        effective_efficiency,
        diffuse_irradiance_w_per_m2,
        float(delta_temp_n_c),
    )


def _run_oemof_flat_plate_case(
    *,
    timestamp: Any,
    installed_kw_th: float,
    ghi_w_per_m2: float,
    ambient_temp_c: float,
    collector_inlet_temp_c: float,
    target_source_supply_temp_c: float,
    config: Any,
    dt_h: float,
) -> dict[str, float]:
    collector_model = _require_supported_config_string(config, "collector_model", expected="oemof_flat_plate")
    irradiance_input_type = _require_supported_config_string(config, "irradiance_input_type", expected="ghi")
    irradiance_decomposition_model = _require_supported_config_string(
        config,
        "irradiance_decomposition_model",
        expected="erbs",
    )
    temp_collector_inlet_mode = _require_supported_config_string(
        config,
        "temp_collector_inlet_mode",
        expected="dh_return_bus",
    )

    if collector_model != "oemof_flat_plate" or irradiance_input_type != "ghi" or irradiance_decomposition_model != "erbs":
        raise AssertionError("[district_solar_thermal] Unsupported solar-thermal configuration unexpectedly passed validation.")
    if temp_collector_inlet_mode != "dh_return_bus":
        raise AssertionError("[district_solar_thermal] Unsupported temp_collector_inlet_mode unexpectedly passed validation.")

    latitude_deg = _require_config_value(config, "reference_latitude_deg")
    longitude_deg = _require_config_value(config, "reference_longitude_deg")
    collector_tilt_deg = _require_config_value(config, "collector_tilt_deg")
    collector_azimuth_deg = _require_config_value(config, "collector_azimuth_deg")
    eta_0 = _require_config_value(config, "eta_0")
    a_1 = _require_config_value(config, "a_1")
    a_2 = _require_config_value(config, "a_2")
    specific_nominal_capacity_kw_per_m2 = _require_config_value(config, "specific_nominal_capacity_kw_per_m2")

    area_m2 = _collector_area_m2(installed_kw_th, specific_nominal_capacity_kw_per_m2)
    (
        collector_heat_w_per_m2,
        collector_irradiance_w_per_m2,
        effective_efficiency,
        diffuse_irradiance_w_per_m2,
        delta_temp_n_c,
    ) = _oemof_flat_plate_density_cached(
        timestamp_iso=pd.Timestamp(timestamp).isoformat(),
        ghi_w_per_m2=float(ghi_w_per_m2),
        ambient_temp_c=float(ambient_temp_c),
        collector_inlet_temp_c=float(collector_inlet_temp_c),
        target_source_supply_temp_c=float(target_source_supply_temp_c),
        latitude_deg=float(latitude_deg),
        longitude_deg=float(longitude_deg),
        collector_tilt_deg=float(collector_tilt_deg),
        collector_azimuth_deg=float(collector_azimuth_deg),
        eta_0=float(eta_0),
        a_1=float(a_1),
        a_2=float(a_2),
    )
    thermal_capacity_kwh = float(area_m2 * collector_heat_w_per_m2 * float(dt_h) / 1000.0)
    return {
        "thermal_capacity_kwh": float(max(0.0, thermal_capacity_kwh)),
        "collector_area_m2": float(area_m2),
        "collector_irradiance_w_per_m2": float(collector_irradiance_w_per_m2),
        "diffuse_irradiance_w_per_m2": float(diffuse_irradiance_w_per_m2),
        "effective_efficiency": float(effective_efficiency),
        "delta_temp_n_c": float(delta_temp_n_c),
    }


def precompute_district_solar_thermal_series(
    *,
    installed_kw_th: float,
    timestamps: Any,
    ghi_w_per_m2: Any,
    ambient_temp_c: Any,
    network_supply_temp_c: Any,
    network_return_temp_c: Any,
    required_direct_supply_temp_c: Any,
    required_preheat_supply_temp_c: Any,
    config: Any,
    dt_h: float = 1.0,
) -> dict[str, np.ndarray]:
    installed_kw_th = float(installed_kw_th)
    dt_h = float(dt_h)
    if installed_kw_th < 0.0:
        raise ValueError("[district_solar_thermal] installed_kw_th must be >= 0.")
    if dt_h <= 0.0:
        raise ValueError("[district_solar_thermal] dt_h must be > 0.")

    resolved = _resolve_flat_plate_config(config)
    area_m2 = _collector_area_m2(installed_kw_th, float(resolved["specific_nominal_capacity_kw_per_m2"]))

    time_index = pd.DatetimeIndex(pd.to_datetime(timestamps))
    n_steps = len(time_index)
    if n_steps == 0:
        raise ValueError("[district_solar_thermal] timestamps must not be empty.")

    def _align(values: Any, label: str) -> np.ndarray:
        arr = np.asarray(values, dtype=float).reshape(-1)
        if arr.size != n_steps:
            raise ValueError(
                f"[district_solar_thermal] {label} length mismatch: expected {n_steps}, got {arr.size}."
            )
        return arr

    ghi_arr = np.clip(_align(ghi_w_per_m2, "ghi_w_per_m2"), a_min=0.0, a_max=None)
    ambient_arr = _align(ambient_temp_c, "ambient_temp_c")
    supply_arr = _align(network_supply_temp_c, "network_supply_temp_c")
    return_arr = _align(network_return_temp_c, "network_return_temp_c")
    required_direct_arr = _align(required_direct_supply_temp_c, "required_direct_supply_temp_c")
    required_preheat_arr = _align(required_preheat_supply_temp_c, "required_preheat_supply_temp_c")

    if np.any(return_arr >= supply_arr):
        raise ValueError("[district_solar_thermal] network_return_temp_c must stay below network_supply_temp_c.")

    ghi_series = pd.Series(ghi_arr, index=time_index, dtype=float)
    ambient_series = pd.Series(ambient_arr, index=time_index, dtype=float)
    inlet_series = pd.Series(return_arr, index=time_index, dtype=float)

    solar_pos = pvlib_solarposition.get_solarposition(
        time=time_index,
        latitude=float(resolved["reference_latitude_deg"]),
        longitude=float(resolved["reference_longitude_deg"]),
    )
    erbs = pvlib_irradiance.erbs(
        ghi=ghi_series,
        zenith=solar_pos["apparent_zenith"],
        datetime_or_doy=time_index,
    )
    dhi_series = pd.Series(erbs["dhi"], index=time_index, dtype=float).clip(lower=0.0).fillna(0.0)

    direct_delta_series = pd.Series(
        np.maximum(0.0, 0.5 * (required_direct_arr - return_arr)),
        index=time_index,
        dtype=float,
    )
    preheat_delta_series = pd.Series(
        np.maximum(0.0, 0.5 * (required_preheat_arr - return_arr)),
        index=time_index,
        dtype=float,
    )

    common_kwargs = dict(
        lat=float(resolved["reference_latitude_deg"]),
        long=float(resolved["reference_longitude_deg"]),
        collector_tilt=float(resolved["collector_tilt_deg"]),
        collector_azimuth=float(resolved["collector_azimuth_deg"]),
        eta_0=float(resolved["eta_0"]),
        a_1=float(resolved["a_1"]),
        a_2=float(resolved["a_2"]),
        temp_collector_inlet=inlet_series,
        irradiance_global=ghi_series,
        irradiance_diffuse=dhi_series,
        temp_amb=ambient_series,
    )

    direct_df = solar_thermal_collector_oemof.flat_plate_precalc(
        delta_temp_n=direct_delta_series,
        **common_kwargs,
    )
    preheat_df = solar_thermal_collector_oemof.flat_plate_precalc(
        delta_temp_n=preheat_delta_series,
        **common_kwargs,
    )

    direct_capacity_kwh = np.maximum(0.0, np.asarray(direct_df["collectors_heat"], dtype=float)) * area_m2 * dt_h / 1000.0
    preheat_capacity_kwh = np.maximum(0.0, np.asarray(preheat_df["collectors_heat"], dtype=float)) * area_m2 * dt_h / 1000.0
    if np.any(preheat_capacity_kwh + 1e-9 < direct_capacity_kwh):
        idx = int(np.where(preheat_capacity_kwh + 1e-9 < direct_capacity_kwh)[0][0])
        raise ValueError(
            "[district_solar_thermal] preheat_capacity_kwh must be >= direct_capacity_kwh. "
            f"First failing step={idx}, direct={direct_capacity_kwh[idx]}, preheat={preheat_capacity_kwh[idx]}."
        )

    delta_t_network = np.maximum(0.0, supply_arr - return_arr)
    max_mass_flow_kg_per_s = np.zeros(n_steps, dtype=float)
    valid_massflow = delta_t_network > 0.0
    max_mass_flow_kg_per_s[valid_massflow] = (
        direct_capacity_kwh[valid_massflow] / (CP_WATER_KJ_PER_KG_K * delta_t_network[valid_massflow] * dt_h)
    )

    return {
        "thermal_capacity_kwh": np.asarray(direct_capacity_kwh, dtype=float),
        "direct_feed_capacity_kwh": np.asarray(direct_capacity_kwh, dtype=float),
        "preheat_capacity_kwh": np.asarray(preheat_capacity_kwh, dtype=float),
        "direct_feed_feasible": np.asarray(direct_capacity_kwh > 0.0, dtype=float),
        "preheat_feasible": np.asarray(preheat_capacity_kwh > 0.0, dtype=float),
        "direct_effective_efficiency": np.maximum(0.0, np.asarray(direct_df["eta_c"], dtype=float)),
        "preheat_effective_efficiency": np.maximum(0.0, np.asarray(preheat_df["eta_c"], dtype=float)),
        "collector_area_m2": np.full(n_steps, float(area_m2), dtype=float),
        "collector_irradiance_w_per_m2": np.maximum(0.0, np.asarray(direct_df["col_ira"], dtype=float)),
        "diffuse_irradiance_w_per_m2": np.maximum(0.0, np.asarray(dhi_series, dtype=float)),
        "direct_delta_temp_n_c": np.asarray(direct_delta_series, dtype=float),
        "preheat_delta_temp_n_c": np.asarray(preheat_delta_series, dtype=float),
        "max_mass_flow_kg_per_s": np.asarray(max_mass_flow_kg_per_s, dtype=float),
    }


def dispatch_district_solar_thermal(
    requested_thermal_kwh: float,
    installed_kw_th: float,
    irradiance_w_per_m2: float,
    config: Any,
    dt_h: float = 1.0,
    *,
    timestamp: Any,
    ambient_temp_c: float,
    required_direct_supply_temp_c: float,
    required_preheat_supply_temp_c: float,
    requested_preheat_kwh: float = 0.0,
    network_supply_temp_c: float | None = None,
    network_return_temp_c: float | None = None,
) -> Dict[str, float]:
    requested_thermal_kwh = float(requested_thermal_kwh)
    requested_preheat_kwh = float(requested_preheat_kwh)
    installed_kw_th = float(installed_kw_th)
    irradiance_w_per_m2 = float(irradiance_w_per_m2)
    dt_h = float(dt_h)
    if requested_thermal_kwh < 0.0:
        raise ValueError("[district_solar_thermal] requested_thermal_kwh must be >= 0.")
    if requested_preheat_kwh < 0.0:
        raise ValueError("[district_solar_thermal] requested_preheat_kwh must be >= 0.")
    if installed_kw_th < 0.0:
        raise ValueError("[district_solar_thermal] installed_kw_th must be >= 0.")
    if dt_h <= 0.0:
        raise ValueError("[district_solar_thermal] dt_h must be > 0.")
    if network_return_temp_c is None:
        raise ValueError("[district_solar_thermal] network_return_temp_c is required.")
    if network_supply_temp_c is None:
        raise ValueError("[district_solar_thermal] network_supply_temp_c is required.")

    direct_case = _run_oemof_flat_plate_case(
        timestamp=timestamp,
        installed_kw_th=installed_kw_th,
        ghi_w_per_m2=irradiance_w_per_m2,
        ambient_temp_c=float(ambient_temp_c),
        collector_inlet_temp_c=float(network_return_temp_c),
        target_source_supply_temp_c=float(required_direct_supply_temp_c),
        config=config,
        dt_h=dt_h,
    )
    preheat_case = _run_oemof_flat_plate_case(
        timestamp=timestamp,
        installed_kw_th=installed_kw_th,
        ghi_w_per_m2=irradiance_w_per_m2,
        ambient_temp_c=float(ambient_temp_c),
        collector_inlet_temp_c=float(network_return_temp_c),
        target_source_supply_temp_c=float(required_preheat_supply_temp_c),
        config=config,
        dt_h=dt_h,
    )
    direct_capacity_kwh = float(direct_case["thermal_capacity_kwh"])
    preheat_capacity_kwh = float(preheat_case["thermal_capacity_kwh"])
    if preheat_capacity_kwh + 1e-9 < direct_capacity_kwh:
        raise ValueError(
            "[district_solar_thermal] preheat_capacity_kwh must be >= direct_capacity_kwh. "
            f"Got direct={direct_capacity_kwh}, preheat={preheat_capacity_kwh}."
        )

    direct_feed_kwh = min(max(0.0, requested_thermal_kwh), direct_capacity_kwh)
    remaining_low_temp_kwh = max(0.0, preheat_capacity_kwh - direct_feed_kwh)
    preheat_kwh = min(max(0.0, requested_preheat_kwh), remaining_low_temp_kwh)
    storage_candidate_kwh = max(0.0, preheat_capacity_kwh - direct_feed_kwh - preheat_kwh)

    delta_t_k = 0.0
    if network_supply_temp_c is not None and network_return_temp_c is not None:
        delta_t_k = max(0.0, float(network_supply_temp_c) - float(network_return_temp_c))
    max_mass_flow_kg_per_s = 0.0
    if delta_t_k > 0.0 and direct_feed_kwh > 0.0:
        max_mass_flow_kg_per_s = direct_feed_kwh / (CP_WATER_KJ_PER_KG_K * delta_t_k * dt_h)

    return {
        "thermal_kwh": float(direct_feed_kwh + preheat_kwh),
        "thermal_capacity_kwh": float(direct_capacity_kwh),
        "direct_feed_capacity_kwh": float(direct_capacity_kwh),
        "preheat_capacity_kwh": float(preheat_capacity_kwh),
        "direct_feed_kwh": float(direct_feed_kwh),
        "preheat_kwh": float(preheat_kwh),
        "storage_candidate_kwh": float(storage_candidate_kwh),
        "thermal_spillage_kwh": 0.0,
        "direct_feed_feasible": float(direct_capacity_kwh > 0.0),
        "preheat_feasible": float(preheat_capacity_kwh > 0.0),
        "effective_efficiency": float(
            preheat_case["effective_efficiency"] if preheat_kwh > 0.0 else direct_case["effective_efficiency"]
        ),
        "max_mass_flow_kg_per_s": float(max_mass_flow_kg_per_s),
        "collector_area_m2": float(direct_case["collector_area_m2"]),
        "collector_irradiance_w_per_m2": float(direct_case["collector_irradiance_w_per_m2"]),
        "diffuse_irradiance_w_per_m2": float(direct_case["diffuse_irradiance_w_per_m2"]),
        "direct_delta_temp_n_c": float(direct_case["delta_temp_n_c"]),
        "preheat_delta_temp_n_c": float(preheat_case["delta_temp_n_c"]),
    }
