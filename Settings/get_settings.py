from __future__ import annotations

from dataclasses import is_dataclass
from copy import deepcopy
from typing import Any, Dict

from Settings.data.building_stock import make_building_stock
from Settings.data.energy_potentials import make_energy_potentials
from Settings.data.impacts import make_impacts
from Settings.data.thermal_archetypes import make_thermal_archetypes
from Settings.constraints import make_constraints
from Settings.dispatch.dispatch import make_dispatch
from Settings.engines.engine import make_engine, resolve_country_code
from Settings.engines.gating import make_gating
from Settings.market.market import make_market
from Settings.learning import make_learning
from Settings.optimization.optimizer import make_optimizer
from Settings.reporting.reporting import make_reporting
from Settings.run.run import make_run
from Settings.optimization.sampler import make_sampler
from Settings.run.scheduler import make_scheduler
from Settings.surrogate.surrogate import make_surrogate
from Settings.surrogate.train import make_surrogate_train
from Settings.problem.bounds import make_bounds, apply_feature_bounds, Bounds
from Settings.problem.feasibility.verification import make_feasibility_verification
from Settings.problem.hypervolume import make_hypervolume
from Settings.problem.objectives import make_objectives
from Settings.settings_model import Settings
from Settings.technical.bess import make_bess
from Settings.technical.biogas_engine import make_biogas_engine
from Settings.technical.building_calibration import make_building_calibration_config
from Settings.technical.district_biogas_chp import make_district_biogas_chp
from Settings.technical.district_biomass_chp import make_district_biomass_chp
from Settings.technical.district_external_heat import make_district_external_heat
from Settings.technical.district_gas_boiler import make_district_gas_boiler
from Settings.technical.district_gas_chp import make_district_gas_chp
from Settings.technical.district_heating import make_district_heating
from Settings.technical.district_heat_pump import make_district_heat_pump
from Settings.technical.district_thermal_storage import make_district_thermal_storage
from Settings.technical.district_geothermal import make_district_geothermal
from Settings.technical.district_solar_thermal import make_district_solar_thermal
from Settings.technical.district_waste_incineration import make_district_waste_incineration
from Settings.technical.district_wood_chip_boiler import make_district_wood_chip_boiler
from Settings.technical.full_load_hours import make_full_load_hours
from Settings.technical.heating_control import make_heating_control
from Settings.technical.hydrogen import make_hydrogen
from Settings.technical.large_wind import make_large_wind
from Settings.technical.members import MembersConfig, make_members
from Settings.technical.run_of_river_hydro import make_run_of_river_hydro
from Settings.technical.small_wind import make_small_wind
from Settings.technical.technology_activation import make_technology_activation
from Settings.technical.thermal import make_thermal
from Settings.technical.v2h import make_v2h
from Settings.technical.wood_gasifier import make_wood_gasifier
from Settings.validation.holdout import make_validation


def _apply_overrides(obj: Any, override: Any) -> Any:
    """Recursively apply dict overrides to dataclasses and nested dictionaries."""

    if override is None:
        return obj
    if is_dataclass(obj) and isinstance(override, dict):
        for key, value in override.items():
            if not hasattr(obj, key):
                raise KeyError(f"[settings] Unknown override key '{key}' for {type(obj).__name__}")
            cur = getattr(obj, key)
            if is_dataclass(cur) and isinstance(value, dict):
                _apply_overrides(cur, value)
            elif isinstance(cur, dict) and isinstance(value, dict):
                cur.update(value)
            else:
                setattr(obj, key, value)
        return obj
    if isinstance(obj, dict) and isinstance(override, dict):
        obj.update(override)
        return obj
    return override


def _members_from_overrides(overrides: Dict[str, Any] | None) -> MembersConfig:
    tech = (overrides or {}).get("technical", {})
    members_override = tech.get("members")
    if members_override is None:
        return make_members()
    if isinstance(members_override, MembersConfig):
        return members_override
    if isinstance(members_override, dict):
        return make_members(members_override)
    raise TypeError("[settings] technical.members override must be MembersConfig or dict.")


def _has_explicit_members_override(overrides: Dict[str, Any] | None) -> bool:
    tech = (overrides or {}).get("technical", {})
    return "members" in tech


def _extract_caps_overrides(overrides: Dict[str, Any] | None) -> Dict[str, float]:
    b_ovr = (overrides or {}).get("bounds", None)
    if not isinstance(b_ovr, dict):
        return {}
    caps = b_ovr.get("caps", {})
    if not isinstance(caps, dict):
        return {}
    out: Dict[str, float] = {}
    for k, v in caps.items():
        out[str(k)] = float(v)
    return out


def _apply_bounds_struct_overrides(bounds: Bounds, overrides: Dict[str, Any] | None) -> None:
    b_ovr = (overrides or {}).get("bounds", None)
    if not isinstance(b_ovr, dict):
        return
    if isinstance(b_ovr.get("names"), list):
        bounds.names = [str(x) for x in b_ovr["names"]]
    if isinstance(b_ovr.get("lower"), list):
        bounds.lower = [float(x) for x in b_ovr["lower"]]
    if isinstance(b_ovr.get("upper"), list):
        bounds.upper = [float(x) for x in b_ovr["upper"]]
    if isinstance(b_ovr.get("steps"), list):
        bounds.steps = [float(x) for x in b_ovr["steps"]]


