from __future__ import annotations

# Backward-compatible: keep technologies_global with EXACT keys from legacy Data/data.py.
from .technology_data import PV, BESS, Grid, heatpump, building, EV

technologies_global = {
    'PV': dict(PV),
    'BESS': dict(BESS),
    'Grid': dict(Grid),
    'heatpump': dict(heatpump),
    'building': dict(building),
    'EV': dict(EV),
}
