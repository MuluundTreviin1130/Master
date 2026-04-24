from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Technical_model.technologies.buildings.calibration.teachers.energyplus import (
    run_energyplus_mini_smoke,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a tiny EnergyPlus smoke test on one selected Vienna pseudo-EPW.")
    parser.add_argument("--role", type=str, default=None, help="One of average_year, cold_year, mild_year.")
    args = parser.parse_args()
    result = run_energyplus_mini_smoke(role=args.role)
    print(f"[energyplus_smoke] teacher : {result.teacher}")
    print(f"[energyplus_smoke] epw     : {result.epw_path}")
    print(f"[energyplus_smoke] workdir : {result.workdir}")


if __name__ == "__main__":
    main()
