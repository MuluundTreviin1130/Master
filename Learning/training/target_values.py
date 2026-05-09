from __future__ import annotations

from typing import Dict, Iterable, List


def resolve_teacher_target_row(
    targets: Iterable[str],
    objectives: Dict[str, float],
    flows_L: Dict[str, float],
) -> List[float]:
    """Resolve one supervised training row from explicit teacher outputs.

    Surrogate targets are a mixed contract: some names are KPI objectives
    computed by ``compute_kpis``, while others are raw lifetime flow exports from
    the teacher. A target that is in neither mapping means the teacher did not
    provide the requested supervised signal. Returning ``0.0`` in that case
    silently corrupts datasets and model artifacts, so this helper fails before
    the row can be persisted.
    """

    row: List[float] = []
    missing: List[str] = []

    for raw_name in targets:
        name = str(raw_name)
        if name in objectives:
            row.append(float(objectives[name]))
        elif name in flows_L:
            row.append(float(flows_L[name]))
        else:
            missing.append(name)

    if missing:
        available_objectives = ", ".join(sorted(str(key) for key in objectives.keys())) or "<none>"
        available_flows = ", ".join(sorted(str(key) for key in flows_L.keys())) or "<none>"
        raise KeyError(
            "[surrogate_train] Teacher evaluation did not export required surrogate target(s): "
            f"{', '.join(missing)}. Available KPI objectives: {available_objectives}. "
            f"Available teacher flows: {available_flows}."
        )

    return row
