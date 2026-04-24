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
    raise RuntimeError(f"[run_ablation] Project root not found from {current}")
project_root_str = str(project_root.resolve())
if project_root_str not in sys.path:
    sys.path.insert(0, project_root_str)

from Learning.ablation.execute_ablation import execute_ablation
from Learning.ablation.plan_ablation import plan_ablation
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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--overrides-json", default="")
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--block", default="")
    ap.add_argument("--max-experiments", type=int, default=0)
    args = ap.parse_args()

    overrides: Dict[str, Any] | None = None
    if args.overrides_json:
        overrides = _load_json(Path(args.overrides_json))

    if args.execute:
        payload = execute_ablation(
            base_overrides=overrides or {},
            selected_block=(args.block or None),
            max_experiments=(args.max_experiments or None),
        )
    else:
        settings = get_settings(overrides or {})
        payload = plan_ablation(settings)
    print(json.dumps(_json_safe(payload), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
