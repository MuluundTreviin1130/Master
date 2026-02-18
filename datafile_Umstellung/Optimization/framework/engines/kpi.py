from __future__ import annotations

from typing import Any, Dict, List, Tuple

from Optimization.framework.Constraints.dispatch import evaluate_constraints


def _lca_metric_exists(params: Dict[str, Any], metric: str) -> bool:
    for tech in ("PV", "BESS", "Grid"):
        d = params.get(tech, {}).get("LCA", {})
        if metric in d.get("infra", {}) or metric in d.get("op", {}):
            return True
    return False


def _total_lca_metric(
    params: Dict[str, Any],
    metric: str,
    pv_kwp: float,
    bess_kwh: float,
    E_import_grid_L: float,
    pv_generation_L: float = 0.0,
    bess_throughput_L: float = 0.0,
) -> float:
    pv = params.get("PV", {}).get("LCA", {})
    bs = params.get("BESS", {}).get("LCA", {})
    gr = params.get("Grid", {}).get("LCA", {})

    pv_infra = float(pv.get("infra", {}).get(metric, 0.0))
    pv_op = float(pv.get("op", {}).get(metric, 0.0))

    bs_infra = float(bs.get("infra", {}).get(metric, 0.0))
    bs_op = float(bs.get("op", {}).get(metric, 0.0))

    gr_infra = float(gr.get("infra", {}).get(metric, 0.0))
    gr_op = float(gr.get("op", {}).get(metric, 0.0))

    return float(
        pv_infra * pv_kwp
        + bs_infra * bess_kwh
        + gr_infra * 0.0
        + gr_op * E_import_grid_L
        + pv_op * pv_generation_L
        + bs_op * bess_throughput_L
    )


def compute_objectives(
    flows_L: Dict[str, float],
    design_vars: Dict[str, Any],
    settings: Any,
    profiles: Dict[str, Any] | None = None,
) -> Dict[str, float]:
    params = dict(design_vars.get("params", {}))
    lifetime_years = int(design_vars.get("lifetime_years", params.get("lifetime", params.get("lifetime_years", 25))))
    L = int(params.get("lifetime", lifetime_years))

    pv_kwp = float(design_vars.get("pv_kwp", 0.0))
    bess_kwh = float(design_vars.get("bess_kwh", 0.0))

    def Y(k: str) -> float:
        return float(flows_L.get(k, 0.0)) / float(L)

    e_import_grid_Y = Y("E_import_grid_kWh")
    e_export_grid_Y = Y("E_export_grid_kWh")
    e_import_ec_pv_Y = Y("E_import_ec_pv_kWh")
    e_import_ec_ev_Y = Y("E_import_ec_ev_kWh")

    E_import_grid_L = float(flows_L.get("E_import_grid_kWh", 0.0))
    E_export_grid_L = float(flows_L.get("E_export_grid_kWh", 0.0))
    E_load_L = float(flows_L.get("E_total_load_kWh", 0.0))

    obj_names = list(getattr(settings.objectives, "names", []) or [])
    out: Dict[str, float] = {}

    npc_val = None
    if "npc_eur" in obj_names:
        from Cost_model.financial_model import calculate_npc_yearly

        params_fin = dict(params)
        params_fin["pv_size"] = float(pv_kwp)
        params_fin["battery_capacity_kWh"] = float(bess_kwh)

        eng = getattr(settings, "engine", None)
        params_fin.setdefault("EV", {})
        params_fin["EV"]["N_EV_total"] = int(getattr(eng, "N_EV_total", 0))
        params_fin["EV"]["N_EV_bidirectional"] = int(getattr(eng, "N_EV_bidirectional", 0))

        npc_val = float(
            calculate_npc_yearly(
                params_fin,
                e_import_grid_year=e_import_grid_Y,
                e_import_ec_pv_year=e_import_ec_pv_Y,
                e_import_ec_ev_year=e_import_ec_ev_Y,
                e_export_grid_year=e_export_grid_Y,
                e_export_pv_ec_year=0.0,
                e_export_ev_ec_year=0.0,
            )
        )

    autarky_val = None
    if "autarky" in obj_names:
        autarky = 1.0 - (E_import_grid_L / E_load_L) if E_load_L > 0 else 0.0
        autarky_val = float(max(0.0, min(1.0, autarky)))

    for name in obj_names:
        if name == "npc_eur":
            out[name] = float(npc_val or 0.0)
        elif name == "autarky":
            out[name] = float(autarky_val or 0.0)
        elif name == "grid_import_kwh":
            out[name] = float(E_import_grid_L)
        elif name == "grid_export_kwh":
            out[name] = float(E_export_grid_L)
        elif name == "grid_interaction_kwh":
            out[name] = float(E_import_grid_L + E_export_grid_L)
        elif _lca_metric_exists(params, name):
            out[name] = _total_lca_metric(
                params,
                name,
                pv_kwp,
                bess_kwh,
                E_import_grid_L,
                pv_generation_L=float(flows_L.get("PV_generation_kWh", 0.0)),
                bess_throughput_L=float(flows_L.get("BESS_throughput_kWh", 0.0)),
            )
        else:
            raise ValueError(
                f"[kpi] unknown objective '{name}'. "
                f"Supported: npc_eur, autarky, grid_import_kwh, grid_export_kwh, grid_interaction_kwh, "
                f"or any LCA metric present in params[tech]['LCA']."
            )
    return out


def get_selected_objective_names(settings: Any) -> List[str]:
    return list(getattr(getattr(settings, "objectives", None), "names", []) or [])


def compute_constraints(
    flows_L: Dict[str, float],
    design_vars: Dict[str, Any],
    settings: Any,
    profiles: Dict[str, Any] | None = None,
) -> Tuple[List[float], Dict[str, Any]]:
    con_names = list(getattr(settings.constraints, "names", []) or [])
    if not con_names:
        return [], {}

    ctx = {
        "params": dict(design_vars.get("params", {})),
        "E_import_grid_L": float(flows_L.get("E_import_grid_kWh", 0.0)),
        "E_load_L": float(flows_L.get("E_total_load_kWh", 0.0)),
        "E_export_grid_L": float(flows_L.get("E_export_grid_kWh", 0.0)),
        "PV_generation_L": float(flows_L.get("PV_generation_kWh", 0.0)),
        "pv_kwp": float(design_vars.get("pv_kwp", 0.0)),
        "bess_kwh": float(design_vars.get("bess_kwh", 0.0)),
    }
    return evaluate_constraints(settings.constraints, ctx), ctx


def compute_kpis(
    flows_L: Dict[str, float],
    design_vars: Dict[str, Any],
    settings: Any,
    profiles: Dict[str, Any] | None = None,
) -> Tuple[Dict[str, float], List[float], Dict[str, Any]]:
    objectives = compute_objectives(flows_L, design_vars, settings, profiles)
    constraints, ctx = compute_constraints(flows_L, design_vars, settings, profiles)
    return objectives, constraints, ctx