def _apply_bounds_variable_overrides(cfg: Settings, overrides: Dict[str, Any], base_upper: Dict[str, float] | None = None) -> None:
    b_ovr = (overrides or {}).get("bounds", None)
    if not isinstance(b_ovr, dict):
        return
    # Variable override form: {"pv_kwp": [lo, hi], ...}
    names = list(cfg.bounds.names)
    idx = {n: i for i, n in enumerate(names)}
    for k, v in b_ovr.items():
        if k in {"names", "lower", "upper", "steps", "caps"}:
            continue
        if k not in idx:
            raise KeyError(f"[settings] Unknown bounds variable '{k}'.")
        if not isinstance(v, (list, tuple)) or len(v) != 2:
            raise ValueError(f"[settings] bounds override for '{k}' must be [lower, upper].")
        i = idx[k]
        lo = float(v[0])
        hi = float(v[1])
        if base_upper is not None and k in base_upper:
            hi = min(hi, float(base_upper[k]))
            lo = min(lo, hi)
        cfg.bounds.lower[i] = lo
        cfg.bounds.upper[i] = hi


def _extract_explicit_variable_upper_bounds(overrides: Dict[str, Any] | None) -> Dict[str, float]:
    b_ovr = (overrides or {}).get("bounds", None)
    if not isinstance(b_ovr, dict):
        return {}
    out: Dict[str, float] = {}
    for k, v in b_ovr.items():
        if k in {"names", "lower", "upper", "steps", "caps"}:
            continue
        if isinstance(v, (list, tuple)) and len(v) == 2:
            out[str(k)] = float(v[1])
    return out


def _resolve_thermal_archetype_variant(overrides: Dict[str, Any] | None) -> str:
    thermal_ovr = (overrides or {}).get("thermal_archetypes")
    if thermal_ovr is None:
        return "calibrated_v1"
    if not isinstance(thermal_ovr, dict):
        raise TypeError("[settings] thermal_archetypes override must be a dict.")
    variant = thermal_ovr.get("variant", "calibrated_v1")
    resolved = str(variant or "").strip()
    if not resolved:
        raise ValueError("[settings] thermal_archetypes.variant must be a non-empty string.")
    return resolved


def _extract_technology_capacity_upper_bounds(cfg: Settings) -> Dict[str, float]:
    mapping = {
        "district_heat_pump_kw_th": getattr(getattr(cfg, "district_heat_pump", None), "installed_kw_th_max", None),
        "district_thermal_storage_kwh_th": getattr(getattr(cfg, "district_thermal_storage", None), "installed_kwh_th_max", None),
        "district_wood_chip_boiler_kw_th": getattr(getattr(cfg, "district_wood_chip_boiler", None), "installed_kw_th_max", None),
        "district_biomass_chp_kw_th": getattr(getattr(cfg, "district_biomass_chp", None), "installed_kw_th_max", None),
        "district_geothermal_kw_el": getattr(getattr(cfg, "district_geothermal", None), "installed_kw_el_max", None),
        "district_gas_chp_kw_el": getattr(getattr(cfg, "district_gas_chp", None), "installed_kw_el_max", None),
        "district_biogas_chp_kw_el": getattr(getattr(cfg, "district_biogas_chp", None), "installed_kw_el_max", None),
        "district_solar_thermal_kw_th": getattr(getattr(cfg, "district_solar_thermal", None), "installed_kw_th_max", None),
        "district_waste_incineration_kw_th": getattr(getattr(cfg, "district_waste_incineration", None), "installed_kw_th_max", None),
    }
    out: Dict[str, float] = {}
    for name, value in mapping.items():
        if value is None:
            continue
        value_f = float(value)
        if value_f <= 0.0:
            raise ValueError(f"[settings] Manual capacity upper bound for '{name}' must be > 0, got {value_f}.")
        out[name] = value_f
    return out


def _apply_manual_technology_capacity_limits(cfg: Settings) -> None:
    manual_caps = _extract_technology_capacity_upper_bounds(cfg)
    if not manual_caps:
        return
    idx = {name: i for i, name in enumerate(cfg.bounds.names)}
    for name, cap in manual_caps.items():
        if name not in idx:
            continue
        i = idx[name]
        cfg.bounds.upper[i] = float(cap)
        cfg.bounds.lower[i] = min(float(cfg.bounds.lower[i]), float(cap))


def _require_manual_bounds_for_nonpotential_central_dh_technologies(cfg: Settings) -> None:
    activation = getattr(cfg, "technology_activation", None)
    if activation is None:
        return

    required = [
        ("district_heat_pump", "district_heat_pump", "installed_kw_th_max"),
        ("district_thermal_storage", "district_thermal_storage", "installed_kwh_th_max"),
        ("district_geothermal", "district_geothermal", "installed_kw_el_max"),
        ("district_gas_chp", "district_gas_chp", "installed_kw_el_max"),
    ]
    for activation_attr, config_attr, bound_attr in required:
        if not bool(getattr(activation, activation_attr, False)):
            continue
        tech_cfg = getattr(cfg, config_attr, None)
        value = getattr(tech_cfg, bound_attr, None) if tech_cfg is not None else None
        if value is None:
            raise ValueError(
                f"[settings] {config_attr} is active, but {config_attr}.{bound_attr} is missing. "
                "For these central DH technologies there is no energy-potential cap; a manual installed_*_max "
                "must be set explicitly instead of falling back to the generic bounds scaffold."
            )


