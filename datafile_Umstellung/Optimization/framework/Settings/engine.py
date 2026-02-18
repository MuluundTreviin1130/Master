from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import sys
from pathlib import Path

# Robust import handling for both module import and direct execution
try:
    from .members import MembersConfig, make_members
except ImportError:
    # Fallback: try absolute import
    try:
        from Optimization.framework.Settings.members import MembersConfig, make_members
    except ImportError:
        # Fallback: add datafile_Umstellung directory to path and import
        current_file = Path(__file__).resolve()
        # Navigate: Settings -> framework -> Optimization -> datafile_Umstellung
        settings_dir = current_file.parent
        framework_dir = settings_dir.parent
        optimization_dir = framework_dir.parent
        datafile_umstellung_dir = optimization_dir.parent
        
        # Add datafile_Umstellung to path (this is where Optimization module lives)
        if str(datafile_umstellung_dir) not in sys.path:
            sys.path.insert(0, str(datafile_umstellung_dir))
        
        from Optimization.framework.Settings.members import MembersConfig, make_members


@dataclass
class EngineConfig:
    """Execution context (engine choice + scenario counts)."""
    name: str
    system_id: str
    location: str

    ec_share_import: float
    ec_share_export: float

    N_HH: int  # Number of household members (derived from members.household_ids)
    N_EC: int  # Total number of EC members (derived from members.sum(count))
    N_EV_total: int
    N_EV_bidirectional: int

    rng_seed: int
    surrogate_artifact_path: Optional[str] = None

    members: Optional[MembersConfig] = None  # Member composition (None = legacy mode)

    n_jobs: int = -1
    chunk_size: int = 20000


def make_engine() -> EngineConfig:
    """Default engine config (edit here, not in get_settings)."""
    # Load members configuration (no legacy fallback)
    members = make_members(legacy_N_HH=None)
    
    if members is None or len(members.members) == 0:
        raise ValueError(
            "[engine] members.yaml is required. No legacy fallback available. "
            "Please create Optimization/framework/Settings/members.yaml with member definitions."
        )

    # Derive N_EC and N_HH from members
    N_EC = members.N_EC
    N_HH = members.N_HH
    
    if N_EC <= 0:
        raise ValueError(f"[engine] N_EC must be > 0, but got {N_EC} from members configuration.")
    
    if N_HH < 0 or N_HH > N_EC:
        raise ValueError(
            f"[engine] N_HH ({N_HH}) must be >= 0 and <= N_EC ({N_EC}). "
            f"Check household_ids in members.yaml."
        )
    
    # Print member composition at optimization start
    counts_by_id = {m.id: m.count for m in members.members}
    h0_count = counts_by_id.get("H0", 0)
    g0_count = counts_by_id.get("G0", 0)
    g1_count = counts_by_id.get("G1", 0)
    g2_count = counts_by_id.get("G2", 0)
    g3_count = counts_by_id.get("G3", 0)
    household_ids_str = ",".join(members.household_ids) if members.household_ids else "[]"

    return EngineConfig(
        name="gated", #alternatives: "fast", "gold", "gated", "surrogate"
        system_id="PV_BESS_HP_V2H",
        location="Vienna",

        ec_share_import=1,
        ec_share_export=1,

        N_HH=N_HH,
        N_EC=N_EC,
        N_EV_total=50,
        N_EV_bidirectional=50,

        rng_seed=10,
        surrogate_artifact_path=None,
        members=members,
        n_jobs=-1,
        chunk_size=20000,
    )
