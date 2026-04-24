from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Technical_model.technologies.buildings.calibration.teachers.energyplus import (
    run_energyplus_teacher_experiment,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run one pilot EnergyPlus teacher experiment for a selected Vienna cohort and calibration experiment."
    )
    parser.add_argument("--cohort-id", type=str, default=None, help="Teacher cohort_id from teacher_inputs_v1.json.")
    parser.add_argument(
        "--experiment-id",
        type=str,
        default=None,
        help="Experiment id from experiment_library_v1.json.",
    )
    parser.add_argument(
        "--dh-share",
        type=float,
        default=None,
        help="Optional explicit DH-connected share for bus-scaled plausibility metrics. Without this no DH scaling is applied unless the cohort provides an override.",
    )
    args = parser.parse_args()
    result = run_energyplus_teacher_experiment(
        cohort_id=args.cohort_id,
        experiment_id=args.experiment_id,
        dh_connected_share=args.dh_share,
    )
    print(f"[energyplus_teacher] cohort   : {result.cohort_id}")
    print(f"[energyplus_teacher] experiment: {result.experiment_id}")
    print(f"[energyplus_teacher] workdir   : {result.workdir}")
    print(f"[energyplus_teacher] hourly    : {result.hourly_csv_path}")
    if result.plausibility_hourly_csv_path is not None:
        print(f"[energyplus_teacher] plaus csv : {result.plausibility_hourly_csv_path}")
    if result.plausibility_summary_path is not None:
        print(f"[energyplus_teacher] plaus sum : {result.plausibility_summary_path}")
    if result.plausibility_plot_path is not None:
        print(f"[energyplus_teacher] plaus plot: {result.plausibility_plot_path}")


if __name__ == "__main__":
    main()