def _apply_energy_potential_caps(cfg: Settings, overrides: Dict[str, Any] | None = None) -> None:
    potentials = getattr(cfg, "energy_potentials", None)
    if potentials is None or not bool(getattr(potentials, "enforce_hard_caps", False)):
        return
    caps = potentials.to_bounds_caps()
    if not caps:
        return
    explicit_variable_uppers = _extract_explicit_variable_upper_bounds(overrides)
    manual_technology_uppers = _extract_technology_capacity_upper_bounds(cfg)
    central_absolute_cap_names = {
        "district_heat_pump_kw_th",
        "district_thermal_storage_kwh_th",
        "district_wood_chip_boiler_kw_th",
        "district_biomass_chp_kw_th",
        "district_geothermal_kw_el",
        "district_gas_chp_kw_el",
        "district_biogas_chp_kw_el",
    }
    idx = {name: i for i, name in enumerate(cfg.bounds.names)}
    for name, cap in caps.items():
        if name not in idx:
            continue
        i = idx[name]
        current_upper = float(cfg.bounds.upper[i])
        if name in central_absolute_cap_names:
            hi = float(cap)
            if name in manual_technology_uppers:
                hi = min(hi, float(manual_technology_uppers[name]))
            if name in explicit_variable_uppers:
                hi = min(hi, float(explicit_variable_uppers[name]))
        else:
            hi = min(current_upper, float(cap))
        lo = min(float(cfg.bounds.lower[i]), hi)
        cfg.bounds.lower[i] = lo
        cfg.bounds.upper[i] = hi


def _tighten_optional_cap(current_cap: Any, derived_cap: float) -> float:
    if current_cap is None:
        return float(derived_cap)
    return float(min(float(current_cap), float(derived_cap)))


def _require_positive_float(value: Any, *, label: str) -> float:
    if value is None:
        raise ValueError(f"[settings] {label} must not be None.")
    value_f = float(value)
    if value_f <= 0.0:
        raise ValueError(f"[settings] {label} must be > 0, got {value_f}.")
    return value_f


def _validate_district_gas_chp_operating_region(cfg: Settings) -> None:
    """Fail fast on incomplete future CHP operating-region settings.

    The active runtime still defaults to ``fixed_ratio``. Once the explicit
    piecewise region is selected we require the operating points to be fully
    specified in Settings, so later dispatch code never has to invent or
    silently infer missing CHP modes.
    """

    gas_cfg = getattr(cfg, "district_gas_chp", None)
    if gas_cfg is None:
        return

    mode = str(getattr(gas_cfg, "operating_mode_model", "fixed_ratio") or "fixed_ratio").strip().lower()
    if mode not in {"fixed_ratio", "piecewise_power_heat_v1"}:
        raise ValueError(
            "[settings] district_gas_chp.operating_mode_model must be either "
            "'fixed_ratio' or 'piecewise_power_heat_v1'."
        )
    power_priority_mode = str(getattr(gas_cfg, "power_priority_mode", "free") or "free").strip().lower()
    if power_priority_mode not in {"free", "price_spike_gated_v1"}:
        raise ValueError(
            "[settings] district_gas_chp.power_priority_mode must be either "
            "'free' or 'price_spike_gated_v1'."
        )
    power_priority_quantile = float(getattr(gas_cfg, "power_priority_price_quantile", 0.0) or 0.0)
    if not (0.0 < power_priority_quantile <= 1.0):
        raise ValueError(
            "[settings] district_gas_chp.power_priority_price_quantile must be within (0, 1]."
        )

    points = tuple(getattr(gas_cfg, "operating_points_v1", ()) or ())
    names_seen: set[str] = set()
    max_eta_el = 0.0
    if mode == "piecewise_power_heat_v1" and len(points) < 2:
        raise ValueError(
            "[settings] district_gas_chp.operating_points_v1 must contain at least two points "
            "when district_gas_chp.operating_mode_model='piecewise_power_heat_v1'."
        )
    for idx, point in enumerate(points):
        name = str(getattr(point, "name", "") or "").strip()
        if not name:
            raise ValueError(
                "[settings] district_gas_chp.operating_points_v1 entries require a non-empty 'name'."
            )
        if name in names_seen:
            raise ValueError(
                f"[settings] district_gas_chp.operating_points_v1 contains duplicate point name '{name}'."
            )
        names_seen.add(name)
        eta_el = _require_positive_float(
            getattr(point, "eta_el", None),
            label=f"district_gas_chp.operating_points_v1[{idx}].eta_el",
        )
        eta_th = _require_positive_float(
            getattr(point, "eta_th", None),
            label=f"district_gas_chp.operating_points_v1[{idx}].eta_th",
        )
        if eta_el + eta_th > 1.0 + 1e-9:
            raise ValueError(
                "[settings] district_gas_chp.operating_points_v1 total efficiency must not exceed 1.0. "
                f"Point '{name}' has eta_el + eta_th = {eta_el + eta_th:.4f}."
            )
        max_eta_el = max(max_eta_el, float(eta_el))

    if mode == "piecewise_power_heat_v1":
        if max_eta_el <= 0.0:
            raise ValueError(
                "[settings] district_gas_chp.operating_points_v1 must contain a positive electric anchor."
            )
        if power_priority_mode == "price_spike_gated_v1" and "power_led" not in names_seen:
            raise ValueError(
                "[settings] district_gas_chp.power_priority_mode='price_spike_gated_v1' requires "
                "an operating point named 'power_led'."
            )
        # The legacy fields stay required because the rest of the current repo
        # still uses them outside the day-ahead MILP path. Keeping them present
        # avoids hidden partial support while the dispatch upgrade is in flight.
        _require_positive_float(getattr(gas_cfg, "eta_el", None), label="district_gas_chp.eta_el")
        _require_positive_float(getattr(gas_cfg, "eta_th", None), label="district_gas_chp.eta_th")
        _require_positive_float(
            getattr(gas_cfg, "fuel_lhv_kwh_per_m3", None),
            label="district_gas_chp.fuel_lhv_kwh_per_m3",
        )
        _require_positive_float(
            getattr(gas_cfg, "min_partload", None),
            label="district_gas_chp.min_partload",
        )


