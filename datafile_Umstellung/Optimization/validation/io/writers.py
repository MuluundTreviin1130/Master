# Optimization/validation/io/writers.py
from __future__ import annotations

from pathlib import Path
from typing import Dict, Any
import json
import pandas as pd


def ensure_out_dir(base, run_id: str, timestamping: bool = True) -> Path:
    """
    Erzeugt:
      <base>/<run_id>/<timestamp>/validation
    """
    from datetime import datetime

    base = Path(base)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S") if timestamping else "latest"
    p = base / run_id / stamp / "validation"
    p.mkdir(parents=True, exist_ok=True)
    return p


def save_audit(out_root: Path, audit: Dict[str, Any]) -> Path:
    p = out_root / "audit" / "audit.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(audit, indent=2), encoding="utf-8")
    print(f"[validation][reports] saved audit → {p}")
    return p


def save_probes(out_root: Path, probes: Dict[str, Any]) -> Path:
    """
    Speichert Probes (z.B. Designpunkte X) unter probes/.
    DataFrames → CSV, sonst JSON.
    """
    root = out_root / "probes"
    root.mkdir(parents=True, exist_ok=True)

    for name, obj in probes.items():
        if isinstance(obj, pd.DataFrame):
            p = root / f"{name}.csv"
            obj.to_csv(p, index=False)
        else:
            p = root / f"{name}.json"
            p.write_text(json.dumps(obj, indent=2), encoding="utf-8")
    print(f"[validation][reports] saved probes → {root}")
    return root


def save_predictions(out_root: Path, df: pd.DataFrame) -> Path:
    p = out_root / "predictions" / "predictions.csv"
    p.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(p, index=False)
    print(f"[validation][reports] saved predictions → {p}")
    return p


def save_metrics(out_root: Path, label: str, metrics) -> Path:
    root = out_root / "metrics"
    root.mkdir(parents=True, exist_ok=True)
    p = root / f"{label}.csv"

    if isinstance(metrics, pd.DataFrame):
        metrics.to_csv(p, index=True)
    elif isinstance(metrics, dict):
        df = pd.DataFrame([metrics])
        df.to_csv(p, index=False)
    else:
        raise TypeError(f"Unsupported metrics type: {type(metrics)}")

    print(f"[validation][reports] saved metrics → {p}")
    return p


def save_report(out_root: Path, content: str) -> Path:
    p = out_root / "report.txt"
    p.write_text(content, encoding="utf-8")
    print(f"[validation][reports] saved report → {p}")
    return p


def save_report_md(out_root: Path, content: str) -> Path:
    p = out_root / "report.md"
    p.write_text(content, encoding="utf-8")
    print(f"[validation][reports] saved report → {p}")
    return p
