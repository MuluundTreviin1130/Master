from __future__ import annotations

import json
from pathlib import Path
from pprint import pformat

import pandas as pd

from Settings.data.thermal_archetypes import make_thermal_archetypes
from Settings.technical.building_calibration import make_building_calibration_config


def _load_summary_csv(path: Path, *, label: str) -> pd.DataFrame:
    resolved = path.resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"[building_calibration.export_calibrated] Missing {label}: {resolved}")
    if not resolved.is_file():
        raise FileNotFoundError(
            f"[building_calibration.export_calibrated] Expected file for {label}, got: {resolved}"
        )
    df = pd.read_csv(resolved)
    if df.empty:
        raise ValueError(f"[building_calibration.export_calibrated] Empty {label}: {resolved}")
    return df


def _load_summary_json(path: Path, *, label: str) -> list[dict]:
    resolved = path.resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"[building_calibration.export_calibrated] Missing {label}: {resolved}")
    if not resolved.is_file():
        raise FileNotFoundError(
            f"[building_calibration.export_calibrated] Expected file for {label}, got: {resolved}"
        )
    payload = json.loads(resolved.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or not payload:
        raise ValueError(
            f"[building_calibration.export_calibrated] Expected non-empty list payload in {label}: {resolved}"
        )
    if not all(isinstance(item, dict) for item in payload):
        raise ValueError(
            f"[building_calibration.export_calibrated] Expected list[dict] payload in {label}: {resolved}"
        )
    return payload


def build_calibrated_v1_payload() -> dict:
    cfg = make_building_calibration_config()
    base = make_thermal_archetypes(cfg.location)
    reduced_df = _load_summary_csv(
        Path(cfg.reduced_order_fit_output_dir) / str(cfg.reduced_order_fit_summary_csv),
        label="reduced_order_fit_summary_csv",
    )
    event_df = _load_summary_csv(
        Path(cfg.event_response_fit_output_dir) / str(cfg.event_response_fit_summary_csv),
        label="event_response_fit_summary_csv",
    )
    reduced_payload = _load_summary_json(
        Path(cfg.reduced_order_fit_output_dir) / str(cfg.reduced_order_fit_summary_json),
        label="reduced_order_fit_summary_json",
    )
    event_payload = _load_summary_json(
        Path(cfg.event_response_fit_output_dir) / str(cfg.event_response_fit_summary_json),
        label="event_response_fit_summary_json",
    )

    if len(reduced_payload) != len(reduced_df):
        raise ValueError(
            "[building_calibration.export_calibrated] Reduced-order CSV/JSON row count mismatch. "
            f"csv={len(reduced_df)}, json={len(reduced_payload)}"
        )
    if len(event_payload) != len(event_df):
        raise ValueError(
            "[building_calibration.export_calibrated] Event-response CSV/JSON row count mismatch. "
            f"csv={len(event_df)}, json={len(event_payload)}"
        )

    reduced_index = {str(row["cohort_id"]): row for row in reduced_payload}
    event_index = {str(row["cohort_id"]): row for row in event_payload}

    base_keys = set(base.archetypes.keys())
    if set(reduced_index.keys()) != base_keys:
        missing = sorted(base_keys - set(reduced_index.keys()))
        extra = sorted(set(reduced_index.keys()) - base_keys)
        raise ValueError(
            "[building_calibration.export_calibrated] Reduced-order fit coverage mismatch. "
            f"Missing={missing}, Extra={extra}"
        )
    if set(event_index.keys()) != base_keys:
        missing = sorted(base_keys - set(event_index.keys()))
        extra = sorted(set(event_index.keys()) - base_keys)
        raise ValueError(
            "[building_calibration.export_calibrated] Event-response fit coverage mismatch. "
            f"Missing={missing}, Extra={extra}"
        )

    archetypes: dict[str, dict] = {}
    for key, archetype in base.archetypes.items():
        base_payload = {
            "key": archetype.key,
            "sector": archetype.sector,
            "construction_period": archetype.construction_period,
            "u_wall": archetype.u_wall,
            "u_window": archetype.u_window,
            "u_roof": archetype.u_roof,
            "u_floor": archetype.u_floor,
            "wall_area_per_gfa": archetype.wall_area_per_gfa,
            "window_area_per_gfa": archetype.window_area_per_gfa,
            "roof_area_per_gfa": archetype.roof_area_per_gfa,
            "floor_exposed_per_gfa": archetype.floor_exposed_per_gfa,
            "conditioned_floor_share_of_gfa": archetype.conditioned_floor_share_of_gfa,
            "c_th_wh_per_m2k": archetype.c_th_wh_per_m2k,
            "window_typology_class": archetype.window_typology_class,
            "window_pane_count": archetype.window_pane_count,
            "window_glazing_family": archetype.window_glazing_family,
            "window_frame_type": archetype.window_frame_type,
            "window_has_low_e": archetype.window_has_low_e,
            "window_has_inert_gas_fill": archetype.window_has_inert_gas_fill,
            "window_has_thermal_break": archetype.window_has_thermal_break,
            "window_g_value": archetype.window_g_value,
            "window_visible_transmittance": archetype.window_visible_transmittance,
            "glazing_source": archetype.glazing_source,
            "solar_shading_assumption": archetype.solar_shading_assumption,
            "window_data_source_note": archetype.window_data_source_note,
            "t_min_k": archetype.t_min_k,
            "t_max_k": archetype.t_max_k,
            "calibration_v1": {
                "reduced_order_v1": reduced_index[key],
                "event_response_v1": event_index[key],
            },
        }
        archetypes[key] = base_payload

    return {
        "source": "calibrated_v1_energyplus_teacher_sidecar",
        "location": cfg.location,
        "base_source": base.source,
        "reduced_order_fit_summary_csv": str(
            (Path(cfg.reduced_order_fit_output_dir) / str(cfg.reduced_order_fit_summary_csv)).resolve()
        ),
        "reduced_order_fit_summary_json": str(
            (Path(cfg.reduced_order_fit_output_dir) / str(cfg.reduced_order_fit_summary_json)).resolve()
        ),
        "event_response_fit_summary_csv": str(
            (Path(cfg.event_response_fit_output_dir) / str(cfg.event_response_fit_summary_csv)).resolve()
        ),
        "event_response_fit_summary_json": str(
            (Path(cfg.event_response_fit_output_dir) / str(cfg.event_response_fit_summary_json)).resolve()
        ),
        "notes": [
            "calibrated_v1 is a sidecar SSOT export; it does not yet replace the runtime archetype loader automatically.",
            "Base envelope/geometric fields remain intact; calibration outputs are attached under calibration_v1.",
            "No silent fallback is allowed: export requires full reduced-order and event-response coverage for all archetypes.",
        ],
        "archetypes": archetypes,
    }


def write_calibrated_v1_payload(payload: dict) -> tuple[Path, Path]:
    cfg = make_building_calibration_config()
    json_path = Path(cfg.calibrated_v1_json_path).resolve()
    py_path = Path(cfg.calibrated_v1_python_path).resolve()
    json_path.parent.mkdir(parents=True, exist_ok=True)

    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    py_text = (
        "from __future__ import annotations\n\n\n"
        "def build_calibrated_v1_values() -> dict[str, object]:\n"
        f"    return {pformat(payload, sort_dicts=False, width=100)}\n"
    )
    py_path.write_text(py_text, encoding="utf-8")
    return json_path, py_path