def _validate_activated_district_chps(cfg: Settings) -> None:
    """Fail fast when activated CHPs lack eta/LHV/partload SSOT fields.

    Heuristic DH source modules already require these attributes. The MILP path
    previously coerced ``fuel_lhv_*=None`` to ``1.0``, which silently scaled fuel
    mass/volume and EUR fuel terms by orders of magnitude (fuel ~ 1/LHV).
    """

    activation = getattr(cfg, "technology_activation", None)
    if activation is None:
        return

    if bool(getattr(activation, "district_biomass_chp", False)):
        biomass_cfg = getattr(cfg, "district_biomass_chp", None)
        eta_el = _require_positive_float(
            getattr(biomass_cfg, "eta_el", None) if biomass_cfg is not None else None,
            label="district_biomass_chp.eta_el",
        )
        eta_th = _require_positive_float(
            getattr(biomass_cfg, "eta_th", None) if biomass_cfg is not None else None,
            label="district_biomass_chp.eta_th",
        )
        if eta_el > 1.0 or eta_th > 1.0:
            raise ValueError(
                "[settings] district_biomass_chp eta_el/eta_th must be <= 1, "
                f"got eta_el={eta_el}, eta_th={eta_th}."
            )
        _require_positive_float(
            getattr(biomass_cfg, "fuel_lhv_kwh_per_kg", None) if biomass_cfg is not None else None,
            label="district_biomass_chp.fuel_lhv_kwh_per_kg",
        )
        min_partload = getattr(biomass_cfg, "min_partload", None) if biomass_cfg is not None else None
        if min_partload is None:
            raise ValueError(
                "[settings] district_biomass_chp.min_partload is required when "
                "technology_activation.district_biomass_chp is enabled."
            )
        min_pl = float(min_partload)
        if not 0.0 <= min_pl <= 1.0:
            raise ValueError(
                "[settings] district_biomass_chp.min_partload must satisfy 0 <= min_partload <= 1."
            )

    if bool(getattr(activation, "district_biogas_chp", False)):
        biogas_cfg = getattr(cfg, "district_biogas_chp", None)
        eta_el = _require_positive_float(
            getattr(biogas_cfg, "eta_el", None) if biogas_cfg is not None else None,
            label="district_biogas_chp.eta_el",
        )
        eta_th = _require_positive_float(
            getattr(biogas_cfg, "eta_th", None) if biogas_cfg is not None else None,
            label="district_biogas_chp.eta_th",
        )
        if eta_el > 1.0 or eta_th > 1.0:
            raise ValueError(
                "[settings] district_biogas_chp eta_el/eta_th must be <= 1, "
                f"got eta_el={eta_el}, eta_th={eta_th}."
            )
        _require_positive_float(
            getattr(biogas_cfg, "fuel_lhv_kwh_per_nm3", None) if biogas_cfg is not None else None,
            label="district_biogas_chp.fuel_lhv_kwh_per_nm3",
        )
        min_partload = getattr(biogas_cfg, "min_partload", None) if biogas_cfg is not None else None
        if min_partload is None:
            raise ValueError(
                "[settings] district_biogas_chp.min_partload is required when "
                "technology_activation.district_biogas_chp is enabled."
            )
        min_pl = float(min_partload)
        if not 0.0 <= min_pl <= 1.0:
            raise ValueError(
                "[settings] district_biogas_chp.min_partload must satisfy 0 <= min_partload <= 1."
            )

    if bool(getattr(activation, "district_gas_chp", False)):
        gas_cfg = getattr(cfg, "district_gas_chp", None)
        eta_el = _require_positive_float(
            getattr(gas_cfg, "eta_el", None) if gas_cfg is not None else None,
            label="district_gas_chp.eta_el",
        )
        eta_th = _require_positive_float(
            getattr(gas_cfg, "eta_th", None) if gas_cfg is not None else None,
            label="district_gas_chp.eta_th",
        )
        if eta_el > 1.0 or eta_th > 1.0:
            raise ValueError(
                "[settings] district_gas_chp eta_el/eta_th must be <= 1, "
                f"got eta_el={eta_el}, eta_th={eta_th}."
            )
        # Activation-gated LHV is required for every operating mode. Piecewise mode
        # already checks LHV in `_validate_district_gas_chp_operating_region`; fixed_ratio
        # previously skipped it and let the MILP path invent fuel_lhv=1.0.
        _require_positive_float(
            getattr(gas_cfg, "fuel_lhv_kwh_per_m3", None) if gas_cfg is not None else None,
            label="district_gas_chp.fuel_lhv_kwh_per_m3",
        )
        min_partload = getattr(gas_cfg, "min_partload", None) if gas_cfg is not None else None
        if min_partload is None:
            raise ValueError(
                "[settings] district_gas_chp.min_partload is required when "
                "technology_activation.district_gas_chp is enabled."
            )
        min_pl = float(min_partload)
        if not 0.0 <= min_pl <= 1.0:
            raise ValueError(
                "[settings] district_gas_chp.min_partload must satisfy 0 <= min_partload <= 1."
            )


def _validate_dispatch_objective_components(cfg: Settings) -> None:
    """Fail fast on unsupported dispatch objective component names."""

    components = getattr(getattr(cfg, "dispatch", None), "objective_components", None)
    if not isinstance(components, list) or not components:
        raise ValueError("[settings] dispatch.objective_components must be a non-empty list.")
    allowed = {
        "grid_import_cost",
        "grid_export_revenue",
        "fuel_cost",
        "co2_cost",
        "variable_opex",
        "unserved_penalty",
        "spill_penalty",
        "thermflex_activation_penalty",
        "temperature_violation_penalty",
    }
    invalid = [str(item) for item in components if str(item) not in allowed]
    if invalid:
        raise ValueError(
            "[settings] Unsupported dispatch.objective_components entries: "
            f"{invalid}. Allowed: {sorted(allowed)}"
        )


