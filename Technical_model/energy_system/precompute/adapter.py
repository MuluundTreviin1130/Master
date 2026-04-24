from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterator, Tuple

import numpy as np
import pandas as pd

from Data.assembly import get_parameters, load_profiles
from Technical_model.energy_system.precompute.precompute import prepare_profiles as _prepare

@dataclass
class PrecomputePackage:
    params_base: Dict[str, Any]
    profiles: Dict[str, Any]
    year_load_kwh: float
    lifetime_years: int

    # damit weiterhin möglich: params, profiles = prepare_profiles_adapter(...)
    def __iter__(self) -> Iterator[Dict[str, Any]]:
        yield self.params_base
        yield self.profiles


def _inject_fixed_dh_capacities_from_settings(params: Dict[str, Any], settings_obj: Any) -> None:
    tech_activation = getattr(settings_obj, "technology_activation", None)
    if tech_activation is None:
        return

    if bool(getattr(tech_activation, "district_external_heat", False)):
        cfg = getattr(settings_obj, "district_external_heat", None)
        if cfg is None or getattr(cfg, "installed_kw_th_fixed", None) is None:
            raise ValueError(
                "[adapter] district_external_heat is active, but settings.district_external_heat.installed_kw_th_fixed is missing."
            )
        params["district_external_heat_kw_th"] = float(cfg.installed_kw_th_fixed)

    if bool(getattr(tech_activation, "district_gas_boiler", False)):
        cfg = getattr(settings_obj, "district_gas_boiler", None)
        if cfg is None or getattr(cfg, "installed_kw_th_fixed", None) is None:
            raise ValueError(
                "[adapter] district_gas_boiler is active, but settings.district_gas_boiler.installed_kw_th_fixed is missing."
            )
        params["district_gas_boiler_kw_th"] = float(cfg.installed_kw_th_fixed)

    if bool(getattr(tech_activation, "district_solar_thermal", False)):
        cfg = getattr(settings_obj, "district_solar_thermal", None)
        if cfg is None or getattr(cfg, "installed_kw_th_fixed", None) is None:
            raise ValueError(
                "[adapter] district_solar_thermal is active, but settings.district_solar_thermal.installed_kw_th_fixed is missing."
            )
        params["district_solar_thermal_kw_th"] = float(cfg.installed_kw_th_fixed)

    if bool(getattr(tech_activation, "district_waste_incineration", False)):
        cfg = getattr(settings_obj, "district_waste_incineration", None)
        if cfg is None or getattr(cfg, "installed_kw_th_fixed", None) is None:
            raise ValueError(
                "[adapter] district_waste_incineration is active, but settings.district_waste_incineration.installed_kw_th_fixed is missing."
            )
        params["district_waste_incineration_kw_th"] = float(cfg.installed_kw_th_fixed)


def _slice_prepared_profiles(prepared: Dict[str, Any], *, start_ts: str, hours: int) -> Dict[str, Any]:
    timestamps = pd.DatetimeIndex(pd.to_datetime(prepared.get("timestamps")))
    if len(timestamps) == 0:
        raise ValueError("[adapter] Cannot slice profiles because timestamps are missing or empty.")
    start = pd.Timestamp(start_ts)
    try:
        start_idx = int(timestamps.get_loc(start))
    except KeyError as exc:
        raise KeyError(f"[adapter] Requested run.profile_start={start} is not present in prepared timestamps.") from exc
    stop_idx = start_idx + int(hours)
    if stop_idx > len(timestamps):
        raise ValueError(
            f"[adapter] Requested profile slice [{start_idx}:{stop_idx}] exceeds available horizon {len(timestamps)}."
        )

    sliced: Dict[str, Any] = {}
    n = len(timestamps)
    for key, value in prepared.items():
        if key == "timestamps":
            sliced[key] = timestamps[start_idx:stop_idx]
            continue
        if isinstance(value, pd.Series):
            if len(value) == n:
                sliced[key] = value.iloc[start_idx:stop_idx].copy()
            else:
                sliced[key] = value
            continue
        if isinstance(value, pd.DataFrame):
            if len(value) == n:
                sliced[key] = value.iloc[start_idx:stop_idx].copy()
            else:
                sliced[key] = value.copy()
            continue
        if isinstance(value, np.ndarray):
            if value.ndim >= 1 and value.shape[0] == n:
                sliced[key] = value[start_idx:stop_idx].copy()
            else:
                sliced[key] = value.copy()
            continue
        sliced[key] = value
    return sliced


