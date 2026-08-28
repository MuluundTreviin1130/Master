from __future__ import annotations

from pathlib import Path


RUNNERS_DIR = Path(__file__).resolve().parent
FIGURES_DIR = RUNNERS_DIR.parent
PAPER_DIR = FIGURES_DIR.parent
PROJECT_ROOT = PAPER_DIR.parents[2]

PNG_DIR = FIGURES_DIR / "png"
CSV_DIR = FIGURES_DIR / "csv"


def ensure_output_dirs() -> None:
    PNG_DIR.mkdir(parents=True, exist_ok=True)
    CSV_DIR.mkdir(parents=True, exist_ok=True)
