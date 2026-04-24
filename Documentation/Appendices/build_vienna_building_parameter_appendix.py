from __future__ import annotations

"""Build a paper appendix with all Vienna building-model parameters."""

from dataclasses import dataclass
from datetime import datetime, timezone
from html import escape
from pathlib import Path
import sys
from types import SimpleNamespace
from zipfile import ZIP_DEFLATED, ZipFile

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Settings.constraints.thermflex import ThermflexConstraintConfig
from Settings.data.building_stock import make_building_stock
from Settings.data.thermal_archetypes import make_thermal_archetypes
from Settings.technical.building_calibration import make_building_calibration_config
from Settings.technical.heating_control import make_heating_control
from Settings.technical.members import make_members
from Technical_model.technologies.buildings.runtime_building_params import (
    get_runtime_building_params,
)

OUTPUT_MD = Path(__file__).resolve().with_name("vienna_building_model_parameters_appendix.md")
OUTPUT_DOCX = Path(__file__).resolve().with_name("vienna_building_model_parameters_appendix.docx")


@dataclass(frozen=True)
class SourceEntry:
    source_id: str
    citation: str
    note: str


@dataclass(frozen=True)
class TableSection:
    title: str
    intro: str
    headers: list[str]
    rows: list[list[str]]


def build_appendix() -> tuple[Path, Path]:
    appendix = _build_appendix_payload()
    markdown = _render_markdown(appendix)
    OUTPUT_MD.write_text(markdown, encoding="utf-8")
    _write_docx(OUTPUT_DOCX, appendix)
    return OUTPUT_MD, OUTPUT_DOCX


