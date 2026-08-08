# Dispatch Core

This sublayer contains shared dispatch contracts and mode resolution logic.

`gas_boiler_fuel_price.py` keeps the fossil peak-boiler fuel price on a
separate contract from Gas-CHP day-ahead gas prices so Vienna's gas/oil mix
SSOT cannot be silently dropped in MILP fuel-cost terms.
