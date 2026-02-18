from __future__ import annotations

EV = {
    'PEF': 0.0,
    'capacity_kWh': 60.0,
    'max_soc': 1.0,
    'initial_soc': 0.5,
    'charging_efficiency': 0.95,
    'discharging_efficiency': 0.95,
    'max_charge_power': 11.0,
    'max_discharge_power': 11.0,
    'degradation_rate': 0.005,
    'self_discharge_EV': 0.001,
    'maintenance_rate_EV': 0.001,
    'charge_c_rate_table': [
        {'min_temp': -273,   'max_temp': 278.15, 'c_rate': 1.0},
        {'min_temp': 278.15, 'max_temp': 283.15, 'c_rate': 1.0},
        {'min_temp': 283.15, 'max_temp': 318.15, 'c_rate': 1.0},
        {'min_temp': 318.15, 'max_temp': 333.15, 'c_rate': 1.0},
        {'min_temp': 333.15, 'max_temp': 1000,   'c_rate': 1.0},
    ],
    'discharge_c_rate_table': [
        {'min_temp': 0,      'max_temp': 263.15, 'c_rate': 1.0},
        {'min_temp': 263.15, 'max_temp': 273.15, 'c_rate': 1.0},
        {'min_temp': 273.15, 'max_temp': 318.15, 'c_rate': 1.0},
        {'min_temp': 318.15, 'max_temp': 333.15, 'c_rate': 1.0},
        {'min_temp': 333.15, 'max_temp': 1000,   'c_rate': 1.0},
    ],
}
