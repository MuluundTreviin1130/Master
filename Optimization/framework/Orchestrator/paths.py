# Optimization/framework/Orchestrator/paths.py
from pathlib import Path
from datetime import datetime


def make_run_dir(output_root: str, tag: str, location: str, system_id: str, engine_name: str) -> str:
    """
    Build run directory at project root.
    Structure: <project_root>/<output_root>/<Location>/<Engine>/<timestamp>_<tag>
    """
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    # project_root is one level above ".../Optimization"
    project_root = Path(__file__).resolve().parents[4]
    base = (project_root / output_root).resolve()
    d = base / location / engine_name / f"{ts}_{tag}"
    return str(d)