def prepare_profiles_adapter(location,
                             data_source: str | None = None
                             ) -> PrecomputePackage:
    """
    Adapter zwischen Data-Schicht (Parameter/Profile) und Precompute-Logik.

    Akzeptiert entweder:
      - location: str  (z.B. "Vienna")
      - oder ein Settings-Objekt (dann wird location aus settings.engine.location extrahiert)

    Rückgabe:
      PrecomputePackage mit:
        - .params_base
        - .profiles
        - .year_load_kwh
        - .lifetime_years

    Zusätzlich unpackbar als (params_base, profiles).
    """

    # --- 0) Support: Settings statt location-String ---
    members = None
    settings_obj = None
    if not isinstance(location, str):
        settings_obj = location
        eng = getattr(settings_obj, "engine", None)

        loc = getattr(eng, "location", None) or getattr(settings_obj, "location", None)
        if not isinstance(loc, str) or not loc.strip():
            raise TypeError(
                "prepare_profiles_adapter: expected location str or settings with settings.engine.location."
            )
        location = loc

        # Extract members from settings
        members = getattr(eng, "members", None) if eng else None

        # data_source optional aus settings ziehen, falls nicht explizit übergeben
        if data_source is None:
            data = getattr(settings_obj, "data", None)
            ds = getattr(data, "source", None) if data is not None else None
            if isinstance(ds, str) and ds.strip():
                data_source = ds

    # --- 1) Basis-Parameter holen ---
    params = dict(get_parameters(location))
    params["location"] = location
    if isinstance(data_source, str) and data_source.strip():
        params["data_source"] = data_source
    
    # Add N_EC and N_HH from settings if available (settings_obj already extracted above)
    if settings_obj is not None:
        eng = getattr(settings_obj, "engine", None)
        if eng:
            params["N_HH"] = int(eng.N_HH)
            params["N_EC"] = int(eng.N_EC)
            params["rng_seed"] = int(eng.rng_seed)
            ev_cfg = params.setdefault("EV", {})
            ev_cfg["N_EV_total"] = int(eng.N_EV_total)
            ev_cfg["N_EV_bidirectional"] = int(eng.N_EV_bidirectional)
        params["settings_obj"] = settings_obj
        _inject_fixed_dh_capacities_from_settings(params, settings_obj)

    # lifetime (fallback auf 25 wie bei dir im Log)
    lifetime_years = int(params.get("lifetime", params.get("lifetime_years", 25)))

    # --- 2) Profile laden (no fallback - members required) ---
    # Prepare member_ids and counts for load_profiles
    # WICHTIG: Nur Member mit count > 0 laden, um Signatur-Stabilität zu gewährleisten
    # (sonst ändert sich profile_id, wenn Member mit count=0 hinzugefügt werden)
    if members is None or not hasattr(members, "members") or len(members.members) == 0:
        raise ValueError(
            "[adapter] members configuration is required. "
            "Ensure settings.engine.members is provided with at least one active member."
        )
    
    # Filter: Nur Member mit count > 0
    active_members = [m for m in members.members if m.count > 0]
    if len(active_members) == 0:
        raise ValueError(
            "[adapter] At least one member with count > 0 is required. "
            "All configured members have count=0."
        )
    
    features = getattr(eng, "features", None) if settings_obj is not None else None
    require_wind = bool(
        getattr(features, "enable_small_wind", False)
        or getattr(features, "enable_large_wind", False)
    )

    profiles_raw = load_profiles(
        location,
        members=active_members,
        require_wind=require_wind,
    )

    # --- 3) Jahres-Precompute anwenden ---
    prepared = _prepare(
        params=params,
        profiles=profiles_raw,
        do_hp_electricity=True,
        do_coeffs=False,
        members=members,
    )

    if settings_obj is not None:
        run_cfg = getattr(settings_obj, "run", None)
        profile_start = getattr(run_cfg, "profile_start", None) if run_cfg is not None else None
        profile_hours = getattr(run_cfg, "profile_hours", None) if run_cfg is not None else None
        if profile_start is not None and profile_hours is not None:
            profile_hours_int = int(profile_hours)
            if profile_hours_int <= 0:
                raise ValueError(f"[adapter] run.profile_hours must be > 0, got {profile_hours_int}.")
            prepared = _slice_prepared_profiles(prepared, start_ts=str(profile_start), hours=profile_hours_int)

    # --- 4) Sicherstellen, dass profiles['load'] eine pd.Series mit DatetimeIndex ist ---
    load = prepared.get("load")
    if load is not None and not isinstance(load, pd.Series):
        ts = prepared.get("timestamps")
        if ts is not None:
            idx = pd.to_datetime(ts)
        else:
            idx = pd.date_range(start="2023-01-01", periods=len(load), freq="h")
            prepared["timestamps"] = idx
        prepared["load"] = pd.Series(load, index=idx)

    # --- 5) year_load_kwh ableiten ---
    load_series = prepared.get("load")
    year_load_kwh = float(load_series.sum()) if load_series is not None and hasattr(load_series, "sum") else 0.0

    return PrecomputePackage(
        params_base=params,
        profiles=prepared,
        year_load_kwh=year_load_kwh,
        lifetime_years=lifetime_years,
    )
