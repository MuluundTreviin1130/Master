# Dispatch Core

This sublayer contains shared dispatch contracts and mode resolution logic.

- `heat_pump_cop.py` — fail-fast COP resolution for positive DH heat-pump capacity
  (no silent `COP=1.0` / `1e-9` invention in MILP modes).
