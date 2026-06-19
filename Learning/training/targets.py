from __future__ import annotations

from typing import Dict, Iterable, List


def resolve_target_values(
    *,
    targets: Iterable[str],
    objectives: Dict[str, float],
    flows_L: Dict[str, float],
) -> List[float]:
    """Resolve configured surrogate targets without inventing missing labels.

    Objective targets take precedence because they may be derived KPIs rather
    than raw lifetime flow entries. Raw flow targets are accepted only when the
    teacher explicitly exported the requested key. Anything else is a schema or
    settings mismatch and must stop training before a corrupted zero label is
    written into a reusable dataset.
    """

    values: List[float] = []
    missing: List[str] = []
    for target in targets:
        key = str(target)
        if key in objectives:
            values.append(float(objectives[key]))
            continue
        if key in flows_L:
            values.append(float(flows_L[key]))
            continue
        missing.append(key)
    if missing:
        available = sorted({str(k) for k in objectives} | {str(k) for k in flows_L})
        raise KeyError(
            "[surrogate-train] Teacher output is missing required target(s): "
            f"{missing}. Available objective/flow keys: {available}"
        )
    return values
