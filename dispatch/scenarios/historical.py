from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List
import warnings

import numpy as np

from dispatch.core import DispatchInput
from dispatch.scenarios.reduction import reduce_scenarios


@dataclass
class ScenarioBundle:
    inputs: List[DispatchInput]
    probabilities: np.ndarray
    labels: List[str]
    reduction_method: str
    source: str


def _copy_dispatch_input(base: DispatchInput, *, series: Dict[str, Any] | None = None, params: Dict[str, Any] | None = None) -> DispatchInput:
    merged_series = dict(base.series)
    if isinstance(series, dict):
        merged_series.update(series)
    merged_params = dict(base.params)
    if isinstance(params, dict):
        merged_params.update(params)
    return DispatchInput(
        series=merged_series,
        assets=dict(base.assets),
        params=merged_params,
        initial_state=dict(base.initial_state),
    )


def _feature_keys(dispatch_input: DispatchInput) -> List[str]:
    configured = dispatch_input.params.get("dispatch_scenario_feature_keys")
    if configured is None:
        candidates = [
            "ambient_temperature_c",
            "grid_import_price",
        ]
    elif isinstance(configured, (list, tuple)):
        candidates = [str(key) for key in configured]
    else:
        raise TypeError(
            "[dispatch.scenarios] dispatch_scenario_feature_keys must be a list-like value."
        )
    return [key for key in candidates if key in dispatch_input.series]


def _scenario_features(inputs: Iterable[DispatchInput], feature_keys: List[str]) -> np.ndarray:
    rows: list[np.ndarray] = []
    for inp in inputs:
        parts = [np.asarray(inp.series[key], dtype=float).reshape(-1) for key in feature_keys]
        rows.append(np.concatenate(parts, axis=0) if parts else np.zeros(1, dtype=float))
    return np.vstack(rows) if rows else np.zeros((0, 1), dtype=float)


def build_historical_scenario_bundle(dispatch_input: DispatchInput) -> ScenarioBundle:
    raw = dispatch_input.params.get("historical_scenarios")
    method = str(dispatch_input.params.get("dispatch_reduction_method", "fast_forward") or "fast_forward")
    metric = str(
        dispatch_input.params.get("dispatch_distance_metric", "standardized_euclidean")
        or "standardized_euclidean"
    )
    source = str(dispatch_input.params.get("dispatch_scenario_source", "historical") or "historical")
    n_raw = int(dispatch_input.params.get("dispatch_n_raw_scenarios", 0) or 0)
    n_reduced = int(dispatch_input.params.get("dispatch_n_reduced_scenarios", 0) or 0)

    if not isinstance(raw, list) or not raw:
        warnings.warn(
            "[dispatch.scenarios] milp_two_stage requested historical scenarios, but no 'historical_scenarios' were provided.",
            RuntimeWarning,
            stacklevel=2,
        )
        raise ValueError("[dispatch.scenarios] No historical scenarios available for milp_two_stage.")

    items = raw[:n_raw] if n_raw > 0 else raw
    inputs: list[DispatchInput] = []
    probabilities: list[float] = []
    labels: list[str] = []
    for idx, item in enumerate(items):
        if isinstance(item, DispatchInput):
            inputs.append(item)
            probabilities.append(1.0)
            labels.append(f"scenario_{idx}")
            continue
        if not isinstance(item, dict):
            raise ValueError("[dispatch.scenarios] historical_scenarios entries must be dicts or DispatchInput.")
        inputs.append(
            _copy_dispatch_input(
                dispatch_input,
                series=dict(item.get("series") or {}),
                params=dict(item.get("params") or {}),
            )
        )
        probabilities.append(float(item.get("probability", 1.0)))
        labels.append(str(item.get("label", f"scenario_{idx}")))

    probs = np.asarray(probabilities, dtype=float)
    probs = probs / np.sum(probs) if np.sum(probs) > 0.0 else np.full(len(inputs), 1.0 / len(inputs), dtype=float)
    if n_reduced > 0 and n_reduced < len(inputs):
        features = _scenario_features(inputs, _feature_keys(dispatch_input))
        selected, reduced_prob = reduce_scenarios(
            features,
            probs,
            n_reduced,
            method=method,
            metric=metric,
        )
        inputs = [inputs[i] for i in selected.tolist()]
        labels = [labels[i] for i in selected.tolist()]
        probs = reduced_prob

    return ScenarioBundle(
        inputs=inputs,
        probabilities=probs,
        labels=labels,
        reduction_method=method,
        source=source,
    )
