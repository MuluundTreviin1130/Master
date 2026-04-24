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
from Technical_model.technologies.buildings.calibration.fit_reduced_order import (
    _load_teacher_bundle_index,
    fit_reduced_order_for_cohort,
    write_reduced_order_fit_result,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fit reduced-order building parameters from existing EnergyPlus teacher runs."
    )
    parser.add_argument(
        "--cohort-id",
        type=str,
        default=None,
        help="Optional single cohort_id. Without this all cohorts from teacher_inputs_v1.json are fitted.",
    )
    parser.add_argument(
        "--reference-experiment-id",
        type=str,
        default=None,
        help="Reference experiment id. Defaults to the building-calibration SSOT.",
    )
    parser.add_argument(
        "--free-float-experiment-id",
        type=str,
        default=None,
        help="Free-float experiment id. Defaults to the building-calibration SSOT.",
    )
    args = parser.parse_args()

    bundle_index = _load_teacher_bundle_index()
    cohort_ids = [str(args.cohort_id)] if args.cohort_id else sorted(bundle_index.keys())
    results = []
    written_paths = []
    for cohort_id in cohort_ids:
        result = fit_reduced_order_for_cohort(
            cohort_id=cohort_id,
            reference_experiment_id=args.reference_experiment_id,
            free_float_experiment_id=args.free_float_experiment_id,
        )
        written_paths.append(write_reduced_order_fit_result(result))
        results.append(result.to_dict())

    cfg = make_building_calibration_config()
    summary_dir = Path(cfg.reduced_order_fit_output_dir).resolve()
    summary_dir.mkdir(parents=True, exist_ok=True)
    summary_csv_path = summary_dir / str(cfg.reduced_order_fit_summary_csv)
    summary_json_path = summary_dir / str(cfg.reduced_order_fit_summary_json)
    pd.DataFrame(results).to_csv(summary_csv_path, index=False, encoding="utf-8")
    summary_json_path.write_text(json.dumps(results, indent=2), encoding="utf-8")

    print(f"[building_calibration.fit_reduced_order] cohorts     : {len(results)}")
    print(f"[building_calibration.fit_reduced_order] summary csv : {summary_csv_path}")
    print(f"[building_calibration.fit_reduced_order] summary json: {summary_json_path}")
    for path in written_paths:
        print(f"[building_calibration.fit_reduced_order] fit        : {path}")


if __name__ == "__main__":
    main()
