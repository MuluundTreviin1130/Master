from __future__ import annotations

from typing import Any, Dict

from dispatch.core import DispatchInput, DispatchResult


def run_heuristic_dispatch(dispatch_input: DispatchInput, **_: Any) -> DispatchResult:
    """Normalize legacy heuristic outputs into the shared dispatch contract.

    The current repo still computes heuristic operation inside the existing
    system runners. This wrapper intentionally does not re-implement that
    logic. Instead it accepts already computed hourly outputs through
    ``params['legacy_hourly']`` so the existing path can be bridged gradually.
    """

    legacy_hourly = dispatch_input.params.get("legacy_hourly", {})
    if not isinstance(legacy_hourly, dict):
        raise ValueError("[dispatch] heuristic wrapper expects params['legacy_hourly'] as dict.")

    objective_terms = dispatch_input.params.get("objective_terms", {})
    if not isinstance(objective_terms, dict):
        raise ValueError("[dispatch] heuristic wrapper expects params['objective_terms'] as dict.")

    diagnostics: Dict[str, Any] = {
        "mode": "heuristic",
        "source": "legacy_hourly",
    }
    extra_diag = dispatch_input.params.get("diagnostics", {})
    if isinstance(extra_diag, dict):
        diagnostics.update(extra_diag)

    return DispatchResult(
        hourly=dict(legacy_hourly),
        objective_terms={str(k): float(v) for k, v in objective_terms.items()},
        diagnostics=diagnostics,
    )
