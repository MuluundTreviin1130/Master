from __future__ import annotations

from Data.thermal_archetypes.Vienna.windows import build_vienna_window_typology_values


def build_thermal_archetypes_values() -> dict[str, object]:
    """Vienna thermal archetypes for the first cohort-based building-stock cut.

    Source logic:
    - Period-specific U-values are anchored to Austrian TABULA/EPISCOPE residential
      typology ranges (Austrian scientific report + later Austrian requirements).
    - Residential geometry ratios are anchored to Austrian TABULA apartment-block
      averages per conditioned floor area.
    - Non-residential geometry ratios are still pragmatic V1 assumptions based on
      office/service-building prototype reasoning until better stock data is available.
    - Areal heat capacities are pragmatic start values on the SAP/HEM style
      areal-heat-capacity scale (kappa/TMP concept), not directly observed Vienna data.
    """

    geometry_by_sector = {
        # Austrian TABULA / EPISCOPE apartment-block averages per conditioned floor area:
        # roof 0.37, window 0.18, wall 0.82, floor 0.36 [m²/m²].
        "residential": {
            "wall_area_per_gfa": 0.82,
            "window_area_per_gfa": 0.18,
            "roof_area_per_gfa": 0.37,
            "floor_exposed_per_gfa": 0.36,
            "conditioned_floor_share_of_gfa": 1.0,
        },
        # Inference from DOE/PNNL office prototypes:
        # large office with 3 floors gives roof/floor per GFA around 0.33 and gross wall / GFA ~0.40;
        # for a mixed Vienna service-building block we use a moderated opaque wall/window split.
        "non_residential": {
            "wall_area_per_gfa": 0.30,
            "window_area_per_gfa": 0.12,
            "roof_area_per_gfa": 0.30,
            "floor_exposed_per_gfa": 0.30,
            "conditioned_floor_share_of_gfa": 1.0,
        },
    }

    # Start values informed by Austrian TABULA residential typology tables for MFH/AB
    # and later Austrian requirement levels. For V1 the same period ladder is reused for
    # non-residential buildings until a better Vienna-specific non-res stock basis is available.
    u_values_by_period = {
        "pre1975": {"u_wall": 1.40, "u_window": 2.30, "u_roof": 1.70, "u_floor": 1.20},
        "1975_1990": {"u_wall": 1.10, "u_window": 2.70, "u_roof": 0.80, "u_floor": 0.80},
        "1990_2000": {"u_wall": 0.60, "u_window": 2.50, "u_roof": 0.50, "u_floor": 0.50},
        "2000_2014": {"u_wall": 0.35, "u_window": 1.40, "u_roof": 0.20, "u_floor": 0.40},
    }

    # Pragmatic areal heat-capacity start values [Wh/m²K] on the HEM/SAP-style scale.
    # These are model assumptions, chosen so old residential stock carries more thermal mass
    # than newer and more lightweight/service-oriented stock.
    c_th_by_key = {
        "residential_pre1975": 80.0,
        "residential_1975_1990": 75.0,
        "residential_1990_2000": 70.0,
        "residential_2000_2014": 65.0,
        "non_residential_pre1975": 70.0,
        "non_residential_1975_1990": 65.0,
        "non_residential_1990_2000": 60.0,
        "non_residential_2000_2014": 55.0,
    }

    keys = [
        ("residential_pre1975", "residential", "pre1975"),
        ("residential_1975_1990", "residential", "1975_1990"),
        ("residential_1990_2000", "residential", "1990_2000"),
        ("residential_2000_2014", "residential", "2000_2014"),
        ("non_residential_pre1975", "non_residential", "pre1975"),
        ("non_residential_1975_1990", "non_residential", "1975_1990"),
        ("non_residential_1990_2000", "non_residential", "1990_2000"),
        ("non_residential_2000_2014", "non_residential", "2000_2014"),
    ]

    window_typology_data = dict(build_vienna_window_typology_values()["residential_by_period"])

    archetypes = {}
    for key, sector, construction_period in keys:
        geometry = geometry_by_sector[sector]
        u_values = u_values_by_period[construction_period]
        residential_window_record = (
            dict(window_typology_data[construction_period]) if sector == "residential" else None
        )
        window_typology_class = (
            str(residential_window_record["window_typology_class"])
            if sector == "residential"
            else None
        )
        glazing_source = (
            str(residential_window_record["typology_source"])
            if sector == "residential"
            else "non_residential_v1_placeholder_no_source_backed_window_typology"
        )
        solar_shading_assumption = (
            "TABULA_common_procedure_standard_shading_values_pending_cohort_specific_refinement"
        )
        archetypes[key] = {
            "key": key,
            "sector": sector,
            "construction_period": construction_period,
            "u_wall": u_values["u_wall"],
            "u_window": u_values["u_window"],
            "u_roof": u_values["u_roof"],
            "u_floor": u_values["u_floor"],
            "wall_area_per_gfa": geometry["wall_area_per_gfa"],
            "window_area_per_gfa": geometry["window_area_per_gfa"],
            "roof_area_per_gfa": geometry["roof_area_per_gfa"],
            "floor_exposed_per_gfa": geometry["floor_exposed_per_gfa"],
            "conditioned_floor_share_of_gfa": geometry["conditioned_floor_share_of_gfa"],
            "c_th_wh_per_m2k": c_th_by_key[key],
            "window_typology_class": window_typology_class,
            "window_pane_count": (
                int(residential_window_record["n_panes"]) if residential_window_record is not None else None
            ),
            "window_glazing_family": (
                str(residential_window_record["glazing_family"])
                if residential_window_record is not None
                else None
            ),
            "window_frame_type": (
                str(residential_window_record["frame_type"]) if residential_window_record is not None else None
            ),
            "window_has_low_e": (
                bool(residential_window_record["has_low_e"]) if residential_window_record is not None else None
            ),
            "window_has_inert_gas_fill": (
                bool(residential_window_record["has_inert_gas_fill"])
                if residential_window_record is not None
                else None
            ),
            "window_has_thermal_break": (
                bool(residential_window_record["has_thermal_break"])
                if residential_window_record is not None
                else None
            ),
            "window_g_value": (
                float(residential_window_record["g_value"]) if residential_window_record is not None else None
            ),
            "window_visible_transmittance": (
                float(residential_window_record["visible_transmittance"])
                if residential_window_record is not None
                else None
            ),
            "glazing_source": glazing_source,
            "solar_shading_assumption": solar_shading_assumption,
            "window_data_source_note": (
                str(residential_window_record["source_note"]) if residential_window_record is not None else None
            ),
            "t_min_k": 294.15,
            "t_max_k": 300.15,
        }
    return {
        "source": "manual_v1_tabula_and_prototype_inference",
        "location": "Vienna",
        "archetypes": archetypes,
    }
