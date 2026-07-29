from __future__ import annotations

"""Unified EC_FLEX system runner.

Design intent:
- Single system model controlled by feature toggles.
- Full-year timestep simulation with in-loop thermal and hydrogen states.
- Additive output keys; legacy key names are preserved where possible.
"""

from typing import Any, Dict, Tuple

import numpy as np
import pandas as pd

from dispatch.policies.ec_first_policy import allocate_deficit, allocate_surplus
from Data.technology_data.run_of_river_hydro.Vienna.vienna import (
    VIENNA_RUN_OF_RIVER_ANNUAL_GENERATION_GWH,
    VIENNA_RUN_OF_RIVER_INSTALLED_KW,
    load_freudenau_hourly_flow_proxy_context,
)
from Technical_model.technologies.buildings.thermal_building_state import (
    ThermalBuildingState,
    smooth_effective_outdoor_temperature,
)
from Technical_model.technologies.buildings.runtime_building_params import get_runtime_building_params
from Technical_model.technologies.buildings.thermal_flex_controller import thermflex_extra_cap_kwh
from Technical_model.technologies.electricity.large_wind import simulate_large_wind_generation
from Technical_model.technologies.electricity.run_of_river_hydro import simulate_run_of_river_hydro_generation
from Technical_model.technologies.electricity.small_wind import simulate_small_wind_generation
from Technical_model.technologies.gas_and_fuels.biogas_engine import dispatch_biogas_engine
from Technical_model.technologies.gas_and_fuels.wood_gasifier import dispatch_wood_gasifier
from Technical_model.technologies.hydrogen.hydrogen_system import HydrogenSystem


def _u_a(building: Dict[str, Any]) -> float:
    if "effective_total_loss_coefficient_w_per_k" not in building:
        raise KeyError("[EC_FLEX] building params must contain 'effective_total_loss_coefficient_w_per_k'.")
    value = float(building["effective_total_loss_coefficient_w_per_k"])
    if value <= 0.0:
        raise ValueError(f"[EC_FLEX] effective_total_loss_coefficient_w_per_k must be > 0, got {value}.")
    return value


def _distribute(total_kwh: float, caps: np.ndarray) -> np.ndarray:
    caps = np.asarray(caps, dtype=float)
    out = np.zeros_like(caps)
    rem = max(0.0, float(total_kwh))
    order = np.argsort(-caps)
    for idx in order:
        if rem <= 0:
            break
        give = min(rem, max(0.0, caps[idx]))
        out[idx] = give
        rem -= give
    return out


def _align_1d_length(values: Any, n_steps: int, fill_value: float = 0.0) -> np.ndarray:
    """Require an exact-horizon 1D series.

    Silent truncate/pad previously corrupted inputs on length mismatch.
    ``fill_value`` is retained only for call-site compatibility and is unused.
    """

    del fill_value
    arr = np.asarray(values, dtype=float).reshape(-1)
    expected = int(n_steps)
    if arr.size != expected:
        raise ValueError(f"[EC_FLEX] 1D series length mismatch: got {arr.size}, expected {expected}.")
    return arr


def _require_wind_series(values: Any, n_steps: int, *, label: str) -> np.ndarray:
    """Require a wind series that matches the simulation horizon.

    Some Geosphere-style archives include one exclusive endpoint sample
    (``n_steps + 1``). That single trailing sample may be trimmed explicitly;
    any other length mismatch fails fast instead of inventing values.
    """

    arr = np.asarray(values, dtype=float).reshape(-1)
    expected = int(n_steps)
    if arr.size == expected + 1:
        arr = arr[:expected]
    if arr.size != expected:
        raise ValueError(
            f"[EC_FLEX] Wind profile '{label}' length mismatch: "
            f"got {arr.size}, expected {expected} (or {expected + 1} with one trailing endpoint sample)."
        )
    return arr


def _require_block(params: Dict[str, Any], key: str) -> Dict[str, Any]:
    if key not in params or not isinstance(params[key], dict):
        raise ValueError(f"[EC_FLEX] Missing required params['{key}'] dict.")
    return params[key]


def _require_attr(obj: Any, attr: str) -> Any:
    if obj is None or not hasattr(obj, attr):
        raise ValueError(f"[EC_FLEX] Missing required config attribute '{attr}'.")
    return getattr(obj, attr)


def _require_profile(profiles: Dict[str, Any], key: str) -> Any:
    if key not in profiles:
        raise ValueError(f"[EC_FLEX] Missing required profile '{key}'.")
    return profiles[key]


