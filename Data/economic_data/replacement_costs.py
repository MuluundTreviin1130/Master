from __future__ import annotations

# Global replacement CAPEX multipliers (no location split).
# Example: 0.6 means replacement costs 60% of initial CAPEX.
REPLACEMENT_COST_FACTORS = {
    "PV": 0.8,
    "BESS": 0.6,
    "FC": 0.7,
    "H2_SYSTEM": 0.7,
}