def _derive_capacity_caps_from_annual_potentials(cfg: Settings) -> Dict[str, Dict[str, float]]:
    potentials = getattr(cfg, "energy_potentials", None)
    activation = getattr(cfg, "technology_activation", None)
    full_load_hours = getattr(cfg, "full_load_hours", None)
    if potentials is None or activation is None or full_load_hours is None:
        return {}

    shared_caps: Dict[str, Dict[str, float]] = {}

    if bool(getattr(activation, "district_biogas_chp", False)):
        biogas_cfg = getattr(cfg, "district_biogas_chp", None)
        annual_fuel_gwh = getattr(potentials, "district_biogas_feedstock_gwh_per_year_max", None)
        if annual_fuel_gwh is not None:
            eta_el = _require_positive_float(
                getattr(biogas_cfg, "eta_el", None) if biogas_cfg is not None else None,
                label="district_biogas_chp.eta_el",
            )
            flh = _require_positive_float(
                getattr(full_load_hours, "district_biogas_chp", None),
                label="full_load_hours.district_biogas_chp",
            )
            derived_cap_kw_el = float(annual_fuel_gwh) * 1_000_000.0 * eta_el / flh
            potentials.district_biogas_chp_kw_el_max = _tighten_optional_cap(
                getattr(potentials, "district_biogas_chp_kw_el_max", None),
                derived_cap_kw_el,
            )

    if bool(getattr(activation, "district_solar_thermal", False)):
        solar_cfg = getattr(cfg, "district_solar_thermal", None)
        annual_solar_gwh = getattr(potentials, "district_solar_thermal_total_gwh_per_year_max", None)
        if annual_solar_gwh is not None:
            solar_flh = _require_positive_float(
                getattr(full_load_hours, "district_solar_thermal", None),
                label="full_load_hours.district_solar_thermal",
            )
            solar_cap_kw_th = float(annual_solar_gwh) * 1_000_000.0 / solar_flh
            potentials.district_solar_thermal_kw_th_max = _tighten_optional_cap(
                getattr(potentials, "district_solar_thermal_kw_th_max", None),
                solar_cap_kw_th,
            )

    if bool(getattr(activation, "district_waste_incineration", False)):
        waste_cfg = getattr(cfg, "district_waste_incineration", None)
        annual_waste_gwh = getattr(potentials, "district_waste_incineration_gwh_per_year_max", None)
        if annual_waste_gwh is not None:
            waste_flh = _require_positive_float(
                getattr(full_load_hours, "district_waste_incineration", None),
                label="full_load_hours.district_waste_incineration",
            )
            waste_cap_kw_th = float(annual_waste_gwh) * 1_000_000.0 / waste_flh
            potentials.district_waste_incineration_kw_th_max = _tighten_optional_cap(
                getattr(potentials, "district_waste_incineration_kw_th_max", None),
                waste_cap_kw_th,
            )

    biomass_active = bool(getattr(activation, "district_biomass_chp", False))
    wood_active = bool(getattr(activation, "district_wood_chip_boiler", False))
    annual_biomass_fuel_gwh = getattr(potentials, "district_biomass_feedstock_gwh_per_year_max", None)
    if annual_biomass_fuel_gwh is not None and (biomass_active or wood_active):
        annual_biomass_fuel_kwh = float(annual_biomass_fuel_gwh) * 1_000_000.0

        if biomass_active:
            biomass_cfg = getattr(cfg, "district_biomass_chp", None)
            biomass_eta_th = _require_positive_float(
                getattr(biomass_cfg, "eta_th", None) if biomass_cfg is not None else None,
                label="district_biomass_chp.eta_th",
            )
            biomass_flh = _require_positive_float(
                getattr(full_load_hours, "district_biomass_chp", None),
                label="full_load_hours.district_biomass_chp",
            )
            biomass_cap_kw_th = annual_biomass_fuel_kwh * biomass_eta_th / biomass_flh
            potentials.district_biomass_chp_kw_th_max = _tighten_optional_cap(
                getattr(potentials, "district_biomass_chp_kw_th_max", None),
                biomass_cap_kw_th,
            )
        else:
            biomass_eta_th = None
            biomass_flh = None

        if wood_active:
            wood_cfg = getattr(cfg, "district_wood_chip_boiler", None)
            wood_eta_th = _require_positive_float(
                getattr(wood_cfg, "eta_th", None) if wood_cfg is not None else None,
                label="district_wood_chip_boiler.eta_th",
            )
            wood_flh = _require_positive_float(
                getattr(full_load_hours, "district_wood_chip_boiler", None),
                label="full_load_hours.district_wood_chip_boiler",
            )
            wood_cap_kw_th = annual_biomass_fuel_kwh * wood_eta_th / wood_flh
            potentials.district_wood_chip_boiler_kw_th_max = _tighten_optional_cap(
                getattr(potentials, "district_wood_chip_boiler_kw_th_max", None),
                wood_cap_kw_th,
            )
        else:
            wood_eta_th = None
            wood_flh = None

        if biomass_active and wood_active:
            shared_caps["district_biomass_wood_fuel_capacity_max"] = {
                "annual_fuel_kwh": annual_biomass_fuel_kwh,
                "district_biomass_chp_eta_th": float(biomass_eta_th),
                "district_biomass_chp_full_load_hours_per_year": float(biomass_flh),
                "district_wood_chip_boiler_eta_th": float(wood_eta_th),
                "district_wood_chip_boiler_full_load_hours_per_year": float(wood_flh),
            }

    return shared_caps


