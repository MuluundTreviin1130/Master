from __future__ import annotations

"""Debug the `milp_day_ahead -> milp_two_stage` replay gap for one candidate.

This runner exists for one narrow purpose:

1. take one already-exported `selected_candidate.json`,
2. rebuild the active Wiener gold settings from the documented SSOT overrides,
3. replay that exact candidate through a configurable scenario ladder,
4. persist which scenario width is still feasible and how runtime scales.

Why this exists:
- the Thermflex paper currently searches and gold-rechecks candidates mainly on
  `milp_day_ahead`,
- but operational robustness under uncertainty matters, so we need a reproducible
  bridge into `milp_two_stage`,
- ad-hoc shell tests are not enough; the current state must be written as an
  explicit artifact that can be revisited later.

There are no silent fallbacks:
- the candidate file must exist,
- the active bound vector must be complete,
- every ladder token must be parseable as `raw:reduced`,
- every run step writes an explicit status entry.
"""

import argparse
import json
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any


def _bootstrap_project_root() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "Optimization").is_dir() and (parent / "Data").is_dir():
            project_root = parent
            project_root_str = str(project_root)
            if project_root_str not in sys.path:
                sys.path.insert(0, project_root_str)
            return project_root
    raise RuntimeError("[run_vienna_two_stage_gap_debug] Project root not found.")


PROJECT_ROOT = _bootstrap_project_root()

from Optimization.framework.engines.Gold.gold_engine import GoldEngine
from Optimization.run.papers.dh_thermflex.run_vienna_selected_candidate_two_stage import (
    DEFAULT_BASE_OVERRIDE,
    DEFAULT_DISPATCH_OVERRIDE,
    _build_two_stage_settings,
    _load_json,
    _resolve_x,
)


DEFAULT_LADDER = "1:1,4:1,8:2,16:3"


def _parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selected-candidate-json", required=True, type=str)
    ap.add_argument("--base-override", default=str(DEFAULT_BASE_OVERRIDE), type=str)
    ap.add_argument("--dispatch-override", default=str(DEFAULT_DISPATCH_OVERRIDE), type=str)
    ap.add_argument(
        "--ladder",
        default=DEFAULT_LADDER,
        type=str,
        help="Comma-separated raw:reduced steps, e.g. '1:1,4:1,8:2,16:3'.",
    )
    ap.add_argument(
        "--append-dispatch-ssot-step",
        action="store_true",
        help="Append the n_raw/n_reduced pair from the explicit two-stage dispatch SSOT.",
    )
    return ap.parse_args()


def _parse_ladder(text: str) -> list[tuple[int, int]]:
    steps: list[tuple[int, int]] = []
    tokens = [token.strip() for token in str(text).split(",") if token.strip()]
    if not tokens:
        raise ValueError("[run_vienna_two_stage_gap_debug] --ladder must contain at least one raw:reduced step.")
    for token in tokens:
        if ":" not in token:
            raise ValueError(
                "[run_vienna_two_stage_gap_debug] Ladder token must look like 'raw:reduced', got "
                f"'{token}'."
            )
        raw_text, reduced_text = token.split(":", 1)
        raw = int(raw_text)
        reduced = int(reduced_text)
        if raw <= 0 or reduced <= 0:
            raise ValueError(
                "[run_vienna_two_stage_gap_debug] raw and reduced scenario counts must be > 0, got "
                f"{raw}:{reduced}."
            )
        if reduced > raw:
            raise ValueError(
                "[run_vienna_two_stage_gap_debug] reduced scenarios must not exceed raw scenarios, got "
                f"{raw}:{reduced}."
            )
        steps.append((raw, reduced))
    return steps


def _append_dispatch_ssot_step(
    *,
    ladder: list[tuple[int, int]],
    dispatch_override_path: Path,
) -> list[tuple[int, int]]:
    dispatch_override = _load_json(dispatch_override_path)
    dispatch_block = dispatch_override.get("dispatch")
    if not isinstance(dispatch_block, dict):
        raise KeyError(
            "[run_vienna_two_stage_gap_debug] dispatch override does not define a usable 'dispatch' block."
        )
    raw = int(dispatch_block.get("n_raw_scenarios", 0) or 0)
    reduced = int(dispatch_block.get("n_reduced_scenarios", 0) or 0)
    if raw <= 0 or reduced <= 0:
        raise ValueError(
            "[run_vienna_two_stage_gap_debug] dispatch override must define positive n_raw_scenarios and "
            "n_reduced_scenarios when --append-dispatch-ssot-step is used."
        )
    if reduced > raw:
        raise ValueError(
            "[run_vienna_two_stage_gap_debug] dispatch override has invalid scenario counts: "
            f"{raw}:{reduced}."
        )
    if (raw, reduced) not in ladder:
        ladder.append((raw, reduced))
    return ladder


