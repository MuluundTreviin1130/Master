from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from Settings.technical.building_calibration import (
    BuildingCalibrationExperimentTemplate,
    make_building_calibration_config,
)
from Technical_model.technologies.buildings.calibration.schemas import (
    CalibrationExperimentLibrary,
    CalibrationExperimentSpec,
)


def _load_representative_years(path_str: str, expected_roles: tuple[str, ...]) -> dict[str, int]:
    path = Path(path_str).resolve()
    if not path.exists():
        raise FileNotFoundError(f"[building_calibration.experiments] Missing representative years JSON: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    selected = dict(payload.get("selected_years", {}))
    missing_roles = [role for role in expected_roles if role not in selected]
    if missing_roles:
        raise KeyError(
            f"[building_calibration.experiments] Representative years JSON is missing roles: {missing_roles}."
        )
    return {str(role): int(selected[role]) for role in expected_roles}


def _resolve_epw_path(role: str, year: int, epw_dir_str: str) -> Path:
    epw_dir = Path(epw_dir_str).resolve()
    matches = sorted(epw_dir.glob(f"vienna_openmeteo_{role}_{year}.epw"))
    if not matches:
        raise FileNotFoundError(
            f"[building_calibration.experiments] No pseudo EPW found for role='{role}', year={year} in {epw_dir}."
        )
    if len(matches) > 1:
        raise RuntimeError(
            f"[building_calibration.experiments] Expected exactly one pseudo EPW for role='{role}', year={year}, "
            f"found {len(matches)}."
        )
    return matches[0].resolve()


def _build_one(template: BuildingCalibrationExperimentTemplate, *, year: int, epw_path: Path) -> CalibrationExperimentSpec:
    start_local = pd.Timestamp(
        year=year,
        month=int(template.start_month),
        day=int(template.start_day),
        hour=int(template.start_hour),
    )
    if int(template.duration_h) <= 0:
        raise ValueError(
            f"[building_calibration.experiments] Experiment '{template.key}' must have duration_h > 0."
        )
    end_local = start_local + pd.Timedelta(hours=int(template.duration_h))
    return CalibrationExperimentSpec(
        experiment_id=str(template.key),
        role=str(template.role),
        calendar_year=int(year),
        epw_path=str(epw_path),
        start_local=start_local.isoformat(),
        end_local=end_local.isoformat(),
        duration_h=int(template.duration_h),
        control_mode=str(template.control_mode),
        event_type=str(template.event_type),
        event_start_offset_h=int(template.event_start_offset_h),
        event_duration_h=int(template.event_duration_h),
        event_setpoint_delta_k=float(template.event_setpoint_delta_k),
        post_event_observation_h=int(template.post_event_observation_h),
        notes=[str(note) for note in template.notes],
    )


def build_experiment_library() -> CalibrationExperimentLibrary:
    cfg = make_building_calibration_config()
    representative_years = _load_representative_years(
        cfg.pseudo_epw_representative_years_json,
        expected_roles=tuple(cfg.pseudo_epw_year_roles),
    )
    extra_year_roles = {str(key): int(value) for key, value in dict(cfg.pseudo_epw_extra_year_roles).items()}
    resolved_years = {**representative_years, **extra_year_roles}
    experiments: list[CalibrationExperimentSpec] = []
    for template in cfg.experiment_templates:
        role = str(template.role)
        if role not in resolved_years:
            raise KeyError(
                f"[building_calibration.experiments] Experiment '{template.key}' references unknown role '{role}'."
            )
        year = int(resolved_years[role])
        epw_path = _resolve_epw_path(role, year, cfg.pseudo_epw_output_dir)
        experiments.append(_build_one(template, year=year, epw_path=epw_path))
    return CalibrationExperimentLibrary(
        schema_version="v1",
        location=str(cfg.location),
        representative_years_json=str(Path(cfg.pseudo_epw_representative_years_json).resolve()),
        experiments=experiments,
        notes=[
            "Experiment timing is expressed in local standard time to match the pseudo-EPW construction.",
            "V1 keeps a small fixed experiment library on purpose; later calibration rounds can extend this via settings.",
        ],
    )