def _validate_fixed_capacity_against_annual_potential(
    *,
    tech_name: str,
    installed_kw: Any,
    full_load_hours_per_year: Any,
    annual_potential_gwh: Any,
) -> None:
    if installed_kw is None:
        return
    if annual_potential_gwh is None:
        raise ValueError(
            f"[settings] {tech_name} has fixed installed capacity configured, but the annual potential is missing."
        )
    if full_load_hours_per_year is None:
        raise ValueError(
            f"[settings] {tech_name} has fixed installed capacity configured, but the required full_load_hours entry is missing."
        )

    installed_kw_f = float(installed_kw)
    flh = float(full_load_hours_per_year)
    annual_potential_kwh = float(annual_potential_gwh) * 1_000_000.0
    if installed_kw_f < 0.0:
        raise ValueError(f"[settings] {tech_name}.installed_kw must be >= 0, got {installed_kw_f}.")
    if flh <= 0.0:
        raise ValueError(
            f"[settings] full_load_hours entry for {tech_name} must be > 0, got {flh}."
        )
    implied_annual_output_kwh = installed_kw_f * flh
    if implied_annual_output_kwh > annual_potential_kwh:
        implied_capacity_cap_kw = annual_potential_kwh / flh
        raise ValueError(
            f"[settings] {tech_name} fixed capacity is inconsistent with the configured annual potential: "
            f"{installed_kw_f:.3f} kW * {flh:.1f} h/a = {implied_annual_output_kwh:.3f} kWh/a exceeds "
            f"{annual_potential_kwh:.3f} kWh/a. "
            f"With the current full-load-hour assumption, the implied upper bound is {implied_capacity_cap_kw:.3f} kW."
        )


def _validate_fixed_capacity_against_capacity_limit(
    *,
    tech_name: str,
    installed_kw: Any,
    configured_capacity_limit_kw: Any,
    potential_capacity_limit_kw: Any,
) -> None:
    if installed_kw is None:
        return
    installed_kw_f = float(installed_kw)
    if installed_kw_f < 0.0:
        raise ValueError(f"[settings] {tech_name}.installed_kw must be >= 0, got {installed_kw_f}.")

    effective_limit_kw = None
    if configured_capacity_limit_kw is not None:
        configured_limit_f = float(configured_capacity_limit_kw)
        if configured_limit_f <= 0.0:
            raise ValueError(
                f"[settings] {tech_name}.installed_kw_max must be > 0 when provided, got {configured_limit_f}."
            )
        effective_limit_kw = configured_limit_f
    if potential_capacity_limit_kw is not None:
        potential_limit_f = float(potential_capacity_limit_kw)
        if potential_limit_f <= 0.0:
            raise ValueError(
                f"[settings] derived potential limit for {tech_name} must be > 0 when provided, got {potential_limit_f}."
            )
        effective_limit_kw = (
            potential_limit_f
            if effective_limit_kw is None
            else min(effective_limit_kw, potential_limit_f)
        )

    if effective_limit_kw is None:
        return
    if installed_kw_f > effective_limit_kw:
        raise ValueError(
            f"[settings] {tech_name}.installed_kw_th_fixed={installed_kw_f:.3f} kW exceeds the effective hard upper bound "
            f"of {effective_limit_kw:.3f} kW. "
            "The effective limit is min(manual installed_kw_th_max, derived energy-potential cap)."
        )


def _validate_energy_potential_alignment(cfg: Settings) -> None:
    activation = getattr(cfg, "technology_activation", None)
    potentials = getattr(cfg, "energy_potentials", None)
    full_load_hours = getattr(cfg, "full_load_hours", None)
    if activation is None or potentials is None or full_load_hours is None:
        return

    if bool(getattr(activation, "district_solar_thermal", False)):
        solar_cfg = getattr(cfg, "district_solar_thermal", None)
        _validate_fixed_capacity_against_annual_potential(
            tech_name="district_solar_thermal",
            installed_kw=getattr(solar_cfg, "installed_kw_th_fixed", None) if solar_cfg is not None else None,
            full_load_hours_per_year=getattr(full_load_hours, "district_solar_thermal", None),
            annual_potential_gwh=getattr(potentials, "district_solar_thermal_total_gwh_per_year_max", None),
        )
        _validate_fixed_capacity_against_capacity_limit(
            tech_name="district_solar_thermal",
            installed_kw=getattr(solar_cfg, "installed_kw_th_fixed", None) if solar_cfg is not None else None,
            configured_capacity_limit_kw=(
                getattr(solar_cfg, "installed_kw_th_max", None) if solar_cfg is not None else None
            ),
            potential_capacity_limit_kw=getattr(potentials, "district_solar_thermal_kw_th_max", None),
        )

    if bool(getattr(activation, "district_waste_incineration", False)):
        waste_cfg = getattr(cfg, "district_waste_incineration", None)
        _validate_fixed_capacity_against_annual_potential(
            tech_name="district_waste_incineration",
            installed_kw=getattr(waste_cfg, "installed_kw_th_fixed", None) if waste_cfg is not None else None,
            full_load_hours_per_year=getattr(full_load_hours, "district_waste_incineration", None),
            annual_potential_gwh=getattr(potentials, "district_waste_incineration_gwh_per_year_max", None),
        )
        _validate_fixed_capacity_against_capacity_limit(
            tech_name="district_waste_incineration",
            installed_kw=getattr(waste_cfg, "installed_kw_th_fixed", None) if waste_cfg is not None else None,
            configured_capacity_limit_kw=(
                getattr(waste_cfg, "installed_kw_th_max", None) if waste_cfg is not None else None
            ),
            potential_capacity_limit_kw=getattr(potentials, "district_waste_incineration_kw_th_max", None),
        )


