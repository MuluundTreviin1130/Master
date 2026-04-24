from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, List, Optional


@dataclass
class MemberConfig:
    """Run-variable member definition.

    Fields:
        member_id: runtime cohort/member identifier.
        load_profile_key/load_profile_mix: electricity profile selector or profile mixture.
        building_key: legacy key used to fetch building thermal parameters.
        thermal_archetype_key: optional cohort-specific thermal archetype key.
        n_households: runtime multiplicity used to expand profile columns.
        annual_electricity_target_kwh: exogenous profile anchor used to scale the
            sector load profile in precompute. The official sector electricity
            anchor stays in building_stock and is not implicitly folded into this
            field.
        weight: optional weighting factor for future use (defaults to 1.0).
        has_ev/has_hp: optional flags for feature-aware runners.
    """

    member_id: str
    building_key: str
    n_households: int
    load_profile_key: str = ""
    load_profile_mix: dict[str, float] = field(default_factory=dict)
    thermal_archetype_key: str = ""
    sector: str = ""
    represented_gfa_m2: float | None = None
    represented_volume_m3: float | None = None
    annual_heat_target_kwh: float | None = None
    annual_space_heat_target_kwh: float | None = None
    annual_hotwater_target_kwh: float | None = None
    annual_electricity_target_kwh: float | None = None
    dh_connected_share_override: float | None = None
    include_hotwater: bool = True
    weight: float = 1.0
    has_ev: bool = True
    has_hp: bool = True
    label: str = ""

    # Compatibility aliases for existing code paths.
    @property
    def id(self) -> str:
        return self.member_id

    @property
    def count(self) -> int:
        return self.n_households

    @property
    def load_key(self) -> str:
        return str(self.load_profile_key or self.member_id)


@dataclass
class MembersConfig:
    members: List[MemberConfig] = field(default_factory=list)
    household_ids: List[str] = field(default_factory=list)

    @property
    def N_EC(self) -> int:
        return sum(int(m.n_households) for m in self.members)

    @property
    def N_HH(self) -> int:
        hh = set(self.household_ids) if self.household_ids else {m.member_id for m in self.members}
        return sum(int(m.n_households) for m in self.members if m.member_id in hh)

    def get_member_by_id(self, member_id: str) -> Optional[MemberConfig]:
        for m in self.members:
            if m.member_id == member_id:
                return m
        return None


def _coerce_members(rows: Iterable[dict]) -> List[MemberConfig]:
    out: List[MemberConfig] = []
    for row in rows:
        out.append(
            MemberConfig(
                member_id=str(row["member_id"]),
                building_key=str(row.get("building_key", row["member_id"])),
                n_households=int(row.get("n_households", 0)),
                load_profile_key=str(row.get("load_profile_key", row.get("member_id", ""))),
                load_profile_mix={str(k): float(v) for k, v in dict(row.get("load_profile_mix", {})).items()},
                thermal_archetype_key=str(row.get("thermal_archetype_key", row.get("building_key", ""))),
                sector=str(row.get("sector", "")),
                represented_gfa_m2=(
                    None if row.get("represented_gfa_m2") is None else float(row.get("represented_gfa_m2"))
                ),
                represented_volume_m3=(
                    None if row.get("represented_volume_m3") is None else float(row.get("represented_volume_m3"))
                ),
                annual_heat_target_kwh=(
                    None if row.get("annual_heat_target_kwh") is None else float(row.get("annual_heat_target_kwh"))
                ),
                annual_space_heat_target_kwh=(
                    None
                    if row.get("annual_space_heat_target_kwh") is None
                    else float(row.get("annual_space_heat_target_kwh"))
                ),
                annual_hotwater_target_kwh=(
                    None
                    if row.get("annual_hotwater_target_kwh") is None
                    else float(row.get("annual_hotwater_target_kwh"))
                ),
                annual_electricity_target_kwh=(
                    None
                    if row.get("annual_electricity_target_kwh") is None
                    else float(row.get("annual_electricity_target_kwh"))
                ),
                dh_connected_share_override=(
                    None
                    if row.get("dh_connected_share_override") is None
                    else float(row.get("dh_connected_share_override"))
                ),
                include_hotwater=bool(row.get("include_hotwater", True)),
                weight=float(row.get("weight", 1.0)),
                has_ev=bool(row.get("has_ev", True)),
                has_hp=bool(row.get("has_hp", True)),
                label=str(row.get("label", "")),
            )
        )
    return out


def _members_from_building_stock(building_stock: Any) -> MembersConfig:
    if building_stock is None or not hasattr(building_stock, "cohorts"):
        raise ValueError("[members] building_stock with cohorts is required.")
    members: List[MemberConfig] = []
    household_ids: List[str] = []
    for cohort in building_stock.cohorts:
        cohort_id = str(cohort.cohort_id)
        sector = str(cohort.sector)
        if sector == "residential":
            household_ids.append(cohort_id)
        members.append(
            MemberConfig(
                member_id=cohort_id,
                building_key=str(cohort.thermal_archetype_key),
                n_households=1,
                load_profile_key=next(iter(cohort.load_profile_mix.keys()), cohort_id),
                load_profile_mix=dict(cohort.load_profile_mix),
                thermal_archetype_key=str(cohort.thermal_archetype_key),
                sector=sector,
                represented_gfa_m2=float(cohort.represented_gfa_m2),
                represented_volume_m3=float(cohort.represented_volume_m3),
                annual_heat_target_kwh=float(cohort.annual_heat_target_kwh),
                annual_space_heat_target_kwh=float(cohort.annual_space_heat_target_kwh),
                annual_hotwater_target_kwh=float(cohort.annual_hotwater_target_kwh),
                annual_electricity_target_kwh=float(cohort.annual_electricity_target_kwh),
                dh_connected_share_override=cohort.dh_connected_share_override,
                include_hotwater=bool(cohort.include_hotwater),
                label=cohort_id,
            )
        )
    return MembersConfig(members=members, household_ids=household_ids)


def make_members(overrides: dict | None = None, building_stock: Any | None = None) -> MembersConfig:
    """Build default members config (no YAML dependency).

    Default is a full-scale mixed community for production runs.
    Callers can pass override rows through ``get_settings(overrides=...)``.
    """
    if building_stock is not None:
        return _members_from_building_stock(building_stock)

    base = MembersConfig(
        members=[
            MemberConfig(member_id="H0", building_key="H0", n_households=60, load_profile_key="H0", label="Haushalt"),
            MemberConfig(member_id="G0", building_key="G0", n_households=40, load_profile_key="G0", label="Gewerbe allgemein"),
            MemberConfig(member_id="G1", building_key="G1", n_households=20, load_profile_key="G1", label="Gewerbe werktags"),
            MemberConfig(member_id="G2", building_key="G2", n_households=18, load_profile_key="G2", label="Gewerbe stark tags"),
            MemberConfig(member_id="G3", building_key="G3", n_households=12, load_profile_key="G3", label="Gewerbe durchlaufend"),
        ],
        household_ids=["H0"],
    )
    if not overrides:
        return base

    rows = overrides.get("members")
    hh_ids = overrides.get("household_ids")
    if rows is not None:
        base.members = _coerce_members(rows)
    if hh_ids is not None:
        base.household_ids = [str(x) for x in hh_ids]
    return base