def _build_appendix_payload() -> dict[str, object]:
    """Collect all current SSOT values needed for the appendix tables."""

    building_stock = make_building_stock("Vienna")
    members_cfg = make_members(building_stock=building_stock)
    default_archetypes = make_thermal_archetypes("Vienna", variant="default")
    calibrated_archetypes = make_thermal_archetypes("Vienna", variant="calibrated_v1")
    runtime_settings_stub = SimpleNamespace(thermal_archetypes=calibrated_archetypes)
    calibration_cfg = make_building_calibration_config()
    heating_control = make_heating_control()
    thermflex_constraints = ThermflexConstraintConfig()
    reference_gfa_m2 = float(calibration_cfg.teacher_reference_gfa_m2)

    cohort_rows: list[list[str]] = []
    archetype_rows: list[list[str]] = []
    archetype_meta_rows: list[list[str]] = []
    runtime_geometry_rows: list[list[str]] = []
    calibrated_reduced_order_rows: list[list[str]] = []
    calibrated_event_rows: list[list[str]] = []

    for member in members_cfg.members:
        cohort_id = str(member.member_id)
        base = default_archetypes.archetypes[str(member.thermal_archetype_key)]
        calibrated = calibrated_archetypes.archetypes[str(member.thermal_archetype_key)]
        runtime = get_runtime_building_params(member, settings_obj=runtime_settings_stub)
        room_height_m = float(member.represented_volume_m3) / float(member.represented_gfa_m2)
        runtime_reference = get_runtime_building_params(
            SimpleNamespace(
                thermal_archetype_key=str(member.thermal_archetype_key),
                represented_gfa_m2=reference_gfa_m2,
                represented_volume_m3=reference_gfa_m2 * room_height_m,
            ),
            settings_obj=runtime_settings_stub,
        )
        reduced = dict(calibrated.calibration_v1["reduced_order_v1"])
        event = dict(calibrated.calibration_v1["event_response_v1"])

        cohort_rows.append(
            [
                cohort_id,
                str(base.sector),
                str(base.construction_period),
                _fmt_num(member.represented_gfa_m2, digits=0),
                _fmt_num(member.represented_volume_m3, digits=0),
                _fmt_num(member.annual_space_heat_target_kwh, digits=0),
                _fmt_num(member.annual_hotwater_target_kwh, digits=0),
                _fmt_bool(member.include_hotwater),
                _fmt_optional(member.dh_connected_share_override, digits=3),
                _fmt_load_mix(member.load_profile_mix),
                "BS-1, BS-2, BS-R1",
            ]
        )

        archetype_rows.append(
            [
                cohort_id,
                _fmt_num(base.u_wall, digits=2),
                _fmt_num(base.u_window, digits=2),
                _fmt_num(base.u_roof, digits=2),
                _fmt_num(base.u_floor, digits=2),
                _fmt_num(base.wall_area_per_gfa, digits=2),
                _fmt_num(base.window_area_per_gfa, digits=2),
                _fmt_num(base.roof_area_per_gfa, digits=2),
                _fmt_num(base.floor_exposed_per_gfa, digits=2),
                _fmt_num(base.conditioned_floor_share_of_gfa, digits=2),
                "AR-1, AR-2, AR-5, AR-7",
            ]
        )

        archetype_meta_rows.append(
            [
                cohort_id,
                _fmt_num(base.c_th_wh_per_m2k, digits=1),
                _fmt_num(float(base.t_min_k) - 273.15, digits=2),
                _fmt_num(float(base.t_max_k) - 273.15, digits=2),
                str(base.window_typology_class or "n/a"),
                str(base.glazing_source or "n/a"),
                str(base.solar_shading_assumption or "n/a"),
                "AR-2, AR-3, AR-4, AR-6, AR-R1",
            ]
        )

        runtime_geometry_rows.append(
            [
                cohort_id,
                _fmt_num(reference_gfa_m2, digits=0),
                _fmt_num(reference_gfa_m2 * room_height_m, digits=0),
                _fmt_num(runtime_reference["A_floor"], digits=0),
                _fmt_num(runtime_reference["A_wall"], digits=0),
                _fmt_num(sum(runtime_reference["A_window"].values()), digits=0),
                _fmt_num(runtime_reference["A_roof"], digits=0),
                _fmt_num(runtime_reference["room_height"], digits=2),
                _fmt_num(runtime_reference["cp_air"], digits=2),
                _fmt_num(runtime_reference["g_glazing"], digits=2),
                _fmt_num(runtime_reference["g_glazing_shaded"], digits=2),
                _fmt_solar_multipliers(runtime_reference["solar_multipliers"]),
                "RT-1, CAL-3, LEG-1",
            ]
        )

        calibrated_reduced_order_rows.append(
            [
                cohort_id,
                _fmt_num(reduced["fitted_total_loss_coefficient_w_per_m2k"], digits=3),
                _fmt_num(reduced["fitted_transmission_loss_coefficient_w_per_m2k"], digits=3),
                _fmt_num(reduced["fitted_effective_heat_capacity_wh_per_m2k"], digits=3),
                _fmt_num(reduced["fitted_tau_h"], digits=2),
                _fmt_num(
                    reduced["fitted_total_loss_coefficient_w_per_m2k"] * float(runtime_reference["A_floor"]),
                    digits=1,
                ),
                _fmt_num(
                    reduced["fitted_transmission_loss_coefficient_w_per_m2k"] * float(runtime_reference["A_floor"]),
                    digits=1,
                ),
                _fmt_num(
                    reduced["fitted_effective_heat_capacity_wh_per_m2k"] * float(runtime_reference["A_floor"]),
                    digits=1,
                ),
                _fmt_num(reduced["fitted_air_loss_scale_vs_seed_approx"], digits=3),
                "CAL-1, CAL-2, CAL-3, CAL-4",
            ]
        )

        calibrated_event_rows.append(
            [
                cohort_id,
                _fmt_num(event["preheat_added_energy_kwh"], digits=2),
                _fmt_num(event["preheat_peak_excess_kw"], digits=2),
                _fmt_num(event["cutback_shed_energy_kwh"], digits=2),
                _fmt_num(event["cutback_peak_shed_kw"], digits=2),
                _fmt_num(event["recovery_rebound_energy_kwh"], digits=2),
                _fmt_num(event["recovery_peak_rebound_kw"], digits=2),
                _fmt_num(event["recovery_time_to_reference_h"], digits=2),
                "CAL-1, CAL-2, CAL-3, CAL-4",
            ]
        )

    global_control_rows = [
        ["reference_control_mode", str(heating_control.reference_control_mode), "global default", "HC-1"],
        ["control_mode", str(heating_control.control_mode), "global default", "HC-1"],
        ["constant_setpoint_c", _fmt_num(heating_control.constant_setpoint_c, digits=2), "global default", "HC-1"],
        ["day_setpoint_c", _fmt_num(heating_control.day_setpoint_c, digits=2), "global default", "HC-1"],
        ["night_setpoint_c", _fmt_num(heating_control.night_setpoint_c, digits=2), "global default", "HC-1"],
        ["day_start_hour", str(heating_control.day_start_hour), "global default", "HC-1"],
        ["night_start_hour", str(heating_control.night_start_hour), "global default", "HC-1"],
        ["hysteresis_band_k", _fmt_num(heating_control.hysteresis_band_k, digits=2), "global default", "HC-1"],
        ["comfort_band_enabled", _fmt_bool(heating_control.comfort_band_enabled), "global default", "HC-1"],
        ["comfort_band_k", _fmt_num(heating_control.comfort_band_k, digits=2), "global default", "HC-1"],
        ["max_heating_power_mode", str(heating_control.max_heating_power_mode), "global default", "HC-1"],
        ["max_heating_power_w_per_m2", _fmt_num(heating_control.max_heating_power_w_per_m2, digits=1), "global default", "HC-1"],
        ["max_heating_power_multiplier", _fmt_num(heating_control.max_heating_power_multiplier, digits=2), "global default", "HC-1"],
        ["design_indoor_temp_c", _fmt_num(heating_control.design_indoor_temp_c, digits=2), "global default", "HC-1"],
        ["design_outdoor_temp_c", _fmt_num(heating_control.design_outdoor_temp_c, digits=2), "global default", "HC-1"],
        ["design_ventilation_mode", str(heating_control.design_ventilation_mode), "global default", "HC-1"],
        ["design_internal_gains_w_per_m2", _fmt_num(heating_control.design_internal_gains_w_per_m2, digits=2), "global default", "HC-1"],
        ["design_solar_gains_w_per_m2", _fmt_num(heating_control.design_solar_gains_w_per_m2, digits=2), "global default", "HC-1"],
        ["enable_active_cooling", _fmt_bool(heating_control.enable_active_cooling), "global default", "HC-1"],
        ["cooling_setpoint_c", _fmt_num(heating_control.cooling_setpoint_c, digits=2), "global default", "HC-1"],
        ["max_cooling_power_w_per_m2", _fmt_num(heating_control.max_cooling_power_w_per_m2, digits=1), "global default", "HC-1"],
    ]
    thermflex_rows = [
        ["use_explicit_lower_bounds", _fmt_bool(thermflex_constraints.use_explicit_lower_bounds), "scenario-dependent", "TF-1"],
        ["constant_lower_bound_c", _fmt_optional(thermflex_constraints.constant_lower_bound_c, digits=2), "scenario-dependent", "TF-1"],
        ["day_lower_bound_c", _fmt_optional(thermflex_constraints.day_lower_bound_c, digits=2), "scenario-dependent", "TF-1"],
        ["night_lower_bound_c", _fmt_optional(thermflex_constraints.night_lower_bound_c, digits=2), "scenario-dependent", "TF-1"],
        ["comfort_band_k", _fmt_num(thermflex_constraints.comfort_band_k, digits=2), "scenario-dependent", "TF-1"],
        ["reference_deadband_k", _fmt_num(thermflex_constraints.reference_deadband_k, digits=2), "scenario-dependent", "TF-1"],
        ["constrain_upper_temperature", _fmt_bool(thermflex_constraints.constrain_upper_temperature), "scenario-dependent", "TF-1"],
        ["use_event_response_bounds", _fmt_bool(thermflex_constraints.use_event_response_bounds), "scenario-dependent", "TF-1"],
        ["enforce_event_peak_bounds", _fmt_bool(thermflex_constraints.enforce_event_peak_bounds), "scenario-dependent", "TF-1"],
        ["enforce_event_energy_bounds", _fmt_bool(thermflex_constraints.enforce_event_energy_bounds), "scenario-dependent", "TF-1"],
        ["enforce_recovery_cooldown", _fmt_bool(thermflex_constraints.enforce_recovery_cooldown), "scenario-dependent", "TF-1"],
        ["max_flex_duration_h", str(thermflex_constraints.max_flex_duration_h), "scenario-dependent", "TF-1"],
        ["max_flex_events_per_day", str(thermflex_constraints.max_flex_events_per_day), "scenario-dependent", "TF-1"],
        ["activation_penalty_eur_per_member_h", _fmt_num(thermflex_constraints.activation_penalty_eur_per_member_h, digits=6), "scenario-dependent", "TF-1"],
        ["temperature_violation_penalty_eur_per_degree_h", _fmt_num(thermflex_constraints.temperature_violation_penalty_eur_per_degree_h, digits=0), "scenario-dependent", "TF-1"],
        ["allow_terminal_deviation", _fmt_bool(thermflex_constraints.allow_terminal_deviation), "scenario-dependent", "TF-1"],
        ["terminal_band_k", _fmt_num(thermflex_constraints.terminal_band_k, digits=2), "scenario-dependent", "TF-1"],
    ]

    sections = [
        TableSection(
            title="Table A. Cohort scaling and stock anchors",
            intro=(
                "These values define the Vienna cohort members that enter the paper runs. "
                "They control cohort scale, annual heat anchors, hot-water inclusion, "
                "and the mapping from each cohort to a thermal archetype."
            ),
            headers=[
                "Cohort",
                "Sector",
                "Period",
                "GFA [m2]",
                "Volume [m3]",
                "Annual space heat [kWh/a]",
                "Annual hot water [kWh/a]",
                "HW?",
                "DH share override",
                "Load mix",
                "Sources",
            ],
            rows=cohort_rows,
        ),
        TableSection(
            title="Table B. Base envelope and geometry archetype parameters",
            intro=(
                "These are the base Vienna archetype parameters before the calibrated_v1 "
                "sidecar is applied. The fields remain part of the active runtime path. "
                "The residential period ladder is TABULA-informed, but the values are "
                "simplified cohort seed values rather than direct one-to-one TABULA "
                "WebTool extractions."
            ),
            headers=[
                "Archetype",
                "U_wall",
                "U_window",
                "U_roof",
                "U_floor",
                "Wall/GFA",
                "Window/GFA",
                "Roof/GFA",
                "Floor/GFA",
                "Cond. floor share",
                "Sources",
            ],
            rows=archetype_rows,
        ),
        TableSection(
            title="Table C. Base thermal-mass, comfort, and window metadata",
            intro=(
                "These fields are still attached to the archetype layer. Source quality is "
                "mixed: some fields are literature-backed, while others remain pragmatic "
                "V1 assumptions and are marked accordingly."
            ),
            headers=[
                "Archetype",
                "c_th [Wh/m2K]",
                "T_min [C]",
                "T_max [C]",
                "Window typology class",
                "Glazing source tag",
                "Solar/shading assumption",
                "Sources",
            ],
            rows=archetype_meta_rows,
        ),
        TableSection(
            title="Table D. Reference-building runtime geometry and legacy solar compatibility fields",
            intro=(
                "These values describe one reference building per archetype on the current "
                "teacher-scale reference body. They are not Vienna-wide sums. The reference "
                "gross floor area is taken from the building-calibration SSOT. The solar "
                "multipliers and glazing-g values are still legacy compatibility fields in the "
                "runtime path and are not yet fully cohort-specific literature-backed SSOT."
            ),
            headers=[
                "Archetype",
                "Ref. GFA [m2]",
                "Ref. volume [m3]",
                "A_floor [m2]",
                "A_wall [m2]",
                "A_window_total [m2]",
                "A_roof [m2]",
                "Room height [m]",
                "cp_air",
                "g_glazing",
                "g_glazing_shaded",
                "Solar multipliers",
                "Sources",
            ],
            rows=runtime_geometry_rows,
        ),
        TableSection(
            title="Table E. Calibrated reduced-order runtime parameters for the reference building",
            intro=(
                "These are the EnergyPlus-teacher-derived reduced-order parameters that the "
                "current calibrated_v1 runtime path actually uses for thermal dynamics. Both "
                "the normalized per-square-meter values and the resulting parameters for the "
                "reference building are shown."
            ),
            headers=[
                "Archetype",
                "H_total [W/m2K]",
                "H_trans [W/m2K]",
                "C_eff [Wh/m2K]",
                "tau [h]",
                "H_total ref [W/K]",
                "H_trans ref [W/K]",
                "C_eff ref [Wh/K]",
                "Air-loss scale",
                "Sources",
            ],
            rows=calibrated_reduced_order_rows,
        ),
        TableSection(
            title="Table F. Calibrated event-response parameters",
            intro=(
                "These are the cohort-specific thermflex sidecar parameters fitted from the "
                "EnergyPlus teacher experiments. They constrain preheat, cutback, and recovery "
                "behavior when event-response bounds are active."
            ),
            headers=[
                "Cohort",
                "Preheat energy [kWh]",
                "Preheat peak [kW]",
                "Cutback shed [kWh]",
                "Cutback peak [kW]",
                "Recovery rebound [kWh]",
                "Recovery peak [kW]",
                "Recovery time [h]",
                "Sources",
            ],
            rows=calibrated_event_rows,
        ),
        TableSection(
            title="Table G. Global heating-control parameters",
            intro=(
                "These are global building-operation settings from the Settings layer. They are "
                "not archetype-specific and may be overridden by explicit paper-case JSON "
                "overrides, but they still belong to the active building model path."
            ),
            headers=["Parameter", "Value", "Role", "Sources"],
            rows=global_control_rows,
        ),
        TableSection(
            title="Table H. Global thermflex constraint parameters",
            intro=(
                "These are the global thermflex/bound settings from the Settings layer. "
                "Representative-day and paper sensitivity runs override a subset of them."
            ),
            headers=["Parameter", "Value", "Role", "Sources"],
            rows=thermflex_rows,
        ),
    ]

    sources = [
        SourceEntry(
            "BS-1",
            "Citiwatt indicators Vienna local snapshot; used via Data/building_stock/Vienna/building_stock.py.",
            "Building-stock scale anchors: total heat, GFA, volume, and period shares.",
        ),
        SourceEntry(
            "BS-2",
            "Vienna Energy Report 2025 and repo notes in Documentation/Sources/wien_und_dispatch_quellen.md.",
            "Official Vienna electricity anchors and building-sector context used in the stock layer.",
        ),
        SourceEntry(
            "BS-R1",
            "Repo-derived V1 stock assumptions in Data/building_stock/Vienna/building_stock.py.",
            "Includes the explicit non-residential hot-water exclusion and the current exogenous electricity calibration anchors.",
        ),
        SourceEntry(
            "AR-1",
            "Austrian TABULA / EPISCOPE country page: https://episcope.eu/building-typology/country/at/",
            "Residential period-specific U-value and typology anchor.",
        ),
        SourceEntry(
            "AR-2",
            "Austrian TABULA Scientific Report: https://episcope.eu/fileadmin/tabula/public/docs/scientific/AT_TABULA_ScientificReport_AEA.pdf",
            "Residential period ladder, window typologies, and Austrian multi-family context.",
        ),
        SourceEntry(
            "AR-3",
            "TABULA common calculation procedure: https://episcope.eu/building-typology/tabula-structure/calculation/",
            "Standard shading and usage procedure values; method anchor, not cohort-specific Vienna truth.",
        ),
        SourceEntry(
            "AR-4",
            "TABULA WebTool FAQ: https://episcope.eu/building-typology/webtool/",
            "Important caution that the 45 Wh/(m2K) procedure value is too coarse for research use.",
        ),
        SourceEntry(
            "AR-5",
            "TABULA Final Report Appendix Volume: https://episcope.eu/fileadmin/tabula/public/docs/report/TABULA_FinalReport_AppendixVolume.pdf",
            "Residential envelope-area ratios per conditioned floor area.",
        ),
        SourceEntry(
            "AR-6",
            "OIB-Richtlinie 6 / Kostenoptimalitaet: https://www.oib.or.at/sites/default/files/kostenoptimalitaet_0.pdf",
            "Austrian plausibility anchors for setpoints, g-values, and air-change assumptions.",
        ),
        SourceEntry(
            "AR-7",
            "TABULA Thematic Report No. 3 / Non-Residential Buildings: https://episcope.eu/building-typology/tabula-structure/non-residential/",
            "Explains why non-residential geometry and exposure assumptions remain less certain than residential ones.",
        ),
        SourceEntry(
            "AR-R1",
            "Repo-internal V1 assumption in Data/thermal_archetypes/Vienna/thermal_archetypes.py.",
            "Areal heat capacities and some non-residential fields are still pragmatic start values, not direct Vienna observations.",
        ),
        SourceEntry(
            "RT-1",
            "Runtime derivation in Technical_model/technologies/buildings/runtime_building_params.py.",
            "Cohort-scale areas, room height, and effective runtime fields are derived from the stock + archetype SSOT.",
        ),
        SourceEntry(
            "LEG-1",
            "Legacy compatibility fields in Data/technology_data/building.py and runtime_building_params.py.",
            "solar_multipliers, g_glazing, and g_glazing_shaded remain active compatibility placeholders and are not yet fully recalibrated Vienna SSOT.",
        ),
        SourceEntry(
            "CAL-1",
            "Open-Meteo Historical Weather API: https://open-meteo.com/en/docs/historical-weather-api",
            "Weather driver for the pseudo-EPW and calibration path.",
        ),
        SourceEntry(
            "CAL-2",
            "Climate.OneBuilding Vienna EPW template: https://climate.onebuilding.org/WMO_Region_6_Europe/AUT_Austria/index.html",
            "Header and format anchor for pseudo-EPW generation.",
        ),
        SourceEntry(
            "CAL-3",
            "EnergyPlus 26.1.0 and repo calibration teacher path.",
            "Teacher model used to derive reduced-order and event-response fits.",
        ),
        SourceEntry(
            "CAL-4",
            "Repo-generated calibration exports: Data/thermal_archetypes/Vienna/calibrated_v1.py plus reduced_order_fit_summary.csv and event_response_fit_summary.csv.",
            "Direct source of the fitted reduced-order and event-response sidecar parameters.",
        ),
        SourceEntry(
            "HC-1",
            "Settings/technical/heating_control.py",
            "Global heating and cooling control defaults; scenario-specific overrides may change them in paper runs.",
        ),
        SourceEntry(
            "TF-1",
            "Settings/constraints/thermflex.py",
            "Global thermflex-bound defaults; representative-day and paper runs override a subset of them explicitly.",
        ),
    ]

    intro_lines = [
        "Appendix scope: Vienna cohort-based building model parameters for the current paper path.",
        "Active runtime variant: thermal_archetypes.variant = calibrated_v1.",
        "The appendix separates literature-backed fields, pragmatic V1 assumptions, and legacy compatibility fields.",
        "Case-specific paper JSON overrides can change the global control and thermflex settings; the archetype and calibrated sidecar tables here are the repo SSOT at generation time.",
    ]

    notes = [
        "The calibrated_v1 layer keeps the base envelope and geometry fields intact and adds calibration_v1 as a sidecar payload.",
        "Runtime thermal dynamics use the calibrated reduced-order fields (effective loss coefficient, effective heat capacity, and tau) when calibrated_v1 is active.",
        "Event-response bounds use the calibrated preheat/cutback/recovery metrics when the corresponding thermflex constraint switches are enabled.",
        "Non-residential hot water is intentionally zero in the current Vienna V1 building-stock path.",
        "Residential archetypes represent apartment-block-like multi-family reference buildings; non-residential archetypes are pragmatic service/office-like V1 proxies.",
        "The base residential U-values are TABULA-informed cohort seed values, not direct one-to-one TABULA WebTool extractions.",
    ]

    return {
        "title": "Vienna Building Model Parameters Appendix",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "intro_lines": intro_lines,
        "notes": notes,
        "sections": sections,
        "sources": sources,
    }


