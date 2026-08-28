"""Explicit paths used by Vienna EnergyPlus teacher preparation."""

from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
TEACHER_DATASET = (
    REPOSITORY_ROOT
    / "Learning"
    / "datasets"
    / "vienna_building_energyplus_teacher"
)
PAPER_MODEL_REVIEW = (
    REPOSITORY_ROOT
    / "Documentation"
    / "Papers"
    / "Vienna_2040_Multi_Energy_System_Design"
    / "Results"
    / "Model_Review"
)

