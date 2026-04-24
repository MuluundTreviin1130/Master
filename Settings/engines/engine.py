from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from Settings.technical.features import FeatureFlags
from Settings.technical.members import MembersConfig, make_members


@dataclass
class EngineConfig:
    """Execution context used by engines and system runners."""

    name: str
    system_id: str
    location: str
    country_code: str
    ec_share_import: float
    ec_share_export: float
    N_HH: int
    N_EC: int
    N_EV_total: int
    N_EV_bidirectional: int
    rng_seed: int
    surrogate_artifact_path: Optional[str] = None
    members: MembersConfig = field(default_factory=make_members)
    features: FeatureFlags = field(default_factory=FeatureFlags)
    n_jobs: int = -1
    chunk_size: int = 20000


LOCATION_TO_COUNTRY = {
    "Vienna": "AT",
    "VilaReal": "PT",
    "Kemi": "FI",
}


def resolve_country_code(location: str) -> str:
    """Resolve deterministic location -> country code mapping.

    Raises:
        ValueError: If the location has no configured country mapping.
    """
    code = LOCATION_TO_COUNTRY.get(str(location))
    if not code:
        raise ValueError(
            f"[engine] Missing country_code mapping for location='{location}'. "
            "Add location->country mapping in Settings/engines/engine.py."
        )
    return str(code)


def make_engine(members: MembersConfig | None = None) -> EngineConfig:
    """Build default engine config.

    Members are run-variable and may be injected via ``get_settings(overrides=...)``.
    """
    members_cfg = members if members is not None else make_members()
    if not members_cfg.members:
        raise ValueError("[engine] members configuration must include at least one member.")

    n_ec = members_cfg.N_EC
    n_hh = members_cfg.N_HH
    if n_ec <= 0:
        raise ValueError(f"[engine] N_EC must be > 0, got {n_ec}.")
    if n_hh < 0 or n_hh > n_ec:
        raise ValueError(f"[engine] N_HH ({n_hh}) must satisfy 0 <= N_HH <= N_EC ({n_ec}).")

    location = "Vienna"
    return EngineConfig(
        name="surrogate",
        system_id="ec_flex",
        location=location,
        country_code=resolve_country_code(location),
        ec_share_import=1.0,
        ec_share_export=1.0,
        N_HH=n_hh,
        N_EC=n_ec,
        N_EV_total=50,
        N_EV_bidirectional=50,
        rng_seed=10,
        surrogate_artifact_path=None,
        members=members_cfg,
        features=FeatureFlags(),
        n_jobs=-1,
        chunk_size=20000,
    )
