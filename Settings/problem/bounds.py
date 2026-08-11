from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Bounds:
    """Decision-variable bounds.

    bounds.names is the single source of truth for decision-vector ordering.
    """

    names: List[str]
    lower: List[float]
    upper: List[float]
    steps: Optional[List[float]] = None
    caps: Dict[str, float] = field(default_factory=dict)


def make_name_to_index(bounds: Bounds) -> Dict[str, int]:
    return {name: i for i, name in enumerate(bounds.names)}


def vector_to_named_dict(x, bounds: Bounds) -> Dict[str, float]:
    return {name: float(x[i]) for i, name in enumerate(bounds.names)}


def _n_ec_from_engine(engine) -> float:
    members = getattr(engine, "members", None)
    if members is not None and hasattr(members, "N_EC"):
        return float(getattr(members, "N_EC"))
    return float(getattr(engine, "N_EC"))


def _default_caps() -> Dict[str, float]:
    return {
        "per_ec_pv_kwp": 50.0,
        "per_ec_bess_kwh": 50.0,
        "per_ec_ely_kw": 10.0,
        "per_ec_h2_tank_kwh": 100.0,
        "per_ec_fc_kw": 10.0,
        "per_ec_small_wind_kw": 10.0,
        "per_ec_large_wind_kw": 50.0,
        # Central DH technologies use absolute central scaffold caps, not EC-scaled caps.
        "district_heat_pump_kw_th": 7500.0,
        "district_thermal_storage_kwh_th": 30000.0,
        "district_wood_chip_boiler_kw_th": 7500.0,
        "district_biomass_chp_kw_th": 7500.0,
        "district_geothermal_kw_el": 3750.0,
        "district_gas_chp_kw_el": 7500.0,
        "district_biogas_chp_kw_el": 3750.0,
        "per_ec_biogas_engine_kw": 15.0,
        "per_ec_wood_gasifier_kw": 15.0,
    }


def make_bounds(engine, caps: Optional[Dict[str, float]] = None) -> Bounds:
    """Build feature-aware bounds.

    - Distributed technologies keep member-scaled scaffold caps.
    - Central DH technologies use absolute central scaffold caps.
    - Feature OFF forces the related decision variables to 0..0.
    """
    n_ec = _n_ec_from_engine(engine)
    resolved_caps = _default_caps()
    if isinstance(caps, dict):
        for k, v in caps.items():
            if k in resolved_caps:
                resolved_caps[k] = float(v)

    upper = [
        float(resolved_caps["per_ec_pv_kwp"] * n_ec),
        float(resolved_caps["per_ec_bess_kwh"] * n_ec),
        float(resolved_caps["per_ec_ely_kw"] * n_ec),
        float(resolved_caps["per_ec_h2_tank_kwh"] * n_ec),
        float(resolved_caps["per_ec_fc_kw"] * n_ec),
        float(resolved_caps["per_ec_small_wind_kw"] * n_ec),
        float(resolved_caps["per_ec_large_wind_kw"] * n_ec),
        float(resolved_caps["district_heat_pump_kw_th"]),
        float(resolved_caps["district_thermal_storage_kwh_th"]),
        float(resolved_caps["district_wood_chip_boiler_kw_th"]),
        float(resolved_caps["district_biomass_chp_kw_th"]),
        float(resolved_caps["district_geothermal_kw_el"]),
        float(resolved_caps["district_gas_chp_kw_el"]),
        float(resolved_caps["district_biogas_chp_kw_el"]),
        float(resolved_caps["per_ec_biogas_engine_kw"] * n_ec),
        float(resolved_caps["per_ec_wood_gasifier_kw"] * n_ec),
    ]
    b = Bounds(
        names=[
            "pv_kwp",
            "bess_kwh",
            "ely_kw",
            "h2_tank_kwh",
            "fc_kw",
            "small_wind_kw",
            "large_wind_kw",
            "district_heat_pump_kw_th",
            "district_thermal_storage_kwh_th",
            "district_wood_chip_boiler_kw_th",
            "district_biomass_chp_kw_th",
            "district_geothermal_kw_el",
            "district_gas_chp_kw_el",
            "district_biogas_chp_kw_el",
            "biogas_engine_kw",
            "wood_gasifier_kw",
        ],
        lower=[0.0] * 16,
        upper=upper,
        steps=[0.1] * 16,
        caps=resolved_caps,
    )
    apply_feature_bounds(engine, b)
    return b


