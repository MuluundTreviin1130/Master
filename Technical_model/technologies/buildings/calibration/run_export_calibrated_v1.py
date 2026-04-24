from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Technical_model.technologies.buildings.calibration.export_calibrated_archetypes import (
    build_calibrated_v1_payload,
    write_calibrated_v1_payload,
)


def main() -> None:
    payload = build_calibrated_v1_payload()
    json_path, py_path = write_calibrated_v1_payload(payload)
    print(f"[building_calibration.export_calibrated] json : {json_path}")
    print(f"[building_calibration.export_calibrated] py   : {py_path}")


if __name__ == "__main__":
    main()
