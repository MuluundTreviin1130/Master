from __future__ import annotations

from typing import Any, Dict, List

from Learning.families.build_family import build_family
from Learning.runtime.resolve_dataset import resolve_dataset
from Learning.runtime.resolve_model import resolve_model


def plan_ablation(settings: Any) -> Dict[str, Any]:
    family = build_family(settings)
    learning = getattr(settings, "learning", None)
    target_blocks = list(getattr(learning, "target_blocks", []) or [])
    target_block_targets = dict(getattr(learning, "target_block_targets", {}) or {})
    active_targets = set(list(family.target_schema.get("names", []) or []))
    resolved_model = resolve_model(settings)
    resolved_dataset = resolve_dataset(settings)

    experiments: List[Dict[str, Any]] = []
    for block in target_blocks:
        block_targets = [t for t in list(target_block_targets.get(str(block), []) or []) if t in active_targets]
        if not block_targets:
            continue
        keep_targets = [t for t in sorted(active_targets) if t not in set(block_targets)]
        experiments.append(
            {
                "kind": "target_block",
                "block": str(block),
                "label": f"drop_{block}",
                "targets": block_targets,
                "keep_targets": keep_targets,
            }
        )

    return {
        "family_hash": family.family_hash,
        "target_blocks": target_blocks,
        "active_targets": sorted(active_targets),
        "resolved_model": resolved_model,
        "resolved_dataset": resolved_dataset,
        "experiments": experiments,
    }
