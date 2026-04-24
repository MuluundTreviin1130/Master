from __future__ import annotations

# Backward-compatible: keep technologies_local with EXACT keys from legacy Data/data.py.
#
# This facade sits in Data/assembly/, but the canonical local-cost SSOT stays in
# Data/economic_data/. Use the package-absolute import so the moved assembly
# layer does not depend on a non-existent Data.assembly.economic_data package.
from Data.economic_data.location_costs import technologies_local
