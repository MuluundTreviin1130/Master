from __future__ import annotations

# Kept EXACT legacy key names (CPV, CBESS, Cbuy_grid, ...).
technologies_local = {
    'Vienna': {
        'CPV': 1000.0, 'CBESS': 450.0,
        'CEV': 0.0,'CEV_V2H': 2000,
        'Cbuy_grid': 0.35,'Cfeed_grid': 0.10,
        'Cbuy_community': 0.15,
        'Cfeed_community': 0.15,  # Einheitlicher EC-Feed-in Preis (für alle EC-Trades)
        # Legacy: PV/EV-spezifische Preise bleiben für Rückwärtskompatibilität, werden aber nicht mehr verwendet
        'Cbuy_community_PV': 0.2, 'Cbuy_community_EV': 0.2,
        'Cfeed_community_PV': 0.10, 'Cfeed_community_EV': 0.10,
        'CHP': 1000.0, 'WACC': 0.08,
        'feedin_growth_rate': 0.0, 'electricity_price_growth': 0.01,
    },
    'VilaReal': {
        'CPV': 1100.0, 'CBESS': 600.0,
        'CEV': 2000.0, 'CEV_V2H': 2500.0,
        'Cbuy_grid': 0.30, 'Cfeed_grid': 0.08,
        'Cbuy_community': 0.29,
        'Cfeed_community': 0.08,  # Einheitlicher EC-Feed-in Preis (für alle EC-Trades)
        # Legacy: PV/EV-spezifische Preise bleiben für Rückwärtskompatibilität, werden aber nicht mehr verwendet
        'Cbuy_community_PV': 0.29, 'Cbuy_community_EV': 0.29,
        'Cfeed_community_PV': 0.08, 'Cfeed_community_EV': 0.08,
        'CHP': 950.0, 'WACC': 0.08,
        'feedin_growth_rate': 0.01, 'electricity_price_growth': 0.02,
    },
    'Kemi': {
        'CPV': 1300.0, 'CBESS': 580.0,
        'CEV': 2000.0, 'CEV_V2H': 2500.0,
        'Cbuy_grid': 0.32, 'Cfeed_grid': 0.09,
        'Cbuy_community': 0.31,
        'Cfeed_community': 0.09,  # Einheitlicher EC-Feed-in Preis (für alle EC-Trades)
        # Legacy: PV/EV-spezifische Preise bleiben für Rückwärtskompatibilität, werden aber nicht mehr verwendet
        'Cbuy_community_PV': 0.31, 'Cbuy_community_EV': 0.31,
        'Cfeed_community_PV': 0.09, 'Cfeed_community_EV': 0.09,
        'CHP': 980.0, 'WACC': 0.08,
        'feedin_growth_rate': 0.01, 'electricity_price_growth': 0.02,
    },
}
