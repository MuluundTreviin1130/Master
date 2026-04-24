from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Settings.technical.building_calibration import make_building_calibration_config
from Technical_model.technologies.buildings.calibration.experiments import build_experiment_library
from Technical_model.technologies.buildings.calibration.from_repo import build_teacher_input_bundle


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepare offline building-calibration teacher inputs and experiment library from repo SSOT data."
    )
    args = parser.parse_args()
    _ = args

    cfg = make_building_calibration_config()
    out_dir = Path(cfg.teacher_setup_output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    teacher_bundle = build_teacher_input_bundle()
    experiment_library = build_experiment_library()

    teacher_path = Path(cfg.teacher_input_output_json).resolve()
    experiment_path = Path(cfg.experiment_library_output_json).resolve()

    teacher_path.write_text(json.dumps(teacher_bundle.to_dict(), indent=2), encoding="utf-8")
    experiment_path.write_text(json.dumps(experiment_library.to_dict(), indent=2), encoding="utf-8")

    print(f"[building_calibration_setup] teacher_inputs : {teacher_path}")
    print(f"[building_calibration_setup] cohorts        : {len(teacher_bundle.cohorts)}")
    print(f"[building_calibration_setup] experiments    : {len(experiment_library.experiments)}")
    print(f"[building_calibration_setup] experiment_lib : {experiment_path}")


if __name__ == "__main__":
    main()
