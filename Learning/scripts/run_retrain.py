from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

current = Path(__file__).resolve()
project_root = None
for parent in current.parents:
    if (parent / "Learning").is_dir() and (parent / "Optimization").is_dir():
        project_root = parent
        break
if project_root is None:
    raise RuntimeError(f"[run_retrain] Project root not found from {current}")
project_root_str = str(project_root.resolve())
if project_root_str not in sys.path:
    sys.path.insert(0, project_root_str)

from Learning.policies.resolve_retrain import resolve_retrain
from Learning.registry.register_family import register_family
from Learning.runtime.resolve_dataset import resolve_dataset
from Learning.runtime.resolve_model import resolve_model
from Settings.get_settings import get_settings


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _json_safe(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    return value


def _decide_remediation(settings: Any, training_info: Dict[str, Any], round_idx: int) -> Dict[str, Any]:
    gate_cfg = getattr(getattr(settings, "learning", None), "validation_gate", None)
    gate_result = dict((training_info or {}).get("gate_result") or {})
    failed_targets = list(gate_result.get("failed_targets") or [])
    failed_critical = list(gate_result.get("failed_critical_targets") or [])
    failed_secondary = list(gate_result.get("failed_secondary_targets") or [])
    pass_share = float(gate_result.get("pass_share", 0.0) or 0.0)
    if gate_cfg is None:
        return {"retry": False, "reason": "gate_config_missing"}
    if bool(gate_result.get("eligible")):
        return {"retry": False, "reason": "already_eligible"}
    if str(gate_result.get("reason") or "") not in {"metrics_below_threshold", "insufficient_target_coverage"}:
        return {"retry": False, "reason": "non_remediable_gate_reason"}
    if bool(getattr(gate_cfg, "remediation_stop_on_zero_pass_share", True)) and pass_share <= 0.0:
        return {"retry": False, "reason": "zero_pass_share"}

    min_failed = int(getattr(gate_cfg, "remediation_min_failed_targets_for_retry", 1))
    if len(failed_targets) < min_failed:
        return {"retry": False, "reason": "too_few_failed_targets"}
    stop_after_critical = int(getattr(gate_cfg, "remediation_stop_after_critical_fail_rounds", 2))
    if failed_critical and round_idx >= stop_after_critical:
        return {
            "retry": False,
            "reason": "persistent_critical_failures",
            "failed_critical_targets": failed_critical,
            "pass_share": pass_share,
        }

    growth = float(getattr(gate_cfg, "remediation_append_growth_factor", 2.0))
    critical_multiplier = float(getattr(gate_cfg, "remediation_critical_growth_multiplier", 1.5))
    cap = int(getattr(gate_cfg, "remediation_max_append_samples", 200))
    learning = getattr(settings, "learning", None)
    base_append = int(getattr(learning, "max_auto_append_samples", 50))
    factor = growth ** max(0, round_idx)
    if failed_critical:
        factor *= critical_multiplier
    if failed_secondary and not failed_critical:
        factor *= 1.0
    next_append = int(min(cap, max(base_append, round(base_append * factor))))
    return {
        "retry": True,
        "reason": "append_then_train",
        "next_append_samples": next_append,
        "failed_targets": failed_targets,
        "failed_critical_targets": failed_critical,
        "failed_secondary_targets": failed_secondary,
        "pass_share": pass_share,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--overrides-json", default="")
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--force-native", action="store_true")
    args = ap.parse_args()

    overrides: Dict[str, Any] | None = None
    if args.overrides_json:
        overrides = _load_json(Path(args.overrides_json))

    settings = get_settings(overrides or {})
    if args.force_native:
        settings.learning.force_native_retrain = True
    decision = resolve_retrain(settings, force_native=args.force_native)
    spec, registry_path = register_family(settings, provenance={"source": "run_retrain"})
    payload = {
        "registry_path": registry_path,
        "family_hash": spec.family_hash,
        "status": decision["status"],
        "action": decision["action"],
        "family_status": decision.get("family_status"),
        "resolved_model": decision["resolved_model"],
        "resolved_dataset": decision.get("resolved_dataset"),
        "has_native_model": decision.get("has_native_model"),
        "has_dataset": decision.get("has_dataset"),
        "force_native": bool(args.force_native),
    }

    if args.execute and decision["action"] in {"train_model", "register_and_train", "append_then_train"}:
        from Optimization.framework.engines.Surrogat_model.surrogate_engine import SurrogateEngine

        gate_cfg = getattr(getattr(settings, "learning", None), "validation_gate", None)
        auto_remediate = bool(getattr(gate_cfg, "auto_remediate_on_blocked", False)) if gate_cfg else False
        max_rounds = int(getattr(gate_cfg, "max_remediation_rounds", 0)) if gate_cfg else 0
        attempts = []
        last_engine = None
        original_max_append = int(getattr(settings.learning, "max_auto_append_samples", 50))
        for round_idx in range(max(1, max_rounds + 1)):
            if round_idx > 0:
                settings.learning.force_append_then_train = True
            else:
                settings.learning.force_append_then_train = False
            engine = SurrogateEngine(settings)
            last_engine = engine
            training_info = dict(getattr(engine, "_last_training_info", None) or {})
            attempts.append(
                {
                    "round": int(round_idx),
                    "action": str(decision.get("action")),
                    "artifact_path": str(engine._artifact_path),
                    "training_info": training_info,
                }
            )
            gate_result = training_info.get("gate_result", {}) if training_info else {}
            if not training_info or bool(gate_result.get("eligible")) or not auto_remediate or round_idx >= max_rounds:
                break
            remediation = _decide_remediation(settings, training_info, round_idx + 1)
            attempts[-1]["remediation"] = remediation
            if not bool(remediation.get("retry")):
                break
            settings.learning.max_auto_append_samples = int(remediation.get("next_append_samples", original_max_append))
        settings.learning.force_append_then_train = False
        settings.learning.max_auto_append_samples = original_max_append

        payload["executed"] = True
        payload["artifact_path"] = str(last_engine._artifact_path) if last_engine is not None else None
        payload["training_attempts"] = attempts
        payload["resolved_model_after"] = resolve_model(settings)
        payload["resolved_dataset_after"] = resolve_dataset(settings)
        if attempts:
            final_training = dict(attempts[-1].get("training_info") or {})
            payload["training_info"] = final_training
            final_gate = dict(final_training.get("gate_result") or {})
            payload["gate_result"] = final_gate
            payload["final_stage"] = final_training.get("validation_stage")
    else:
        payload["executed"] = False

    print(json.dumps(_json_safe(payload), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