def simulate_energy_system_ec_flex(params: Dict[str, Any], profiles: Dict[str, Any], pv_size: float) -> Dict[str, Any]:
    eng = params.get("engine_config", None)
    features = getattr(eng, "features", None) if eng is not None else None
    enable_bess = bool(getattr(features, "enable_bess", True))
    enable_v2h = bool(getattr(features, "enable_v2h", True))
    enable_h2 = bool(getattr(features, "enable_h2", False))
    enable_thermflex = bool(getattr(features, "enable_thermflex", False))
    enable_small_wind = bool(getattr(features, "enable_small_wind", False))
    enable_large_wind = bool(getattr(features, "enable_large_wind", False))
    enable_biogas_engine = bool(getattr(features, "enable_biogas_engine", False))
    enable_wood_gasifier = bool(getattr(features, "enable_wood_gasifier", False))

    load_member_2d = np.asarray(profiles["load_member_2d"], dtype=float)
    hotwater_member_2d = np.asarray(_require_profile(profiles, "hotwater_member_2d"), dtype=float)
    t_out = np.asarray(_require_profile(profiles, "T_outdoor"), dtype=float)
    thermal_cfg = _require_attr(params.get("settings_obj", None), "thermal")
    t_out_building = smooth_effective_outdoor_temperature(
        t_out,
        float(getattr(thermal_cfg, "outdoor_smoothing_hours", 24.0)),
    )
    solar = np.asarray(_require_profile(profiles, "solargains"), dtype=float)
    usage = profiles["usage_profile"]
    availability = np.asarray(_require_profile(profiles, "availability_profile"), dtype=float)
    driving = np.asarray(_require_profile(profiles, "driving_profile"), dtype=float)
    min_soc_profile = np.asarray(_require_profile(profiles, "min_SOC"), dtype=float)

    n_steps, n_ec = load_member_2d.shape
    dt_h = 1.0
    timestamps = profiles.get("timestamps", pd.date_range("2023-01-01", periods=n_steps, freq="h"))
    wind_enabled = enable_small_wind or enable_large_wind
    if wind_enabled:
        wind_speed_ms = _require_wind_series(_require_profile(profiles, "wind_speed_ms"), n_steps, label="wind_speed_ms")
        wind_pressure_hpa = _require_wind_series(
            _require_profile(profiles, "wind_pressure_hpa"),
            n_steps,
            label="wind_pressure_hpa",
        )
    else:
        wind_speed_ms = np.zeros(n_steps, dtype=float)
        wind_pressure_hpa = np.zeros(n_steps, dtype=float)

    # Thermal states per member (building.py as source of truth).
    members = getattr(eng, "members", None) if eng is not None else None
    member_keys = []
    if members is not None and getattr(members, "members", None):
        for m in members.members:
            member_keys.extend([m.building_key] * int(m.count))
    if len(member_keys) != n_ec:
        member_keys = ["H0"] * n_ec

    thermal_states = []
    if members is not None and getattr(members, "members", None):
        for member in members.members:
            b = get_runtime_building_params(member, settings_obj=params.get("settings_obj", None))
            c_th_wh_per_k = float(b["heat_capacity"])
            for _ in range(int(member.count)):
                thermal_states.append(
                    ThermalBuildingState(
                        ti_k=float(b["T_min"]),
                        c_th_wh_per_k=max(1.0, c_th_wh_per_k),
                        ua_w_per_k=_u_a(b),
                        a_floor_m2=float(b["A_floor"]),
                        t_min_k=float(b["T_min"]),
                        t_max_k=float(b["T_max"]),
                        dt_h=dt_h,
                    )
                )

    hp = _require_block(params, "heatpump")
    if "cop_max" not in hp or "eer_max" not in hp:
        raise ValueError("[EC_FLEX] Missing required heatpump keys 'cop_max' and/or 'eer_max'.")
    cop_heat = float(hp["cop_max"])
    cop_cool = float(hp["eer_max"])
    delta_t = float(_require_attr(_require_attr(params.get("settings_obj", None), "thermal"), "delta_T"))
    # EV state.
    ev_cfg = _require_block(params, "EV")
    settings_obj = params.get("settings_obj", None)
    v2h_cfg = getattr(settings_obj, "v2h", None)
    if v2h_cfg is None:
        raise ValueError("[EC_FLEX] Missing required settings_obj.v2h policy config.")
    required_ev_keys = [
        "N_EV_total",
        "N_EV_bidirectional",
        "capacity_kWh",
        "charging_efficiency",
        "discharging_efficiency",
        "max_charge_power",
        "max_discharge_power",
        "initial_soc",
        "max_soc",
    ]
    missing_ev_keys = [k for k in required_ev_keys if k not in ev_cfg]
    if missing_ev_keys:
        raise ValueError(f"[EC_FLEX] Missing required EV keys: {missing_ev_keys}")
    n_ev = int(ev_cfg["N_EV_total"])
    n_ev_bidir = int(ev_cfg["N_EV_bidirectional"])
    ev_cap = float(ev_cfg["capacity_kWh"])
    ev_eta_ch = float(ev_cfg["charging_efficiency"])
    ev_eta_dis = float(ev_cfg["discharging_efficiency"])
    ev_p_max = float(ev_cfg["max_charge_power"]) * dt_h
    ev_p_dis_max = float(ev_cfg["max_discharge_power"]) * dt_h
    ev_reserve_lookahead_h = int(_require_attr(v2h_cfg, "reserve_lookahead_h"))
    ev_reserve_factor = float(_require_attr(v2h_cfg, "reserve_factor"))
    import_sensitive_dispatch = bool(_require_attr(v2h_cfg, "import_sensitive_dispatch"))
    ev_soc = np.zeros((n_steps, n_ev), dtype=float)
    if n_ev > 0:
        ev_soc[0, :] = ev_cap * float(ev_cfg["initial_soc"])
    if "rng_seed" not in params:
        raise ValueError("[EC_FLEX] Missing required key 'rng_seed'.")
    rng = np.random.default_rng(int(params["rng_seed"]))
    ev_to_member = rng.choice(n_ec, size=n_ev, replace=True) if n_ev > 0 else np.zeros(0, dtype=int)

    # BESS state.
    bess_cap = float(params.get("battery_capacity_kWh", 0.0)) if enable_bess else 0.0
    bess_settings = _require_attr(params.get("settings_obj", None), "bess")
    bess_initial_soc = float(_require_attr(bess_settings, "initial_soc")) if enable_bess else 0.0
    bess_initial_soc = min(1.0, max(0.0, bess_initial_soc))
    bess_soc = np.zeros(n_steps, dtype=float)
    bess_soc[0] = bess_initial_soc * bess_cap
    bess_block = _require_block(params, "BESS")
    if "power_kW" not in bess_block or "efficiency" not in bess_block:
        raise ValueError("[EC_FLEX] Missing required BESS keys 'power_kW' and/or 'efficiency'.")
    bess_p_cap = float(bess_block["power_kW"]) * float(max(1, n_ec)) * dt_h if enable_bess else 0.0
    bess_eta = float(bess_block["efficiency"]) if enable_bess else 1.0

    # Hydrogen state.
    if "ELY" not in params or not isinstance(params["ELY"], dict):
        raise ValueError("[EC_FLEX] Missing required params['ELY'] dict.")
    if "FC" not in params or not isinstance(params["FC"], dict):
        raise ValueError("[EC_FLEX] Missing required params['FC'] dict.")
    if "eta_ely" not in params["ELY"]:
        raise ValueError("[EC_FLEX] Missing required params['ELY']['eta_ely'].")
    if "eta_fc" not in params["FC"]:
        raise ValueError("[EC_FLEX] Missing required params['FC']['eta_fc'].")

    h2 = HydrogenSystem(
        p_ely_max_kw=float(params.get("ely_kw", 0.0) if enable_h2 else 0.0),
        e_h2_max_kwh=float(params.get("h2_tank_kwh", 0.0) if enable_h2 else 0.0),
        p_fc_max_kw=float(params.get("fc_kw", 0.0) if enable_h2 else 0.0),
        eta_ely=float(params["ELY"]["eta_ely"]),
        eta_fc=float(params["FC"]["eta_fc"]),
        soc_kwh=0.0,
        dt_h=dt_h,
    )
    h2_soc = np.zeros(n_steps, dtype=float)
    h2_soc[0] = h2.soc_kwh

    # Output arrays.
    # pv_generation profile is provided in W per reference kWp.
    # Convert to kWh/timestep (dt_h=1h): W -> kW via /1000, then scale by installed kWp.
    pv_gen = (np.asarray(profiles["pv_generation"], dtype=float) / 1000.0) * float(max(0.0, pv_size)) * dt_h
    small_wind_cfg = getattr(params.get("settings_obj", None), "small_wind", None)
    large_wind_cfg = getattr(params.get("settings_obj", None), "large_wind", None)
    biomass_biogas_cfg = getattr(params.get("settings_obj", None), "biogas_engine", None)
    biomass_wood_cfg = getattr(params.get("settings_obj", None), "wood_gasifier", None)
    small_wind_kw = float(params.get("small_wind_kw", 0.0)) if enable_small_wind else 0.0
    large_wind_kw = float(params.get("large_wind_kw", 0.0)) if enable_large_wind else 0.0
    biogas_kw = float(params.get("biogas_engine_kw", 0.0)) if enable_biogas_engine else 0.0
    wood_gasifier_kw = float(params.get("wood_gasifier_kw", 0.0)) if enable_wood_gasifier else 0.0
    wood_gasifier_params = _require_block(params, "WOOD_GASIFIER") if enable_wood_gasifier else {}
    run_of_river_cfg = getattr(params.get("settings_obj", None), "run_of_river_hydro", None)
    enable_run_of_river_hydro = bool(getattr(run_of_river_cfg, "enabled", False))
    if enable_run_of_river_hydro:
        location = str(getattr(getattr(params.get("settings_obj", None), "engine", None), "location", "")).strip().lower()
        if location != "vienna":
            raise ValueError("[EC_FLEX] run_of_river_hydro is only configured for Vienna.")
        run_of_river_flow_proxy = load_freudenau_hourly_flow_proxy_context(timestamps)
        run_of_river_hydro_gen = simulate_run_of_river_hydro_generation(
            timestamps=timestamps,
            hourly_flow_proxy=run_of_river_flow_proxy,
            installed_kw=VIENNA_RUN_OF_RIVER_INSTALLED_KW,
            annual_generation_gwh=VIENNA_RUN_OF_RIVER_ANNUAL_GENERATION_GWH,
            dt_h=dt_h,
        )
    else:
        run_of_river_hydro_gen = np.zeros(n_steps, dtype=float)
    small_wind_gen = simulate_small_wind_generation(
        installed_kw=small_wind_kw,
        wind_speed_ms=wind_speed_ms,
        reference_height_m=float(_require_attr(small_wind_cfg, "reference_measurement_height_m")),
        hub_height_m=float(_require_attr(small_wind_cfg, "hub_height_m")),
        shear_exponent=float(_require_attr(small_wind_cfg, "shear_exponent")),
        cut_in_ms=float(_require_attr(small_wind_cfg, "cut_in_ms")),
        rated_ms=float(_require_attr(small_wind_cfg, "rated_ms")),
        cut_out_ms=float(_require_attr(small_wind_cfg, "cut_out_ms")),
        temperature_c=t_out,
        pressure_hpa=wind_pressure_hpa,
        reference_air_density_kg_per_m3=float(_require_attr(small_wind_cfg, "reference_air_density_kg_per_m3")),
        dt_h=dt_h,
    ) if enable_small_wind else np.zeros(n_steps, dtype=float)
    large_wind_gen = simulate_large_wind_generation(
        installed_kw=large_wind_kw,
        wind_speed_ms=wind_speed_ms,
        reference_height_m=float(_require_attr(large_wind_cfg, "reference_measurement_height_m")),
        hub_height_m=float(_require_attr(large_wind_cfg, "hub_height_m")),
        shear_exponent=float(_require_attr(large_wind_cfg, "shear_exponent")),
        cut_in_ms=float(_require_attr(large_wind_cfg, "cut_in_ms")),
        rated_ms=float(_require_attr(large_wind_cfg, "rated_ms")),
        cut_out_ms=float(_require_attr(large_wind_cfg, "cut_out_ms")),
        temperature_c=t_out,
        pressure_hpa=wind_pressure_hpa,
        reference_air_density_kg_per_m3=float(_require_attr(large_wind_cfg, "reference_air_density_kg_per_m3")),
        dt_h=dt_h,
    ) if enable_large_wind else np.zeros(n_steps, dtype=float)
    grid_import = np.zeros(n_steps, dtype=float)
    grid_export = np.zeros(n_steps, dtype=float)
    bess_ch = np.zeros(n_steps, dtype=float)
    bess_dis = np.zeros(n_steps, dtype=float)
    ev_charge_ac = np.zeros(n_steps, dtype=float)
    mandatory_ev_charge_ac = np.zeros(n_steps, dtype=float)
    ev_dis_ac = np.zeros((n_steps, n_ev), dtype=float)
    ev_charge_from_pv = np.zeros(n_steps, dtype=float)
    ev_charge_from_bess = np.zeros(n_steps, dtype=float)
    ev_charge_from_ec = np.zeros(n_steps, dtype=float)
    ev_charge_from_grid = np.zeros(n_steps, dtype=float)
    ec_import_from_pv = np.zeros(n_steps, dtype=float)
    ec_import_from_ev = np.zeros(n_steps, dtype=float)
    ec_export_from_pv = np.zeros(n_steps, dtype=float)
    base_load = np.zeros(n_steps, dtype=float)
    total_load = np.zeros(n_steps, dtype=float)
    hp_base_elec = np.zeros(n_steps, dtype=float)
    hp_flex_elec = np.zeros(n_steps, dtype=float)
    h2_charge_elec = np.zeros(n_steps, dtype=float)
    h2_discharge_elec = np.zeros(n_steps, dtype=float)
    biogas_generation = np.zeros(n_steps, dtype=float)
    wood_gasifier_generation = np.zeros(n_steps, dtype=float)
    wood_gasifier_fuel_input_kwh = np.zeros(n_steps, dtype=float)
    wood_gasifier_fuel_input_kg = np.zeros(n_steps, dtype=float)
    h2_used_kwh = np.zeros(n_steps, dtype=float)
    v2h_allowed = np.zeros(n_steps, dtype=float)
    v2h_used = np.zeros(n_steps, dtype=float)
    v2h_avoided_import = np.zeros(n_steps, dtype=float)
    for t in range(n_steps):
        if t > 0:
            bess_soc[t] = bess_soc[t - 1]
            if n_ev > 0:
                ev_soc[t, :] = ev_soc[t - 1, :]
            h2_soc[t] = h2.soc_kwh

        # Base thermal simulation and mandatory HVAC.
        hvac_member = np.zeros(n_ec, dtype=float)
        internal_w_m2 = usage["Qi Winter W/m2"].to_numpy(dtype=float)[t] if "Qi Winter W/m2" in usage.columns else 0.0
        for m_idx, st in enumerate(thermal_states):
            st.passive_step(t_out_building[t], internal_w_m2, solar[t])
            heat_kwh, cool_kwh = st.base_hvac_energy()
            hvac_member[m_idx] = (heat_kwh / max(1e-9, cop_heat)) + (cool_kwh / max(1e-9, cop_cool))
        hp_base_elec[t] = float(np.sum(hvac_member))

        base_member = load_member_2d[t, :] + hotwater_member_2d[t, :] + hvac_member
        base_load_t = float(np.sum(base_member))

        base_load[t] = base_load_t

        # EV mobility constraints and capacities.
        mandatory_ev_charge = 0.0
        opt_ev_charge_cap = np.zeros(n_ev, dtype=float)
        opt_ev_dis_cap = np.zeros(n_ev, dtype=float)
        if n_ev > 0:
            for i in range(n_ev):
                available = bool(rng.random() <= availability[t])
                if not available:
                    ev_soc[t, i] = max(0.0, ev_soc[t, i] - (driving[t] * ev_cap))
                    continue
                min_soc = ev_cap * min_soc_profile[t]
                max_soc = ev_cap * float(ev_cfg["max_soc"])
                if ev_soc[t, i] < min_soc:
                    need_dc = min_soc - ev_soc[t, i]
                    mandatory_ev_charge += need_dc / max(1e-9, ev_eta_ch)
                    ev_soc[t, i] += need_dc
                headroom = max(0.0, max_soc - ev_soc[t, i])
                opt_ev_charge_cap[i] = min(headroom / max(1e-9, ev_eta_ch), ev_p_max)
                if enable_v2h and i < n_ev_bidir:
                    # Keep a dynamic SoC reserve above min_soc to avoid near-term grid rebound charging.
                    t_end = min(n_steps, t + max(1, ev_reserve_lookahead_h))
                    future_drive_dc = np.asarray(driving[t:t_end], dtype=float) * ev_cap
                    future_unavail = np.clip(1.0 - np.asarray(availability[t:t_end], dtype=float), 0.0, 1.0)
                    reserve_dc = ev_reserve_factor * float(np.sum(future_drive_dc * future_unavail))
                    reserve_dc = min(max(0.0, reserve_dc), max(0.0, max_soc - min_soc))
                    discharge_margin_dc = max(0.0, ev_soc[t, i] - (min_soc + reserve_dc))
                    opt_ev_dis_cap[i] = min(discharge_margin_dc * ev_eta_dis, ev_p_dis_max)

        demand = base_load_t + mandatory_ev_charge
        mandatory_ev_charge_ac[t] = mandatory_ev_charge
        ev_charge_ac[t] += mandatory_ev_charge
        pv_t = float(pv_gen[t])
        small_wind_t = float(small_wind_gen[t])
        large_wind_t = float(large_wind_gen[t])
        run_of_river_t = float(run_of_river_hydro_gen[t])
        nondispatch_gen_t = pv_t + small_wind_t + large_wind_t + run_of_river_t
        provisional_deficit = max(0.0, demand - nondispatch_gen_t)
        biogas_t = 0.0
        if enable_biogas_engine:
            biogas_t = dispatch_biogas_engine(
                capacity_kw=biogas_kw,
                deficit_kwh=provisional_deficit,
                min_partload=float(_require_attr(biomass_biogas_cfg, "min_partload")),
                max_partload=float(_require_attr(biomass_biogas_cfg, "max_partload")),
                fixed_output_fraction=float(_require_attr(biomass_biogas_cfg, "fixed_output_fraction")),
                dispatch_mode=str(_require_attr(biomass_biogas_cfg, "dispatch_mode")),
                dt_h=dt_h,
            )
        wood_t = 0.0
        if enable_wood_gasifier:
            wood_dispatch = dispatch_wood_gasifier(
                capacity_kw=wood_gasifier_kw,
                deficit_kwh=provisional_deficit,
                min_partload=float(_require_attr(biomass_wood_cfg, "min_partload")),
                max_partload=float(_require_attr(biomass_wood_cfg, "max_partload")),
                dispatch_mode=str(_require_attr(biomass_wood_cfg, "dispatch_mode")),
                eta_el=float(wood_gasifier_params["eta_el"]),
                fuel_lhv_kwh_per_kg=float(wood_gasifier_params["fuel_lhv_kwh_per_kg"]),
                dt_h=dt_h,
            )
            wood_t = float(wood_dispatch["electric_output_kwh"])
            wood_gasifier_fuel_input_kwh[t] = float(wood_dispatch["fuel_input_kwh"])
            wood_gasifier_fuel_input_kg[t] = float(wood_dispatch["fuel_input_kg"])
        biogas_generation[t] = biogas_t
        wood_gasifier_generation[t] = wood_t
        local_gen_t = nondispatch_gen_t + biogas_t + wood_t
        surplus = max(0.0, local_gen_t - demand)
        deficit = max(0.0, demand - local_gen_t)
        mandatory_share = (mandatory_ev_charge / demand) if demand > 1e-9 else 0.0

        # Capabilities for dispatch policy.
        therm_cap = 0.0
        therm_mode = "heat"
        if enable_thermflex:
            for st in thermal_states:
                cap, mode = thermflex_extra_cap_kwh(st, t_out[t], delta_t, cop_heat, cop_cool)
                therm_cap += cap
                therm_mode = mode
        bess_charge_cap = min(bess_p_cap, max(0.0, (bess_cap - bess_soc[t]) / max(1e-9, bess_eta)))
        bess_discharge_cap = min(bess_p_cap, max(0.0, bess_soc[t] * bess_eta))
        h2_ely_cap = h2.p_ely_max_kw * dt_h if enable_h2 else 0.0
        h2_fc_cap = h2.p_fc_max_kw * dt_h if enable_h2 else 0.0

        if surplus > 0.0:
            ev_charge_from_pv[t] += mandatory_ev_charge
            alloc = allocate_surplus(
                surplus_kwh=surplus,
                ev_charge_cap_kwh=float(np.sum(opt_ev_charge_cap)),
                thermflex_cap_kwh=therm_cap if enable_thermflex else 0.0,
                bess_charge_cap_kwh=bess_charge_cap if enable_bess else 0.0,
                h2_ely_cap_kwh=h2_ely_cap if enable_h2 else 0.0,
            )
            # EV charging from surplus.
            ev_add = _distribute(alloc["ev_charge"], opt_ev_charge_cap)
            ev_charge_ac[t] += float(np.sum(ev_add))
            ev_charge_from_pv[t] += float(np.sum(ev_add))
            if n_ev > 0:
                ev_soc[t, :] += ev_add * ev_eta_ch

            # ThermFlex uses residual surplus.
            hp_flex_elec[t] = float(alloc["thermflex"])
            if enable_thermflex and alloc["thermflex"] > 0.0 and n_ec > 0:
                per_member = alloc["thermflex"] / float(n_ec)
                for st in thermal_states:
                    if therm_mode == "heat":
                        st.ti_k = min(st.t_max_k + delta_t, st.ti_k + (per_member * cop_heat * 1000.0) / max(1e-9, st.c_th_wh_per_k))
                    else:
                        st.ti_k = max(st.t_min_k - delta_t, st.ti_k - (per_member * cop_cool * 1000.0) / max(1e-9, st.c_th_wh_per_k))

            # BESS charge.
            if enable_bess:
                bch = min(alloc["bess_charge"], bess_charge_cap)
                bess_ch[t] = bch
                bess_soc[t] = min(bess_cap, bess_soc[t] + (bch * bess_eta))

            # Hydrogen electrolysis.
            if enable_h2:
                h2_in, _h2_store = h2.charge(alloc["h2_electrolysis"])
                h2_charge_elec[t] = h2_in
            grid_export[t] = alloc["export"]
        else:
            v2h_cap_total = float(np.sum(opt_ev_dis_cap)) if enable_v2h else 0.0
            # Dispatch FC only with physically available electric output from current H2 SoC.
            h2_fc_cap_dispatch = min(h2_fc_cap, max(0.0, h2.soc_kwh * h2.eta_fc)) if enable_h2 else 0.0
            if import_sensitive_dispatch:
                # Only dispatch EV discharge that is actually needed to avoid grid import.
                non_ev_firm_supply = (bess_discharge_cap if enable_bess else 0.0) + h2_fc_cap_dispatch
                v2h_needed_for_import = max(0.0, deficit - non_ev_firm_supply)
                v2h_gate_cap = min(v2h_cap_total, v2h_needed_for_import)
            else:
                v2h_gate_cap = v2h_cap_total
            if v2h_gate_cap > 1e-9:
                v2h_allowed[t] = 1.0
            alloc = allocate_deficit(
                deficit_kwh=deficit,
                v2h_discharge_cap_kwh=v2h_gate_cap,
                bess_discharge_cap_kwh=bess_discharge_cap if enable_bess else 0.0,
                h2_fc_cap_kwh=h2_fc_cap_dispatch,
            )
            # V2H discharge.
            v2h_to_def = 0.0
            if enable_v2h and n_ev > 0:
                ev_dis = _distribute(alloc["v2h_discharge"], opt_ev_dis_cap)
                ev_dis_ac[t, :] = ev_dis
                ev_soc[t, :] = np.maximum(0.0, ev_soc[t, :] - (ev_dis / max(1e-9, ev_eta_dis)))
                v2h_to_def = float(np.sum(ev_dis))
                if v2h_to_def > 1e-9:
                    v2h_used[t] = 1.0
            # BESS discharge.
            bdis = 0.0
            if enable_bess:
                bdis = min(alloc["bess_discharge"], bess_discharge_cap)
                bess_dis[t] = bdis
                bess_soc[t] = max(0.0, bess_soc[t] - (bdis / max(1e-9, bess_eta)))
            # Hydrogen FC.
            h2_to_def = 0.0
            if enable_h2:
                el_out, h2_used = h2.discharge(alloc["h2_fuel_cell"])
                h2_discharge_elec[t] = el_out
                h2_used_kwh[t] = h2_used
                h2_to_def = el_out
            # IMPORTANT: always compute import from realized dispatch (not planned caps).
            grid_import[t] = max(0.0, deficit - float(v2h_to_def) - float(bdis) - float(h2_to_def))
            # Debug proxy: estimated grid import avoided by V2H in this timestep.
            if v2h_to_def > 1e-9:
                import_without_v2h = max(0.0, deficit - float(bdis) - float(h2_to_def))
                v2h_avoided_import[t] = max(
                    0.0,
                    min(float(v2h_to_def), import_without_v2h - float(grid_import[t])),
                )
            # Attribute mandatory EV charging to actually used supply mix (aggregated proxy).
            ev_charge_from_pv[t] += mandatory_share * min(local_gen_t, demand)
            ev_charge_from_grid[t] += mandatory_share * float(grid_import[t])
            ev_charge_from_bess[t] += mandatory_share * float(bdis)
            ev_charge_from_ec[t] += mandatory_share * float(v2h_to_def + h2_to_def)

        # ev_charge_ac already includes mandatory + opportunistic EV charging.
        total_load[t] = base_load_t + ev_charge_ac[t] + hp_flex_elec[t]
        h2_soc[t] = h2.soc_kwh

    # Cyclic hydrogen SoC check (relative tolerance locked by settings).
    # Do not raise here: expose violation as flow for constraint handling.
    bess_cyclic_violation_kwh = 0.0
    b_cfg = bool(_require_attr(bess_settings, "cyclic_soc"))
    if enable_bess and bool(b_cfg):
        rtol = float(_require_attr(bess_settings, "cyclic_soc_rtol"))
        e0 = bess_initial_soc * bess_cap
        tol = rtol * max(1.0, bess_cap)
        bess_cyclic_violation_kwh = max(0.0, abs(bess_soc[-1] - e0) - tol)

    h2_cyclic_violation_kwh = 0.0
    hydrogen_cfg = _require_attr(params.get("settings_obj", None), "hydrogen")
    h_cfg = bool(_require_attr(hydrogen_cfg, "cyclic_soc"))
    if enable_h2 and bool(h_cfg):
        rtol = float(_require_attr(hydrogen_cfg, "cyclic_soc_rtol"))
        e0 = 0.0
        tol = rtol * max(1.0, h2.e_h2_max_kwh)
        h2_cyclic_violation_kwh = max(0.0, abs(h2.soc_kwh - e0) - tol)

    hours_v2h_allowed = float(np.sum(v2h_allowed))
    hours_v2h_used = float(np.sum(v2h_used))
    v2h_avoided_import_kwh = float(np.sum(v2h_avoided_import))
    v2h_recharge_grid_kwh = float(np.sum(ev_charge_from_grid))
    v2h_net_grid_saving_kwh = float(v2h_avoided_import_kwh - v2h_recharge_grid_kwh)

    return {
        "pv_generation": pv_gen,
        "small_wind_generation": small_wind_gen,
        "large_wind_generation": large_wind_gen,
        "run_of_river_hydro_generation": run_of_river_hydro_gen,
        "biogas_generation": biogas_generation,
        "wood_gasifier_generation": wood_gasifier_generation,
        "wood_gasifier_fuel_input_kwh": wood_gasifier_fuel_input_kwh,
        "wood_gasifier_fuel_input_kg": wood_gasifier_fuel_input_kg,
        "grid_import": grid_import,
        "grid_export": grid_export,
        "bess_charged": bess_ch,
        "bess_discharged": bess_dis,
        "bess_soc": bess_soc,
        "bess_cyclic_violation_kwh": float(bess_cyclic_violation_kwh),
        "ev_charge_ac": ev_charge_ac,
        "ev_charge_mandatory_ac": mandatory_ev_charge_ac,
        "ev_charge_from_pv_ac": ev_charge_from_pv,
        "ev_charge_from_bess_ac": ev_charge_from_bess,
        "ev_charge_from_ec_ac": ev_charge_from_ec,
        "ev_charge_from_grid_ac": ev_charge_from_grid,
        "ev_discharged": ev_dis_ac,
        "ev_discharged_total": ev_dis_ac.sum(axis=1) if n_ev > 0 else np.zeros(n_steps, dtype=float),
        "ev_soc": ev_soc,
        "ec_import_from_pv": ec_import_from_pv,
        "ec_import_from_ev": ec_import_from_ev,
        "ec_export_from_pv": ec_export_from_pv,
        "base_load": base_load,
        "total_load": total_load,
        "household_load": load_member_2d.sum(axis=1),
        "hotwater_load": hotwater_member_2d.sum(axis=1),
        "hp_base_elec": hp_base_elec,
        "hp_flex_elec": hp_flex_elec,
        "h2_charge_elec": h2_charge_elec,
        "h2_discharge_elec": h2_discharge_elec,
        "h2_used_kwh": h2_used_kwh,
        "h2_soc": h2_soc,
        "h2_cyclic_violation_kwh": float(h2_cyclic_violation_kwh),
        "v2h_allowed": v2h_allowed,
        "v2h_used": v2h_used,
        "v2h_avoided_import_kwh_step": v2h_avoided_import,
        "hours_v2h_allowed": hours_v2h_allowed,
        "hours_v2h_used": hours_v2h_used,
        "v2h_avoided_import_kwh": v2h_avoided_import_kwh,
        "v2h_recharge_grid_kwh": v2h_recharge_grid_kwh,
        "v2h_net_grid_saving_kwh": v2h_net_grid_saving_kwh,
        "timestamps": timestamps,
    }