def _render_markdown(payload: dict[str, object]) -> str:
    lines: list[str] = []
    lines.append(f"# {payload['title']}")
    lines.append("")
    lines.append(f"Generated at UTC: `{payload['generated_at_utc']}`")
    lines.append("")
    lines.append("## Scope")
    lines.append("")
    for item in payload["intro_lines"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    for item in payload["notes"]:
        lines.append(f"- {item}")
    lines.append("")
    for section in payload["sections"]:
        lines.append(f"## {section.title}")
        lines.append("")
        lines.append(section.intro)
        lines.append("")
        lines.append(_markdown_table(section.headers, section.rows))
        lines.append("")
    lines.append("## Bibliography and Source Notes")
    lines.append("")
    for source in payload["sources"]:
        lines.append(f"- **{source.source_id}**: {source.citation}")
        lines.append(f"  Note: {source.note}")
    lines.append("")
    return "\n".join(lines)


def _markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    header_line = "| " + " | ".join(headers) + " |"
    sep_line = "| " + " | ".join("---" for _ in headers) + " |"
    row_lines = ["| " + " | ".join(row) + " |" for row in rows]
    return "\n".join([header_line, sep_line, *row_lines])


def _write_docx(path: Path, payload: dict[str, object]) -> None:
    """Write a minimal DOCX package without external dependencies."""

    body_parts: list[str] = []
    body_parts.append(_w_heading(payload["title"], level=1))
    body_parts.append(_w_paragraph(f"Generated at UTC: {payload['generated_at_utc']}"))

    body_parts.append(_w_heading("Scope", level=2))
    for item in payload["intro_lines"]:
        body_parts.append(_w_bullet(item))

    body_parts.append(_w_heading("Notes", level=2))
    for item in payload["notes"]:
        body_parts.append(_w_bullet(item))

    for section in payload["sections"]:
        body_parts.append(_w_heading(section.title, level=2))
        body_parts.append(_w_paragraph(section.intro))
        body_parts.append(_w_table(section.headers, section.rows))

    body_parts.append(_w_heading("Bibliography and Source Notes", level=2))
    for source in payload["sources"]:
        body_parts.append(_w_paragraph(f"{source.source_id}: {source.citation}", bold=True))
        body_parts.append(_w_paragraph(f"Note: {source.note}"))

    document_xml = _document_xml("".join(body_parts))
    core_xml = _core_props_xml(
        title=str(payload["title"]),
        created_iso=str(payload["generated_at_utc"]),
    )

    with ZipFile(path, "w", compression=ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", _content_types_xml())
        zf.writestr("_rels/.rels", _root_rels_xml())
        zf.writestr("docProps/core.xml", core_xml)
        zf.writestr("docProps/app.xml", _app_props_xml())
        zf.writestr("word/document.xml", document_xml)


def _content_types_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>
"""


def _root_rels_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>
"""


def _app_props_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"
            xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <Application>Codex Appendix Generator</Application>
</Properties>
"""


def _core_props_xml(*, title: str, created_iso: str) -> str:
    created = escape(created_iso)
    safe_title = escape(title)
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
                   xmlns:dc="http://purl.org/dc/elements/1.1/"
                   xmlns:dcterms="http://purl.org/dc/terms/"
                   xmlns:dcmitype="http://purl.org/dc/dcmitype/"
                   xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:title>{safe_title}</dc:title>
  <dc:creator>Codex</dc:creator>
  <cp:lastModifiedBy>Codex</cp:lastModifiedBy>
  <dcterms:created xsi:type="dcterms:W3CDTF">{created}</dcterms:created>
  <dcterms:modified xsi:type="dcterms:W3CDTF">{created}</dcterms:modified>
</cp:coreProperties>
"""


def _document_xml(body_xml: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    {body_xml}
    <w:sectPr>
      <w:pgSz w:w="15840" w:h="12240" w:orient="landscape"/>
      <w:pgMar w:top="720" w:right="720" w:bottom="720" w:left="720" w:header="450" w:footer="450" w:gutter="0"/>
    </w:sectPr>
  </w:body>
</w:document>
"""


def _w_heading(text: str, *, level: int) -> str:
    size = {1: 32, 2: 26, 3: 22}.get(level, 22)
    return _w_paragraph(text, bold=True, size=size, spacing_after=160)


def _w_bullet(text: str) -> str:
    return _w_paragraph(f"• {text}")


def _w_paragraph(
    text: str,
    *,
    bold: bool = False,
    size: int | None = None,
    spacing_after: int = 80,
) -> str:
    run_props = []
    if bold:
        run_props.append("<w:b/>")
    if size is not None:
        run_props.append(f'<w:sz w:val="{int(size)}"/>')
    props_xml = f"<w:rPr>{''.join(run_props)}</w:rPr>" if run_props else ""
    safe = escape(str(text))
    return (
        f'<w:p><w:pPr><w:spacing w:after="{int(spacing_after)}"/></w:pPr>'
        f"<w:r>{props_xml}<w:t xml:space=\"preserve\">{safe}</w:t></w:r></w:p>"
    )


def _w_table(headers: list[str], rows: list[list[str]]) -> str:
    header_xml = _w_table_row(headers, header=True)
    row_xml = "".join(_w_table_row(row, header=False) for row in rows)
    return (
        "<w:tbl>"
        "<w:tblPr>"
        "<w:tblW w:w=\"0\" w:type=\"auto\"/>"
        "<w:tblBorders>"
        "<w:top w:val=\"single\" w:sz=\"8\" w:space=\"0\" w:color=\"auto\"/>"
        "<w:left w:val=\"single\" w:sz=\"8\" w:space=\"0\" w:color=\"auto\"/>"
        "<w:bottom w:val=\"single\" w:sz=\"8\" w:space=\"0\" w:color=\"auto\"/>"
        "<w:right w:val=\"single\" w:sz=\"8\" w:space=\"0\" w:color=\"auto\"/>"
        "<w:insideH w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"auto\"/>"
        "<w:insideV w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"auto\"/>"
        "</w:tblBorders>"
        "</w:tblPr>"
        f"{header_xml}{row_xml}"
        "</w:tbl>"
    )


def _w_table_row(values: list[str], *, header: bool) -> str:
    cells = "".join(_w_table_cell(value, header=header) for value in values)
    header_flag = "<w:trPr><w:tblHeader/></w:trPr>" if header else ""
    return f"<w:tr>{header_flag}{cells}</w:tr>"


def _w_table_cell(text: str, *, header: bool) -> str:
    safe = escape(str(text))
    run_props = "<w:rPr><w:b/></w:rPr>" if header else ""
    shading = (
        "<w:tcPr><w:shd w:fill=\"D9E2F3\" w:val=\"clear\"/></w:tcPr>"
        if header
        else "<w:tcPr/>"
    )
    return (
        f"<w:tc>{shading}<w:p><w:r>{run_props}"
        f"<w:t xml:space=\"preserve\">{safe}</w:t></w:r></w:p></w:tc>"
    )


def _fmt_num(value: object, *, digits: int) -> str:
    return f"{float(value):,.{int(digits)}f}"


def _fmt_optional(value: object, *, digits: int) -> str:
    if value is None:
        return "n/a"
    return _fmt_num(value, digits=digits)


def _fmt_bool(value: object) -> str:
    return "yes" if bool(value) else "no"


def _fmt_load_mix(load_mix: dict[str, float]) -> str:
    if not load_mix:
        return "n/a"
    return "; ".join(f"{k}={v:.2f}" for k, v in load_mix.items())


def _fmt_solar_multipliers(values: dict[str, float]) -> str:
    return "; ".join(f"{k}={float(v):.2f}" for k, v in values.items())


if __name__ == "__main__":
    md_path, docx_path = build_appendix()
    print(f"[appendix] wrote markdown: {md_path}")
    print(f"[appendix] wrote docx: {docx_path}")
