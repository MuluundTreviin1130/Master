from __future__ import annotations

BESS = {
    # environmental indicator
    'PEF': 1200.0,
    'water': 20000,   # kg water/kWh (legacy placeholder)

    'DoD': 0.85,
    'efficiency': 0.85,
    'max_cycles': 6500,
    'eol_capacity': 0.8,
    'battery_lifetime': 15,
    'self_discharge': 0.001,
    'power_kW': 5.0,
    'maintenance_rate_BESS': 0.01,
    'max_c_rate': 1.0,
}
