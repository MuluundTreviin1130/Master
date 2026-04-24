from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from Data.profiles import location_usage_profiles
from Settings.data.building_stock import make_building_stock
from Settings.data.thermal_archetypes import make_thermal_archetypes
from Settings.technical.building_calibration import make_building_calibration_config
from Technical_model.consumption.heating_anc_cooling_consumption.thermflex_linear_model import (
    derive_ua_w_per_k,
)
from Technical_model.technologies.buildings.calibration.schemas import (
    CalibrationTeacherCohortInput,
    CalibrationTeacherInputBundle,
    CalibrationWeatherRoleInput,
)
from Technical_model.technologies.buildings.runtime_building_params import (
    get_runtime_building_params,
)


def _require_existing_file(path_str: str, *, label: str) -> Path:
    path = Path(path_str).resolve()
    if not path.exists():
        raise FileNotFoundError(f"[building_calibration.from_repo] Missing {label}: {path}")
    if not path.is_file():
        raise FileNotFoundError(f"[building_calibration.from_repo] Expected file for {label}, got: {path}")
    return path


def _load_representative_years(path_str: str, expected_roles: tuple[str, ...]) -> dict[str, int]:
    path = _require_existing_file(path_str, label="representative_years_json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    selected = dict(payload.get("selected_years", {}))
    missing_roles = [role for role in expected_roles if role not in selected]
    if missing_roles:
        raise KeyError(
            "[building_calibration.from_repo] Representative years JSON is missing roles: "
            f"{missing_roles}."
        )
    return {str(role): int(selected[role]) for role in expected_roles}


def _resolve_epw_paths(epw_dir_str: str, representative_years: dict[str, int]) -> list[CalibrationWeatherRoleInput]:
    epw_dir = Path(epw_dir_str).resolve()
    if not epw_dir.exists():
        raise FileNotFoundError(f"[building_calibration.from_repo] Missing pseudo EPW directory: {epw_dir}")
    out: list[CalibrationWeatherRoleInput] = []
    for role, year in representative_years.items():
        matches = sorted(epw_dir.glob(f"vienna_openmeteo_{role}_{year}.epw"))
        if not matches:
            raise FileNotFoundError(
                f"[building_calibration.from_repo] No pseudo EPW found for role='{role}', year={year} in {epw_dir}."
            )
        if len(matches) > 1:
            raise RuntimeError(
                f"[building_calibration.from_repo] Expected exactly one pseudo EPW for role='{role}', year={year}, "
                f"found {len(matches)}."
            )
        out.append(
            CalibrationWeatherRoleInput(
                role=str(role),
                year=int(year),
                epw_path=str(matches[0].resolve()),
            )
        )
    return out


def _validate_usage_profile(path_str: str, *, sheet_name: str, required_columns: tuple[str, ...]) -> Path:
    resolved_path = _require_existing_file(path_str, label="usage_profile_excel_path")
    xls = pd.ExcelFile(resolved_path)
    if sheet_name not in xls.sheet_names:
        raise KeyError(
            f"[building_calibration.from_repo] Usage-profile workbook is missing sheet '{sheet_name}'. "
            f"Available: {xls.sheet_names}"
        )
    df = pd.read_excel(resolved_path, sheet_name=sheet_name, nrows=5)
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        raise KeyError(
            f"[building_calibration.from_repo] Usage-profile sheet '{sheet_name}' is missing required columns: "
            f"{missing_columns}."
        )
    return resolved_path


def _resolve_teacher_glazing_optics(*, sector: str, window_typology_class: str | None) -> tuple[float, float, str]:
    """Resolve explicit teacher glazing optics from SSOT-backed settings.

    Why this helper exists:
    - The archetype layer already carries period-specific residential window typology
      classes from Austrian TABULA.
    - The EnergyPlus teacher uses a simplified `WindowMaterial:SimpleGlazingSystem`
      representation and therefore needs numeric SHGC / visible-transmittance inputs.
    - We resolve that mapping here once, fail fast on missing residential mappings,
      and carry the resolved values explicitly into the teacher input bundle.
    """

    cfg = make_building_calibration_config()
    if str(sector) == "residential":
        if not str(window_typology_class or "").strip():
            raise ValueError(
                "[building_calibration.from_repo] Residential cohort is missing window_typology_class "
                "required for period-specific teacher glazing optics."
            )
        optics = dict(cfg.teacher_window_typology_optics).get(str(window_typology_class))
        if optics is None:
            raise KeyError(
                "[building_calibration.from_repo] No teacher glazing optics configured for "
                f"window_typology_class='{window_typology_class}'."
            )
        shgc = float(optics["shgc"])
        visible_transmittance = float(optics["visible_transmittance"])
        source = str(optics["source"])
        if min(shgc, visible_transmittance) <= 0.0:
            raise ValueError(
                "[building_calibration.from_repo] Resolved residential teacher glazing optics must stay > 0."
            )
        return shgc, visible_transmittance, source

    if str(cfg.teacher_non_residential_simple_glazing_mode) != "global_v1":
        raise ValueError(
            "[building_calibration.from_repo] Unsupported teacher_non_residential_simple_glazing_mode="
            f"'{cfg.teacher_non_residential_simple_glazing_mode}'."
        )
    shgc = float(cfg.teacher_non_residential_simple_glazing_shgc)
    visible_transmittance = float(cfg.teacher_non_residential_simple_glazing_visible_transmittance)
    source = str(cfg.teacher_non_residential_simple_glazing_source)
    if min(shgc, visible_transmittance) <= 0.0:
        raise ValueError(
            "[building_calibration.from_repo] Non-residential teacher glazing optics must stay > 0."
        )
    return shgc, visible_transmittance, source


def build_teacher_input_bundle() -> CalibrationTeacherInputBundle:
    cfg = make_building_calibration_config()
    if str(cfg.usage_profile_excel_path).strip() != str(location_usage_profiles).strip():
        raise ValueError(
            "[building_calibration.from_repo] Usage-profile path must stay on the shared Data.profiles registry SSOT "
            "for V1. If you want to switch the source, change Data.profiles first."
        )

    building_stock = make_building_stock(cfg.location)
    thermal_archetypes = make_thermal_archetypes(cfg.location)
    settings_stub = SimpleNamespace(thermal_archetypes=thermal_archetypes)

    usage_profile_path = _validate_usage_profile(
        cfg.usage_profile_excel_path,
        sheet_name=str(cfg.usage_profile_sheet_name),
        required_columns=tuple(cfg.required_usage_profile_columns),
    )
    representative_years = _load_representative_years(
        cfg.pseudo_epw_representative_years_json,
        expected_roles=tuple(cfg.pseudo_epw_year_roles),
    )
    weather_roles = _resolve_epw_paths(cfg.pseudo_epw_output_dir, representative_years)

    cohort_ids_seen: set[str] = set()
    cohorts_out: list[CalibrationTeacherCohortInput] = []
    for cohort in building_stock.cohorts:
        if cohort.cohort_id in cohort_ids_seen:
            raise ValueError(
                f"[building_calibration.from_repo] Duplicate cohort_id in building-stock SSOT: {cohort.cohort_id}"
            )
        cohort_ids_seen.add(cohort.cohort_id)

        if cohort.thermal_archetype_key not in thermal_archetypes.archetypes:
            raise KeyError(
                "[building_calibration.from_repo] No thermal archetype registered for "
                f"cohort='{cohort.cohort_id}', key='{cohort.thermal_archetype_key}'."
            )
        archetype = thermal_archetypes.archetypes[cohort.thermal_archetype_key]
        member_stub = SimpleNamespace(
            thermal_archetype_key=cohort.thermal_archetype_key,
            represented_gfa_m2=cohort.represented_gfa_m2,
            represented_volume_m3=cohort.represented_volume_m3,
        )
        runtime = get_runtime_building_params(member_stub, settings_obj=settings_stub)
        conditioned_floor_m2 = float(runtime["A_floor"])
        wall_area_m2 = float(runtime["A_wall"])
        window_area_total_m2 = float(sum(runtime["A_window"].values()))
        roof_area_m2 = float(runtime["A_roof"])
        room_height_m = float(runtime["room_height"])
        floor_exposed_area_m2 = float(archetype.floor_exposed_per_gfa) * float(cohort.represented_gfa_m2)
        heat_capacity_wh_per_k = float(runtime["heat_capacity"])
        runtime_ua_w_per_k = float(derive_ua_w_per_k(runtime))
        window_typology_class = (
            None
            if getattr(archetype, "window_typology_class", None) is None
            else str(getattr(archetype, "window_typology_class"))
        )
        teacher_simple_glazing_shgc, teacher_simple_glazing_visible_transmittance, teacher_simple_glazing_source = (
            _resolve_teacher_glazing_optics(
                sector=str(cohort.sector),
                window_typology_class=window_typology_class,
            )
        )

        cohorts_out.append(
            CalibrationTeacherCohortInput(
                cohort_id=str(cohort.cohort_id),
                sector=str(cohort.sector),
                construction_period=str(cohort.construction_period),
                thermal_archetype_key=str(cohort.thermal_archetype_key),
                window_typology_class=window_typology_class,
                window_pane_count=(
                    None
                    if getattr(archetype, "window_pane_count", None) is None
                    else int(getattr(archetype, "window_pane_count"))
                ),
                window_glazing_family=(
                    None
                    if getattr(archetype, "window_glazing_family", None) is None
                    else str(getattr(archetype, "window_glazing_family"))
                ),
                window_frame_type=(
                    None
                    if getattr(archetype, "window_frame_type", None) is None
                    else str(getattr(archetype, "window_frame_type"))
                ),
                window_has_low_e=(
                    None
                    if getattr(archetype, "window_has_low_e", None) is None
                    else bool(getattr(archetype, "window_has_low_e"))
                ),
                window_has_inert_gas_fill=(
                    None
                    if getattr(archetype, "window_has_inert_gas_fill", None) is None
                    else bool(getattr(archetype, "window_has_inert_gas_fill"))
                ),
                window_has_thermal_break=(
                    None
                    if getattr(archetype, "window_has_thermal_break", None) is None
                    else bool(getattr(archetype, "window_has_thermal_break"))
                ),
                window_g_value=(
                    None
                    if getattr(archetype, "window_g_value", None) is None
                    else float(getattr(archetype, "window_g_value"))
                ),
                window_visible_transmittance=(
                    None
                    if getattr(archetype, "window_visible_transmittance", None) is None
                    else float(getattr(archetype, "window_visible_transmittance"))
                ),
                window_data_source_note=(
                    None
                    if getattr(archetype, "window_data_source_note", None) is None
                    else str(getattr(archetype, "window_data_source_note"))
                ),
                glazing_source=(
                    None
                    if getattr(archetype, "glazing_source", None) is None
                    else str(getattr(archetype, "glazing_source"))
                ),
                solar_shading_assumption=(
                    None
                    if getattr(archetype, "solar_shading_assumption", None) is None
                    else str(getattr(archetype, "solar_shading_assumption"))
                ),
                teacher_simple_glazing_shgc=teacher_simple_glazing_shgc,
                teacher_simple_glazing_visible_transmittance=teacher_simple_glazing_visible_transmittance,
                teacher_simple_glazing_source=teacher_simple_glazing_source,
                include_hotwater=bool(cohort.include_hotwater),
                load_profile_mix={str(k): float(v) for k, v in dict(cohort.load_profile_mix).items()},
                dh_connected_share_override=(
                    None
                    if cohort.dh_connected_share_override is None
                    else float(cohort.dh_connected_share_override)
                ),
                represented_gfa_m2=float(cohort.represented_gfa_m2),
                represented_volume_m3=float(cohort.represented_volume_m3),
                conditioned_floor_m2=conditioned_floor_m2,
                floor_exposed_area_m2=floor_exposed_area_m2,
                room_height_m=room_height_m,
                annual_heat_target_kwh=float(cohort.annual_heat_target_kwh),
                annual_space_heat_target_kwh=float(cohort.annual_space_heat_target_kwh),
                annual_hotwater_target_kwh=float(cohort.annual_hotwater_target_kwh),
                annual_electricity_official_kwh=float(cohort.annual_electricity_official_kwh),
                annual_electricity_target_kwh=float(cohort.annual_electricity_target_kwh),
                u_wall=float(runtime["U_wall"]),
                u_window=float(runtime["U_window"]),
                u_roof=float(runtime["U_roof"]),
                u_floor=float(runtime["U_floor"]),
                wall_area_m2=wall_area_m2,
                window_area_total_m2=window_area_total_m2,
                roof_area_m2=roof_area_m2,
                floor_area_m2=conditioned_floor_m2,
                runtime_ua_w_per_k=runtime_ua_w_per_k,
                heat_capacity_wh_per_k=heat_capacity_wh_per_k,
                t_min_k=float(runtime["T_min"]),
                t_max_k=float(runtime["T_max"]),
            )
        )

    return CalibrationTeacherInputBundle(
        schema_version="v1",
        location=str(cfg.location),
        building_stock_source=str(building_stock.source),
        thermal_archetypes_source=str(thermal_archetypes.source),
        source_file_paths=[str(path) for path in building_stock.source_file_paths],
        usage_profile_path=str(usage_profile_path),
        usage_profile_sheet_name=str(cfg.usage_profile_sheet_name),
        usage_profile_required_columns=[str(col) for col in cfg.required_usage_profile_columns],
        representative_years_json=str(Path(cfg.pseudo_epw_representative_years_json).resolve()),
        weather_roles=weather_roles,
        cohorts=cohorts_out,
        notes=[
            "Teacher inputs are derived from existing Vienna building_stock and thermal_archetypes SSOT layers.",
            "Geometry and runtime thermal parameters follow the same cohort/archetype mapping used by the current runtime building path.",
            "Usage profiles remain global for all cohorts in V1 on purpose.",
        ],
    )
