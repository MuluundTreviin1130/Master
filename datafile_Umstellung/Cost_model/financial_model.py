from __future__ import annotations

def calculate_npc_yearly(params,
                         e_import_grid_year,
                         e_import_ec_pv_year=0.0,
                         e_import_ec_ev_year=0.0,
                         e_export_grid_year=0.0,
                         e_export_pv_ec_year=0.0,
                         e_export_ev_ec_year=0.0) -> float:
    """
    Jahresbasierte NPC-Berechnung (€/NPV) für Community.
    Erwartet Preise in €/kWh, Energiemengen in kWh/a. EV-Zähler aus params['EV'].
    """
    float_ = float  # tiny shortcut

    # CAPEX
    capex_pv   = float_(params['CPV'])   * float_(params.get('pv_size'))
    capex_batt = float_(params['CBESS']) * float_(params.get('battery_capacity_kWh'))

    ev = params.setdefault('EV', {})
    n_ev_bidir  = int(ev.get('N_EV_bidirectional', 0))
    n_ev_total  = int(ev.get('N_EV_total', 0))
    n_ev_charge = max(0, n_ev_total - n_ev_bidir)

    capex_ev_charge = float_(params.get('CEV', 0.0))     * n_ev_charge
    capex_ev_bidir  = float_(params.get('CEV_V2H', 0.0)) * n_ev_bidir
    capex_ev        = capex_ev_charge + capex_ev_bidir

    total_capex = capex_pv + capex_batt + capex_ev

    # OPEX (als % von CAPEX-Komponenten)
    opex_pv   = capex_pv   * float_(params['PV'].get('maintenance_rate_PV', 0.0))
    opex_bess = capex_batt * float_(params['BESS'].get('maintenance_rate_BESS', 0.0))
    opex_ev   = capex_ev   * float_(params['EV'].get('maintenance_rate_EV', 0.0))
    opex_annual = opex_pv + opex_bess + opex_ev

    # Raten/Preise
    lifetime = int(params.get('lifetime'))
    wacc     = float_(params.get('WACC'))

    r_grid = float_(params.get('electricity_price_growth', 0.0))
    r_feed = float_(params.get('feedin_growth_rate', 0.0))
    r_ec   = float_(params.get('ec_price_growth', r_feed))

    c_buy_grid   = float_(params.get('Cbuy_grid'))
    c_feed_grid  = float_(params.get('Cfeed_grid'))
    # Einheitliche EC-Preise (unabhängig von PV/EV)
    c_buy_ec     = float_(params.get('Cbuy_community', c_buy_grid))
    c_feed_ec    = float_(params.get('Cfeed_community', c_feed_grid))

    # BESS Replacement (z. B. 60% von Neu-CAPEX) am Ende jedes battery_lifetime-Jahres (ohne letztes)
    batt_life = params['BESS'].get('battery_lifetime')
    batt_life = int(batt_life) if batt_life else None
    repl_cost_nominal = 0.6 * float_(params['CBESS']) * float_(params.get('battery_capacity_kWh')) if batt_life else 0.0

    npc = total_capex

    for y in range(1, lifetime + 1):
        price_buy_grid   = c_buy_grid   * ((1 + r_grid) ** (y - 1))
        price_feed_grid  = c_feed_grid  * ((1 + r_feed) ** (y - 1))
        price_buy_ec     = c_buy_ec     * ((1 + r_ec)   ** (y - 1))
        price_feed_ec    = c_feed_ec    * ((1 + r_ec)   ** (y - 1))

        cost_import_grid = e_import_grid_year  * price_buy_grid
        cost_import_ec   = (e_import_ec_pv_year + e_import_ec_ev_year) * price_buy_ec

        rev_export_grid  = e_export_grid_year  * price_feed_grid
        rev_export_ec    = (e_export_pv_ec_year + e_export_ev_ec_year) * price_feed_ec

        annual_net = (cost_import_grid + cost_import_ec) \
                   - (rev_export_grid + rev_export_ec) \
                   + opex_annual

        if batt_life and (y % batt_life == 0) and y < lifetime:
            annual_net += repl_cost_nominal

        npc += annual_net / ((1 + wacc) ** y)

    return float(npc)
