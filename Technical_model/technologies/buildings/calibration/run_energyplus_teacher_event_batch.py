from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Settings.technical.building_calibration import make_building_calibration_config
from Technical_model.technologies.buildings.calibration.run_energyplus_teacher_plausibility_batch import (
    _load_json,
    _resolve_cohort_ids,
)
from Technical_model.technologies.buildings.calibration.teachers.energyplus import (
    run_energyplus_teacher_experiment,
)


def _resolve_event_experiment_ids(requested: list[str] | None) -> list[str]:
    cfg = make_building_calibration_config()
    experiment_library = _load_json(cfg.experiment_library_output_json, label="experiment_library_output_json")
    available = [str(item["experiment_id"]) for item in experiment_library.get("experiments", [])]
    if not available:
        raise RuntimeError("[energyplus_teacher_event_batch] No experiments found in experiment library.")
    if not requested:
        requested = list(cfg.teacher_event_batch_default_experiments)
    missing = [experiment_id for experiment_id in requested if experiment_id not in available]
    if missing:
        raise KeyError(f"[energyplus_teacher_event_batch] Unknown experiment_ids requested: {missing}")
    return requested


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run EnergyPlus teacher event batch over selected cohorts and event experiments."
    )
    parser.add_argument(
        "--cohort-id",
        dest="cohort_ids",
        action="append",
        default=None,
        help="Optional repeated cohort_id. Without this, all cohorts from teacher_inputs_v1.json are used.",
    )
    parser.add_argument(
        "--experiment-id",
        dest="experiment_ids",
        action="append",
        default=None,
        help="Optional repeated event experiment_id. Without this, the SSOT event defaults are used.",
    )
    parser.add_argument(
        "--dh-share",
        dest="dh_share",
        type=float,
        default=None,
        help="Optional explicit DH-connected share for bus-scaled plausibility metrics.",
    )
    args = parser.parse_args()

    cfg = make_building_calibration_config()
    cohort_ids = _resolve_cohort_ids(args.cohort_ids)
    experiment_ids = _resolve_event_experiment_ids(args.experiment_ids)

    rows: list[dict] = []
    for cohort_id in cohort_ids:
        for experiment_id in experiment_ids:
            result = run_energyplus_teacher_experiment(
                cohort_id=cohort_id,
                experiment_id=experiment_id,
                dh_connected_share=args.dh_share,
            )
            meta = json.loads(result.meta_path.read_text(encoding="utf-8"))
            rows.append(
                {
                    "cohort_id": cohort_id,
                    "experiment_id": experiment_id,
                    "control_mode": str(meta["control_mode"]),
                    "hourly_csv_path": str(meta["hourly_csv_path"]),
                    "plausibility_hourly_csv_path": str(meta["plausibility_hourly_csv_path"]),
                    "plausibility_summary_path": str(meta["plausibility_summary_path"]),
                    "plausibility_plot_path": str(meta["plausibility_plot_path"]),
                    "meta_path": str(result.meta_path),
                }
            )
            print(
                f"[energyplus_teacher_event_batch] done cohort={cohort_id} experiment={experiment_id}",
                flush=True,
            )

    out_dir = Path(cfg.teacher_event_batch_output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / str(cfg.teacher_event_batch_summary_csv)
    json_path = out_dir / str(cfg.teacher_event_batch_summary_json)
    df = pd.DataFrame(rows)
    df.to_csv(csv_path, index=False, encoding="utf-8")
    json_path.write_text(
        json.dumps(
            {
                "cohort_ids": cohort_ids,
                "experiment_ids": experiment_ids,
                "dh_share_argument": args.dh_share,
                "n_runs": len(rows),
                "summary_csv_path": str(csv_path),
                "rows": rows,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"[energyplus_teacher_event_batch] summary csv : {csv_path}", flush=True)
    print(f"[energyplus_teacher_event_batch] summary json: {json_path}", flush=True)


if __name__ == "__main__":
    main()
