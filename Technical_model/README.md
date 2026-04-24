# Technical Model Package

Physical/dispatch simulation components used by optimization engines.

## Main concepts

- `energy_system/systems/`: registered system runners (active path from registry).
- `energy_system/precompute/`: profile preprocessing and adapter glue.
- `technologies/`: technology sub-models (PV, BESS, EV/V2H, heat pump, etc.).
- `energy_system/ec_clearing.py`: EC internal clearing operator.

## Adding a new system

1. Implement runner under `Technical_model/energy_system/systems/`.
2. Register system id in `Technical_model/energy_system/systems/registry_systems.py`.
3. Point `settings.engine.system_id` to the new id.

