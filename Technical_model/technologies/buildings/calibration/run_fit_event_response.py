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
from Technical_model.technologies.buildings.calibration.fit_event_response import (
    fit_event_response_for_cohort,
    write_event_response_fit_result,
)
from Technical_model.technologies.buildings.calibration.fit_reduced_order import _load_teacher_bundle_index


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fit event response metrics from existing EnergyPlus teacher event runs."
    )
    parser.add_argument(
        "--cohort-id",
        type=str,
        default=None,
        help="Optional single cohort_id. Without this all cohorts from teacher_inputs_v1.json are fitted.",
    )
    args = parser.parse_args()

    bundle_index = _load_teacher_bundle_index()
    cohort_ids = [str(args.cohort_id)] if args.cohort_id else sorted(bundle_index.keys())

    results = []
    written_paths = []
    for cohort_id in cohort_ids:
        result = fit_event_response_for_cohort(cohort_id)
        written_paths.append(write_event_response_fit_result(result))
        results.append(result.to_dict())

    cfg = make_building_calibration_config()
    summary_dir = Path(cfg.event_response_fit_output_dir).resolve()
    summary_dir.mkdir(parents=True, exist_ok=True)
    summary_csv_path = summary_dir / str(cfg.event_response_fit_summary_csv)
    summary_json_path = summary_dir / str(cfg.event_response_fit_summary_json)
    pd.DataFrame(results).to_csv(summary_csv_path, index=False, encoding="utf-8")
    summary_json_path.write_text(json.dumps(results, indent=2), encoding="utf-8")

    print(f"[building_calibration.fit_event_response] cohorts     : {len(results)}")
    print(f"[building_calibration.fit_event_response] summary csv : {summary_csv_path}")
    print(f"[building_calibration.fit_event_response] summary json: {summary_json_path}")
    for path in written_paths:
        print(f"[building_calibration.fit_event_response] fit        : {path}")


if __name__ == "__main__":
    main()
