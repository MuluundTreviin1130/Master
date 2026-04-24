from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List

from Learning.ablation.plan_ablation import plan_ablation
from Learning.policies.resolve_retrain import resolve_retrain
from Learning.registry.register_family import register_family
from Learning.runtime.resolve_dataset import resolve_dataset
from Learning.runtime.resolve_model import resolve_model
from Settings.get_settings import get_settings


def _merge_dicts(base: Dict[str, Any], extra: Dict[str, Any]) -> Dict[str, Any]:
    out = deepcopy(base)
    for key, value in extra.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge_dicts(out[key], value)
        else:
            out[key] = deepcopy(value)
    return out


def _build_experiment_overrides(base_overrides: Dict[str, Any], experiment: Dict[str, Any]) -> Dict[str, Any]:
    keep_targets = list(experiment.get("keep_targets", []) or [])
    extra = {
        "surrogate_train": {
            "targets": keep_targets,
            "include_objectives": False,
        },
        "learning": {
            "force_native_retrain": True,
            "allow_auto_new_family": True,
        },
    }
    return _merge_dicts(base_overrides, extra)


def execute_ablation(
    base_overrides: Dict[str, Any] | None = None,
    *,
    selected_block: str | None = None,
    max_experiments: int | None = None,
) -> Dict[str, Any]:
    base_overrides = dict(base_overrides or {})
    base_settings = get_settings(base_overrides)
    plan = plan_ablation(base_settings)
    experiments = list(plan.get("experiments", []) or [])
    if selected_block:
        experiments = [exp for exp in experiments if str(exp.get("block")) == str(selected_block)]
    if max_experiments is not None:
        experiments = experiments[: int(max_experiments)]

    results: List[Dict[str, Any]] = []
    for experiment in experiments:
        experiment_overrides = _build_experiment_overrides(base_overrides, experiment)
        settings = get_settings(experiment_overrides)
        settings.learning.force_native_retrain = True
        settings.learning.allow_auto_new_family = True

        decision = resolve_retrain(settings, force_native=True)
        spec, registry_path = register_family(
            settings,
            provenance={"source": "run_ablation", "ablation_label": str(experiment.get("label", ""))},
        )
        row: Dict[str, Any] = {
            "label": experiment.get("label"),
            "block": experiment.get("block"),
            "family_hash": spec.family_hash,
            "status": decision.get("status"),
            "action": decision.get("action"),
            "resolved_model_before": decision.get("resolved_model"),
            "resolved_dataset_before": decision.get("resolved_dataset"),
            "executed": False,
            "registry_path": registry_path,
        }
        if decision.get("action") in {"train_model", "register_and_train", "append_then_train"}:
            from Optimization.framework.engines.Surrogat_model.surrogate_engine import SurrogateEngine

            engine = SurrogateEngine(settings)
            row["executed"] = True
            row["artifact_path"] = str(engine._artifact_path)
            row["resolved_model_after"] = resolve_model(settings)
            row["resolved_dataset_after"] = resolve_dataset(settings)
        results.append(row)

    return {
        "base_family_hash": plan.get("family_hash"),
        "selected_block": selected_block,
        "executed_experiments": len(results),
        "results": results,
    }
