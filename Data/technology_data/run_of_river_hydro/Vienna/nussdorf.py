from __future__ import annotations

from Data.technology_data.run_of_river_hydro.Vienna.freudenau import (
    load_freudenau_hourly_flow_proxy,
    load_freudenau_hourly_flow_proxy_context,
)


NUSSDORF_INSTALLED_KW = 4_800.0

# V1 proxy: same climatology-based capacity factor as Freudenau, but capped by
# the official Nussdorf nameplate of 4.8 MW. This yields a physically feasible
# annual energy anchor without inventing a Nussdorf-specific production series.
NUSSDORF_ANNUAL_GENERATION_GWH = (NUSSDORF_INSTALLED_KW / 172_000.0) * 1_052.0

__all__ = [
    "NUSSDORF_INSTALLED_KW",
    "NUSSDORF_ANNUAL_GENERATION_GWH",
    "load_freudenau_hourly_flow_proxy",
    "load_freudenau_hourly_flow_proxy_context",
]
