from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterator, Tuple

import pandas as pd

from Data.data import get_parameters, load_profiles
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

    # lifetime (fallback auf 25 wie bei dir im Log)
    lifetime_years = int(params.get("lifetime", params.get("lifetime_years", 25)))

    # --- 2) Profile laden (no fallback - members required) ---
    # Prepare member_ids and counts for load_profiles
    # WICHTIG: Nur Member mit count > 0 laden, um Signatur-Stabilität zu gewährleisten
    # (sonst ändert sich profile_id, wenn Member mit count=0 hinzugefügt werden)
    if members is None or not hasattr(members, "members") or len(members.members) == 0:
        raise ValueError(
            "[adapter] members configuration is required. "
            "Ensure members.yaml exists and settings.engine.members is set."
        )
    
    # Filter: Nur Member mit count > 0
    active_members = [m for m in members.members if m.count > 0]
    if len(active_members) == 0:
        raise ValueError(
            "[adapter] At least one member with count > 0 is required. "
            "All members in members.yaml have count=0."
        )
    
    member_ids = [m.id for m in active_members]
    member_counts = [m.count for m in active_members]
    
    profiles_raw = load_profiles(location, member_ids=member_ids, member_counts=member_counts)

    # --- 3) Jahres-Precompute anwenden ---
    prepared = _prepare(
        params=params,
        profiles=profiles_raw,
        do_hp_electricity=True,
        do_coeffs=False,
        members=members,
    )

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