# Central DH decision variables that exist in the optimization vector.
# Each entry maps a technology_activation flag onto the bound name(s) that must
# collapse to 0..0 when that technology is inactive. Technologies without a
# design variable here (external heat, gas boiler, solar thermal, waste) are
# intentionally omitted: they are not part of the sampled decision vector.
_TECHNOLOGY_ACTIVATION_BOUND_VARS = (
    ("district_heat_pump", ("district_heat_pump_kw_th",)),
    ("district_thermal_storage", ("district_thermal_storage_kwh_th",)),
    ("district_wood_chip_boiler", ("district_wood_chip_boiler_kw_th",)),
    ("district_biomass_chp", ("district_biomass_chp_kw_th",)),
    ("district_geothermal", ("district_geothermal_kw_el",)),
    ("district_gas_chp", ("district_gas_chp_kw_el",)),
    ("district_biogas_chp", ("district_biogas_chp_kw_el",)),
)


def _force_bound_zero(bounds: Bounds, idx: Dict[str, int], var_name: str) -> None:
    """Collapse one decision variable to the inactive interval 0..0."""
    i = idx.get(var_name)
    if i is None:
        return
    bounds.lower[i] = 0.0
    bounds.upper[i] = 0.0


def apply_feature_bounds(engine, bounds: Bounds) -> None:
    """Enforce feature-toggle consistency on decision bounds.

    This guard is intentionally minimal and centralized:
    - Feature OFF => corresponding decision variable is forced to 0..0.
    - Feature ON  => keep current bounds (including explicit overrides).

    Notes:
    - V2H and thermal-flex currently have no direct decision variable in the
      superset vector, so only BESS and H2 vars are guarded here.
    - Central DH capacities are gated separately by
      ``apply_technology_activation_bounds`` because their SSOT lives in
      ``settings.technology_activation``, not ``engine.features``.
    """
    features = getattr(engine, "features", None)
    if features is None:
        return

    idx = make_name_to_index(bounds)

    if not bool(getattr(features, "enable_bess", True)):
        _force_bound_zero(bounds, idx, "bess_kwh")

    if not bool(getattr(features, "enable_h2", False)):
        _force_bound_zero(bounds, idx, "ely_kw")
        _force_bound_zero(bounds, idx, "h2_tank_kwh")
        _force_bound_zero(bounds, idx, "fc_kw")
    if not bool(getattr(features, "enable_small_wind", False)):
        _force_bound_zero(bounds, idx, "small_wind_kw")
    if not bool(getattr(features, "enable_large_wind", False)):
        _force_bound_zero(bounds, idx, "large_wind_kw")
    if not bool(getattr(features, "enable_biogas_engine", False)):
        _force_bound_zero(bounds, idx, "biogas_engine_kw")
    if not bool(getattr(features, "enable_wood_gasifier", False)):
        _force_bound_zero(bounds, idx, "wood_gasifier_kw")


def apply_technology_activation_bounds(activation, bounds: Bounds) -> None:
    """Enforce technology_activation consistency on central DH decision bounds.

    Why this exists:
    - ``make_bounds`` keeps positive scaffold uppers for central DH assets so an
      activated technology can be sized by Gold / optimizer / teacher sampling.
    - Dispatch already ignores inactive DH technologies, but CAPEX / OPEX in
      ``Cost_model.financial_model`` still scale with the design capacities that
      were sampled into ``params``.
    - Without this clamp, default ``technology_activation.*=False`` still leaves
      e.g. ``district_heat_pump_kw_th`` open at ``0..7500``. Gold/teacher points
      can therefore accumulate HP/storage/CHP CAPEX while IES never dispatches
      those assets — corrupting NPC labels and optimization objectives.

    Contract:
    - Activation OFF => force related decision variable(s) to 0..0.
    - Activation ON  => leave current bounds untouched (manual / potential caps
      remain authoritative).
    - Missing activation object is a no-op, matching ``apply_feature_bounds``
      when ``engine.features`` is absent; callers that own Settings must pass the
      live ``technology_activation`` SSOT.
    """
    if activation is None:
        return

    idx = make_name_to_index(bounds)
    for activation_attr, var_names in _TECHNOLOGY_ACTIVATION_BOUND_VARS:
        # Explicit False (or missing attr treated as inactive) collapses bounds.
        # Active technologies keep whatever upper was established by scaffold,
        # manual installed_*_max, or energy-potential caps.
        if bool(getattr(activation, activation_attr, False)):
            continue
        for var_name in var_names:
            _force_bound_zero(bounds, idx, var_name)
