from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import yaml


@dataclass
class MemberConfig:
    """Single EC member definition."""
    id: str  # Profile ID (e.g., "H0", "G0")
    label: str  # Human-readable label
    count: int  # Number of members of this type
    building_key: str  # Key for building parameters (typically same as id)


@dataclass
class MembersConfig:
    """EC member composition configuration."""
    members: List[MemberConfig] = field(default_factory=list)
    household_ids: List[str] = field(default_factory=list)

    @property
    def N_EC(self) -> int:
        """Total number of EC members."""
        return sum(m.count for m in self.members)

    @property
    def N_HH(self) -> int:
        """Number of household members (sum of counts for members in household_ids)."""
        hh_set = set(self.household_ids)
        return sum(m.count for m in self.members if m.id in hh_set)

    def get_member_by_id(self, member_id: str) -> Optional[MemberConfig]:
        """Get member config by ID."""
        for m in self.members:
            if m.id == member_id:
                return m
        return None


def load_members_yaml(path: Path) -> Optional[MembersConfig]:
    """Load members configuration from YAML file."""
    if not path.exists():
        return None

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        members_list = data.get("members", [])
        members = [
            MemberConfig(
                id=str(m["id"]),
                label=str(m["label"]),
                count=int(m["count"]),
                building_key=str(m.get("building_key", m["id"])),
            )
            for m in members_list
        ]

        household_ids = [str(hid) for hid in data.get("household_ids", [])]

        return MembersConfig(members=members, household_ids=household_ids)
    except Exception as e:
        print(f"[members] Warning: Failed to load members.yaml: {e}. Using legacy defaults.")
        return None


def make_members(legacy_N_HH: Optional[int] = None) -> Optional[MembersConfig]:
    """
    Create members configuration.
    
    If members.yaml exists, load it.
    Otherwise, returns None (no legacy fallback).
    
    Args:
        legacy_N_HH: Ignored (kept for signature compatibility, but not used).
    
    Returns:
        MembersConfig instance if YAML exists, None otherwise.
    """
    # Compute two candidate paths
    p1 = Path("Optimization/framework/Settings/members.yaml")
    p2 = Path(__file__).parent / "members.yaml"
    
    # Resolve both paths if they exist
    p1_exists = p1.exists()
    p2_exists = p2.exists()
    
    if p1_exists and p2_exists:
        p1_resolved = p1.resolve()
        p2_resolved = p2.resolve()
        if p1_resolved != p2_resolved:
            raise ValueError(
                f"[members] Ambiguous members.yaml paths: both exist and differ.\n"
                f"  Path 1 (cwd-relative): {p1_resolved}\n"
                f"  Path 2 (module-relative): {p2_resolved}\n"
                f"  Please remove one or ensure they are identical."
            )
        # Both exist and are the same file, use p1
        yaml_path = p1
    elif p1_exists:
        yaml_path = p1
    elif p2_exists:
        yaml_path = p2
    else:
        # Neither exists, return None
        return None

    members_cfg = load_members_yaml(yaml_path)

    if members_cfg is not None:
        return members_cfg

    # No legacy fallback - return None
    return None