def _attach_central_capacity_constraints(cfg: Settings, shared_caps: Dict[str, Dict[str, float]]) -> None:
    if not shared_caps:
        return
    names = list(getattr(cfg.constraints, "names", []) or [])
    senses = list(getattr(cfg.constraints, "senses", []) or [])
    rhs = list(getattr(cfg.constraints, "rhs", []) or [])
    cfg_dict = dict(getattr(cfg.constraints, "cfg", {}) or {})
    central_caps_cfg = dict(cfg_dict.get("central_capacity_caps", {}) or {})

    for name, payload in shared_caps.items():
        if name not in names:
            names.append(name)
            senses.append("<=")
            rhs.append(float(payload["annual_fuel_kwh"]))
        central_caps_cfg[name] = dict(payload)

    cfg.constraints.names = names
    cfg.constraints.senses = senses
    cfg.constraints.rhs = rhs
    cfg_dict["central_capacity_caps"] = central_caps_cfg
    cfg.constraints.cfg = cfg_dict


def _apply_constraints_overrides(cfg: Settings, overrides: Dict[str, Any] | None) -> None:
    c_ovr = (overrides or {}).get("constraints", None)
    if not isinstance(c_ovr, dict):
        return

    names = list(getattr(cfg.constraints, "names", []) or [])
    senses = list(getattr(cfg.constraints, "senses", []) or [])
    rhs = [float(x) for x in (getattr(cfg.constraints, "rhs", []) or [])]
    cfg_dict = dict(getattr(cfg.constraints, "cfg", {}) or {})

    if "names" in c_ovr:
        if not isinstance(c_ovr["names"], list):
            raise TypeError("[settings] constraints.names override must be a list.")
        names = [str(x) for x in c_ovr["names"]]
    if "senses" in c_ovr:
        if not isinstance(c_ovr["senses"], list):
            raise TypeError("[settings] constraints.senses override must be a list.")
        senses = [str(x) for x in c_ovr["senses"]]
    if "rhs" in c_ovr:
        if not isinstance(c_ovr["rhs"], list):
            raise TypeError("[settings] constraints.rhs override must be a list.")
        rhs = [float(x) for x in c_ovr["rhs"]]
    if "cfg" in c_ovr:
        if not isinstance(c_ovr["cfg"], dict):
            raise TypeError("[settings] constraints.cfg override must be a dict.")
        cfg_dict.update(c_ovr["cfg"])

    for section_name in ("problem", "storage", "hydrogen", "policy", "dispatch", "thermflex"):
        section_override = c_ovr.get(section_name)
        if section_override is None:
            continue
        if not isinstance(section_override, dict):
            raise TypeError(f"[settings] constraints.{section_name} override must be a dict.")
        section_obj = getattr(cfg.constraints, section_name, None)
        if section_obj is None:
            raise KeyError(f"[settings] Unknown constraints section '{section_name}'.")
        _apply_overrides(section_obj, section_override)

    if not (len(names) == len(senses) == len(rhs)):
        raise ValueError(
            "[settings] constraints override must keep names/senses/rhs aligned. "
            f"Got lengths names={len(names)}, senses={len(senses)}, rhs={len(rhs)}."
        )

    cfg.constraints.names = names
    cfg.constraints.senses = senses
    cfg.constraints.rhs = rhs
    cfg.constraints.cfg = cfg_dict
    cfg.constraints.problem.names = list(names)
    cfg.constraints.problem.senses = list(senses)
    cfg.constraints.problem.rhs = list(rhs)
    cfg.constraints.problem.cfg = dict(cfg_dict)


