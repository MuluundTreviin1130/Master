from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from Learning.families.compare_families import compare_families


@dataclass
class FamilyStatus:
    status: str
    family_changed: List[str] = field(default_factory=list)
    append_changed: List[str] = field(default_factory=list)
    refit_changed: List[str] = field(default_factory=list)
    provenance_changed: List[str] = field(default_factory=list)


def resolve_family_status(current, existing) -> FamilyStatus:
    diffs = compare_families(current, existing)
    family_changed = list(diffs["family_changed"])
    append_changed = list(diffs["append_changed"])
    refit_changed = list(diffs["refit_changed"])
    provenance_changed = list(diffs["provenance_changed"])

    if family_changed:
        status = "new_family_required"
    elif append_changed:
        status = "append_only"
    elif refit_changed:
        status = "refit_required"
    elif provenance_changed:
        status = "reusable"
    else:
        status = "reusable"

    return FamilyStatus(
        status=status,
        family_changed=family_changed,
        append_changed=append_changed,
        refit_changed=refit_changed,
        provenance_changed=provenance_changed,
    )
