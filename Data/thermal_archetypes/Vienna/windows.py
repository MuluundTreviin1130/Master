from __future__ import annotations


def build_vienna_window_typology_values() -> dict[str, object]:
    """Vienna residential window-typology SSOT for the current V1 paper path.

    Why this file exists:
    - The repo already had period-specific Austrian TABULA window typology classes.
    - The numeric optical values needed by the simple-glazing teacher were previously
      embedded in settings as an implementation detail.
    - This file makes the window logic explicit data SSOT instead:
      typology, frame family, pane count, glazing family, and teacher-facing
      optical proxies live together and can be documented coherently.

    Source quality:
    - construction-period to window-typology mapping:
      Austrian TABULA / EPISCOPE scientific report
    - numeric g-value / SHGC anchors:
      cross-TABULA proxy from similar European window types (DE/DK/PL reports)
    - visible transmittance:
      documented V1 proxy, not equally source-backed
    """

    residential_by_period = {
        "pre1975": {
            "window_typology_class": "single_glazing_box_type_or_wood_frame",
            "n_panes": 1,
            "glazing_family": "single_glazing",
            "frame_type": "wood_or_box_type",
            "has_low_e": False,
            "has_inert_gas_fill": False,
            "has_thermal_break": False,
            "g_value": 0.85,
            "visible_transmittance": 0.78,
            "typology_source": "AT_TABULA_ScientificReport_AEA_period_window_typologies",
            "g_value_source": "cross_tabula_proxy_dk_pl_single_glazing",
            "visible_transmittance_source": "v1_proxy_not_yet_source_backed",
            "source_note": (
                "AT TABULA provides the period-typical single-glazing / box-type logic; "
                "numeric g-value is proxied from comparable TABULA window tables in DK/PL."
            ),
        },
        "1975_1990": {
            "window_typology_class": "double_glazing_composite_window",
            "n_panes": 2,
            "glazing_family": "double_glazing_conventional",
            "frame_type": "composite_or_wood",
            "has_low_e": False,
            "has_inert_gas_fill": False,
            "has_thermal_break": False,
            "g_value": 0.76,
            "visible_transmittance": 0.74,
            "typology_source": "AT_TABULA_ScientificReport_AEA_period_window_typologies",
            "g_value_source": "cross_tabula_proxy_dk_pl_double_glazing",
            "visible_transmittance_source": "v1_proxy_not_yet_source_backed",
            "source_note": (
                "AT TABULA provides the period-typical composite double-glazing logic; "
                "numeric g-value is proxied from comparable TABULA double-glazing values in DK/PL."
            ),
        },
        "1990_2000": {
            "window_typology_class": "heat_protection_glazing",
            "n_panes": 2,
            "glazing_family": "double_glazing_low_e",
            "frame_type": "improved_wood_or_plastic",
            "has_low_e": True,
            "has_inert_gas_fill": True,
            "has_thermal_break": False,
            "g_value": 0.60,
            "visible_transmittance": 0.70,
            "typology_source": "AT_TABULA_ScientificReport_AEA_period_window_typologies",
            "g_value_source": "cross_tabula_proxy_de_dk_double_low_e",
            "visible_transmittance_source": "v1_proxy_not_yet_source_backed",
            "source_note": (
                "AT TABULA provides the period-typical heat-protection glazing logic; "
                "numeric g-value is proxied from comparable TABULA double low-e values in DE/DK."
            ),
        },
        "2000_2014": {
            "window_typology_class": "triple_glazing_or_high_performance_window",
            "n_panes": 3,
            "glazing_family": "triple_glazing_low_e_or_high_performance",
            "frame_type": "improved_plastic_or_insulated",
            "has_low_e": True,
            "has_inert_gas_fill": True,
            "has_thermal_break": True,
            "g_value": 0.50,
            "visible_transmittance": 0.66,
            "typology_source": "AT_TABULA_ScientificReport_AEA_period_window_typologies",
            "g_value_source": "cross_tabula_proxy_de_dk_triple_low_e",
            "visible_transmittance_source": "v1_proxy_not_yet_source_backed",
            "source_note": (
                "AT TABULA provides the period-typical triple/high-performance glazing logic; "
                "numeric g-value is proxied from comparable TABULA triple low-e values in DE/DK."
            ),
        },
    }

    return {
        "source": "at_tabula_typology_plus_cross_tabula_window_optics_v1",
        "location": "Vienna",
        "residential_by_period": residential_by_period,
        "notes": [
            "Residential typology classes follow Austrian TABULA / EPISCOPE.",
            "Numeric g-values are cross-TABULA proxies, not Austria-direct g-value measurements.",
            "Visible transmittance remains a documented V1 proxy.",
        ],
    }