def get_settings(overrides: Dict[str, Any] | None = None) -> Settings:
    """Compose settings from defaults and apply optional runtime overrides.

    This is the single source of truth. CLI/config helpers must only construct
    ``overrides`` and pass them here.

    Config groups are organized under:
    - ``Settings.run``
    - ``Settings.optimization``
    - ``Settings.engines``
    - ``Settings.surrogate``
    - ``Settings.reporting``
    - ``Settings.problem``
    - ``Settings.dispatch``
    - ``Settings.technical``
    - ``Settings.market``
    - ``Settings.data``
    - ``Settings.validation``
    """

    members = _members_from_overrides(overrides)
    engine = make_engine(members=members)

    # Engine overrides first so derived fields can be refreshed.
    if overrides and isinstance(overrides.get("engine"), dict):
        _apply_overrides(engine, overrides["engine"])
        engine.country_code = resolve_country_code(engine.location)
        engine.N_EC = engine.members.N_EC
        engine.N_HH = engine.members.N_HH

    impacts = make_impacts()
    building_stock = make_building_stock(location=engine.location)
    if not _has_explicit_members_override(overrides) and getattr(building_stock, "cohorts", None):
        engine.members = make_members(building_stock=building_stock)
        engine.N_EC = engine.members.N_EC
        engine.N_HH = engine.members.N_HH
    energy_potentials = make_energy_potentials(location=engine.location)
    thermal_archetype_variant = _resolve_thermal_archetype_variant(overrides)
    thermal_archetypes = make_thermal_archetypes(location=engine.location, variant=thermal_archetype_variant)
    building_calibration = make_building_calibration_config()
    thermal = make_thermal()
    heating_control = make_heating_control()
    bess = make_bess()
    hydrogen = make_hydrogen()
    v2h = make_v2h()
    small_wind = make_small_wind()
    large_wind = make_large_wind()
    run_of_river_hydro = make_run_of_river_hydro(location=engine.location)
    biogas_engine = make_biogas_engine()
    district_heating = make_district_heating(location=engine.location)
    technology_activation = make_technology_activation()
    district_heat_pump = make_district_heat_pump()
    district_thermal_storage = make_district_thermal_storage()
    district_biogas_chp = make_district_biogas_chp()
    district_biomass_chp = make_district_biomass_chp()
    district_external_heat = make_district_external_heat()
    district_gas_boiler = make_district_gas_boiler()
    district_gas_chp = make_district_gas_chp()
    district_solar_thermal = make_district_solar_thermal(location=engine.location)
    district_geothermal = make_district_geothermal()
    district_waste_incineration = make_district_waste_incineration()
    district_wood_chip_boiler = make_district_wood_chip_boiler()
    full_load_hours = make_full_load_hours()
    wood_gasifier = make_wood_gasifier()
    run = make_run()
    caps_override = _extract_caps_overrides(overrides)
    bounds = make_bounds(engine, caps=caps_override)
    objectives = make_objectives()
    constraints = make_constraints(engine, lifetime_years=25)
    feasibility = make_feasibility_verification()
    hypervolume = make_hypervolume()
    sampler = make_sampler()
    optimizer = make_optimizer()
    reporting = make_reporting()
    surrogate_train = make_surrogate_train()
    surrogate = make_surrogate()
    gating = make_gating()
    scheduler = make_scheduler()
    learning = make_learning()
    validation = make_validation()
    market = make_market()
    dispatch = make_dispatch()

    cfg = Settings(
        run=run,
        engine=engine,
        bounds=bounds,
        objectives=objectives,
        constraints=constraints,
        feasibility=feasibility,
        hypervolume=hypervolume,
        sampler=sampler,
        optimizer=optimizer,
        reporting=reporting,
        surrogate_train=surrogate_train,
        surrogate=surrogate,
        gating=gating,
        scheduler=scheduler,
        learning=learning,
        validation=validation,
        market=market,
        dispatch=dispatch,
        building_stock=building_stock,
        thermal_archetypes=thermal_archetypes,
        building_calibration=building_calibration,
        thermal=thermal,
        heating_control=heating_control,
        bess=bess,
        hydrogen=hydrogen,
        v2h=v2h,
        small_wind=small_wind,
        large_wind=large_wind,
        run_of_river_hydro=run_of_river_hydro,
        biogas_engine=biogas_engine,
        district_heating=district_heating,
        technology_activation=technology_activation,
        district_heat_pump=district_heat_pump,
        district_thermal_storage=district_thermal_storage,
        district_biogas_chp=district_biogas_chp,
        district_biomass_chp=district_biomass_chp,
        district_external_heat=district_external_heat,
        district_gas_boiler=district_gas_boiler,
        district_gas_chp=district_gas_chp,
        district_solar_thermal=district_solar_thermal,
        district_geothermal=district_geothermal,
        district_waste_incineration=district_waste_incineration,
        district_wood_chip_boiler=district_wood_chip_boiler,
        full_load_hours=full_load_hours,
        wood_gasifier=wood_gasifier,
        energy_potentials=energy_potentials,
        impacts=impacts,
    )

    if overrides:
        overrides_clean = deepcopy(overrides)
        b_ovr = overrides_clean.get("bounds")
        if isinstance(b_ovr, dict):
            overrides_clean["bounds"] = {k: v for k, v in b_ovr.items() if k in {"names", "lower", "upper", "steps"}}
        # Apply overrides across top-level settings fields.
        _apply_overrides(cfg, overrides_clean)
        _apply_bounds_variable_overrides(cfg, overrides)
        cfg.engine.country_code = resolve_country_code(cfg.engine.location)
        cfg.engine.N_EC = cfg.engine.members.N_EC
        cfg.engine.N_HH = cfg.engine.members.N_HH

    # Final recompute from merged engine + caps (single source of truth for member-scaled bounds).
    final_caps_override = _extract_caps_overrides(overrides)
    cfg.bounds = make_bounds(cfg.engine, caps=final_caps_override or getattr(cfg.bounds, "caps", {}))
    # Apply explicit bounds-structure overrides (legacy compatibility).
    _apply_bounds_struct_overrides(cfg.bounds, overrides)

    # Final hard clamp for feature OFF in case legacy overrides attempted to re-open bounds.
    apply_feature_bounds(cfg.engine, cfg.bounds)
    shared_capacity_caps = _derive_capacity_caps_from_annual_potentials(cfg)
    _require_manual_bounds_for_nonpotential_central_dh_technologies(cfg)
    _apply_manual_technology_capacity_limits(cfg)
    _apply_energy_potential_caps(cfg, overrides)
    apply_feature_bounds(cfg.engine, cfg.bounds)
    # Apply per-variable overrides only after all manual/potential upper caps are known.
    base_upper = {cfg.bounds.names[i]: float(cfg.bounds.upper[i]) for i in range(len(cfg.bounds.names))}
    if overrides:
        _apply_bounds_variable_overrides(cfg, overrides, base_upper=base_upper)
    apply_feature_bounds(cfg.engine, cfg.bounds)
    _validate_energy_potential_alignment(cfg)
    _validate_district_gas_chp_operating_region(cfg)
    _validate_activated_district_chps(cfg)
    _validate_dispatch_objective_components(cfg)
    cfg.constraints = make_constraints(cfg.engine, lifetime_years=25)
    _attach_central_capacity_constraints(cfg, shared_capacity_caps)
    _apply_constraints_overrides(cfg, overrides)

    # Locked reproducibility rule: export credit must remain zero.
    if float(cfg.impacts.export_credit) != 0.0:
        raise ValueError("[settings] impacts.export_credit must be 0.0 for paper/validation reproducibility.")

    return cfg