def _read_latest_dispatch_kpis(run_dir: Path) -> dict[str, Any] | None:
    path = run_dir / "dispatch_kpis.json"
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    latest = payload.get("latest_point")
    return latest if isinstance(latest, dict) else None


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Two-Stage Gap Debug",
        "",
        f"- selection_label: `{payload['selection_label']}`",
        f"- selected_candidate_json: `{payload['selected_candidate_json']}`",
        f"- base_override: `{payload['base_override']}`",
        f"- dispatch_override: `{payload['dispatch_override']}`",
        "",
        "## Steps",
        "",
        "| step | raw | reduced | status | eval_s | objective_eur | operating_cost_eur | penalty_eur | note |",
        "| --- | ---: | ---: | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for item in payload["steps"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(item["step_label"]),
                    str(item["n_raw_scenarios"]),
                    str(item["n_reduced_scenarios"]),
                    str(item["status"]),
                    f"{float(item['eval_s']):.2f}" if item.get("eval_s") is not None else "",
                    f"{float(item['dispatch_objective_eur']):.6f}" if item.get("dispatch_objective_eur") is not None else "",
                    f"{float(item['dispatch_operating_cost_eur']):.6f}" if item.get("dispatch_operating_cost_eur") is not None else "",
                    f"{float(item['dispatch_penalty_total_eur']):.6f}" if item.get("dispatch_penalty_total_eur") is not None else "",
                    str(item.get("note", "")),
                ]
            )
            + " |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = _parse_args()
    selected_candidate_path = Path(args.selected_candidate_json).resolve()
    base_override_path = Path(args.base_override).resolve()
    dispatch_override_path = Path(args.dispatch_override).resolve()

    selected_payload = _load_json(selected_candidate_path)
    selected_payload["_selected_candidate_path"] = str(selected_candidate_path)

    ladder = _parse_ladder(args.ladder)
    if args.append_dispatch_ssot_step:
        ladder = _append_dispatch_ssot_step(
            ladder=ladder,
            dispatch_override_path=dispatch_override_path,
        )

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    selection_label = str(selected_payload["selection_label"])
    root_dir = selected_candidate_path.parent / f"{stamp}_{selection_label}_two_stage_gap_debug"
    root_dir.mkdir(parents=True, exist_ok=False)

    request_payload = {
        "selection_label": selection_label,
        "selected_candidate_json": str(selected_candidate_path),
        "base_override": str(base_override_path),
        "dispatch_override": str(dispatch_override_path),
        "ladder": [{"n_raw_scenarios": raw, "n_reduced_scenarios": reduced} for raw, reduced in ladder],
    }
    _write_json(root_dir / "request.json", request_payload)

    summary_payload: dict[str, Any] = {
        "selection_label": selection_label,
        "selected_candidate_json": str(selected_candidate_path),
        "base_override": str(base_override_path),
        "dispatch_override": str(dispatch_override_path),
        "steps": [],
    }

    for raw, reduced in ladder:
        step_label = f"raw{raw}_red{reduced}"
        step_dir = root_dir / step_label
        if step_dir.exists():
            shutil.rmtree(step_dir)
        step_dir.mkdir(parents=True, exist_ok=False)

        settings = _build_two_stage_settings(
            base_override_path=base_override_path,
            dispatch_override_path=dispatch_override_path,
            selected_payload=selected_payload,
        )
        # The whole point of this runner is to vary only the scenario width while
        # holding the candidate vector and the structural two-stage dispatch path
        # fixed. We therefore override only these two explicit dispatch counters.
        settings.dispatch.n_raw_scenarios = int(raw)
        settings.dispatch.n_reduced_scenarios = int(reduced)
        x = _resolve_x(settings, selected_payload)

        step_payload: dict[str, Any] = {
            "step_label": step_label,
            "n_raw_scenarios": int(raw),
            "n_reduced_scenarios": int(reduced),
            "status": "pending",
            "run_dir": str(step_dir),
            "eval_s": None,
            "dispatch_objective_eur": None,
            "dispatch_operating_cost_eur": None,
            "dispatch_penalty_total_eur": None,
            "note": "",
        }

        t0 = time.perf_counter()
        try:
            GoldEngine(settings, run_dir=str(step_dir)).evaluate(x)
            step_payload["eval_s"] = float(time.perf_counter() - t0)
            latest = _read_latest_dispatch_kpis(step_dir)
            if latest is None:
                raise FileNotFoundError(
                    "[run_vienna_two_stage_gap_debug] dispatch_kpis.json missing after successful gold evaluation."
                )
            step_payload["dispatch_objective_eur"] = float(latest["dispatch_objective_eur"])
            step_payload["dispatch_operating_cost_eur"] = float(latest["dispatch_operating_cost_eur"])
            step_payload["dispatch_penalty_total_eur"] = float(latest["dispatch_penalty_total_eur"])
            step_payload["status"] = "ok"
        except Exception as exc:
            step_payload["eval_s"] = float(time.perf_counter() - t0)
            step_payload["status"] = "failed"
            step_payload["exception_type"] = type(exc).__name__
            step_payload["exception"] = str(exc)
            step_payload["note"] = "First failing ladder step."
            summary_payload["steps"].append(step_payload)
            _write_json(root_dir / "ladder_summary.json", summary_payload)
            _write_markdown(root_dir / "ladder_summary.md", summary_payload)
            raise

        summary_payload["steps"].append(step_payload)
        _write_json(root_dir / "ladder_summary.json", summary_payload)
        _write_markdown(root_dir / "ladder_summary.md", summary_payload)


if __name__ == "__main__":
    main()
