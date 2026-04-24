from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, List

import numpy as np
import pandas as pd
from sklearn.neighbors import KNeighborsClassifier

from Learning.datasets.load_dataset import load_dataset
from Learning.families.build_family import build_family


def _design_row_key(row: np.ndarray) -> tuple[float, ...]:
    arr = np.asarray(row, dtype=float).reshape(-1)
    return tuple(np.round(arr, 8).tolist())


@dataclass
class SurrogateFeasibilityScreen:
    """Explicit surrogate-only feasibility screen built from audited truth data.

    The screen is intentionally narrow:
    - it uses the active surrogate family dataset as SSOT,
    - it predicts *feasible probability* from labeled feasible/infeasible points,
    - it returns a single constraint value `min_feasible_probability - p_feasible`,
      so `g(x) <= 0` means "screen accepts this candidate".

    This is not a hidden fallback or a penalty hack. The calling optimization
    override must explicitly declare the corresponding constraint name.
    """

    constraint_name: str
    min_feasible_probability: float
    neighbors: int
    family_hash: str
    bounds_names: List[str]
    lower: np.ndarray
    span: np.ndarray
    classifier: KNeighborsClassifier
    exact_feasible_keys: set[tuple[float, ...]]
    exact_infeasible_keys: set[tuple[float, ...]]
    n_feasible: int
    n_infeasible: int

    def _normalize(self, X: np.ndarray) -> np.ndarray:
        X = np.asarray(X, dtype=float)
        return (X - self.lower) / self.span

    def feasible_probability(self, X: np.ndarray) -> np.ndarray:
        X = np.asarray(X, dtype=float)
        if X.ndim == 1:
            X = X.reshape(1, -1)
        probs = self.classifier.predict_proba(self._normalize(X))[:, 1]
        for i in range(X.shape[0]):
            row_key = _design_row_key(X[i, :])
            if row_key in self.exact_feasible_keys:
                probs[i] = 1.0
            elif row_key in self.exact_infeasible_keys:
                probs[i] = 0.0
        return probs

    def constraint_values(self, X: np.ndarray) -> np.ndarray:
        probs = self.feasible_probability(X)
        return np.asarray(self.min_feasible_probability - probs, dtype=float).reshape(-1, 1)


def _require_columns(frame: pd.DataFrame, names: Iterable[str], *, label: str) -> None:
    missing = [str(name) for name in names if str(name) not in frame.columns]
    if missing:
        raise KeyError(
            f"[surrogate_feasibility_screen] {label} is missing required bound columns: "
            + ", ".join(missing)
        )


def build_surrogate_feasibility_screen(settings: Any) -> SurrogateFeasibilityScreen | None:
    train_cfg = getattr(settings, "surrogate_train", None)
    enabled = bool(getattr(train_cfg, "feasibility_screen_enabled", False))
    if not enabled:
        return None

    bounds_names = list(getattr(getattr(settings, "bounds", None), "names", []) or [])
    if not bounds_names:
        raise ValueError("[surrogate_feasibility_screen] settings.bounds.names is empty.")

    family_spec = build_family(settings)
    family_hash = str(family_spec.family_hash)
    learning_cfg = getattr(settings, "learning", None)
    dataset_root = str(getattr(learning_cfg, "active_dataset_root", "Learning/datasets"))
    dataset = load_dataset(dataset_root, family_hash)
    if dataset is None:
        raise FileNotFoundError(
            f"[surrogate_feasibility_screen] No active family dataset found for family_hash='{family_hash}'."
        )

    failed_path = dataset.get("teacher_eval_failed_path")
    if failed_path is None or not failed_path.exists():
        raise FileNotFoundError(
            "[surrogate_feasibility_screen] teacher_eval/infeasible_points.csv is missing for the active family dataset."
        )

    feasible_X = np.asarray(dataset["X_design"], dtype=float)
    if feasible_X.ndim != 2 or feasible_X.shape[1] != len(bounds_names):
        raise ValueError(
            "[surrogate_feasibility_screen] Existing feasible design matrix does not match active bounds schema."
        )

    failed_df = pd.read_csv(failed_path)
    _require_columns(failed_df, bounds_names, label="teacher_eval/infeasible_points.csv")
    infeasible_X = failed_df[bounds_names].to_numpy(dtype=float)

    min_labeled_samples = int(getattr(train_cfg, "feasibility_screen_min_labeled_samples", 24))
    min_infeasible_samples = int(getattr(train_cfg, "feasibility_screen_min_infeasible_samples", 8))
    if feasible_X.shape[0] + infeasible_X.shape[0] < min_labeled_samples:
        raise RuntimeError(
            "[surrogate_feasibility_screen] Too few labeled samples for explicit feasibility screen: "
            f"{feasible_X.shape[0] + infeasible_X.shape[0]} < {min_labeled_samples}."
        )
    if infeasible_X.shape[0] < min_infeasible_samples:
        raise RuntimeError(
            "[surrogate_feasibility_screen] Too few audited infeasible samples for explicit feasibility screen: "
            f"{infeasible_X.shape[0]} < {min_infeasible_samples}."
        )

    X_labeled = np.vstack([feasible_X, infeasible_X])
    y_labeled = np.concatenate(
        [
            np.ones(feasible_X.shape[0], dtype=int),
            np.zeros(infeasible_X.shape[0], dtype=int),
        ]
    )

    lower = np.asarray(getattr(settings.bounds, "lower", []) or [], dtype=float)
    upper = np.asarray(getattr(settings.bounds, "upper", []) or [], dtype=float)
    if lower.shape[0] != len(bounds_names) or upper.shape[0] != len(bounds_names):
        raise ValueError("[surrogate_feasibility_screen] Bounds lower/upper do not match bounds.names.")
    span = upper - lower
    span = np.where(span > 0.0, span, 1.0)

    neighbors = int(getattr(train_cfg, "feasibility_screen_neighbors", 9))
    if neighbors <= 0:
        raise ValueError(
            f"[surrogate_feasibility_screen] feasibility_screen_neighbors must be > 0, got {neighbors}."
        )
    neighbors = min(neighbors, int(X_labeled.shape[0]))

    classifier = KNeighborsClassifier(n_neighbors=neighbors, weights="distance")
    classifier.fit((X_labeled - lower) / span, y_labeled)

    threshold = float(getattr(train_cfg, "feasibility_screen_min_feasible_probability", 0.60))
    if not (0.0 < threshold <= 1.0):
        raise ValueError(
            "[surrogate_feasibility_screen] feasibility_screen_min_feasible_probability must be in (0, 1]."
        )

    exact_feasible_keys = {_design_row_key(row) for row in feasible_X}
    exact_infeasible_keys = {_design_row_key(row) for row in infeasible_X}
    overlap = exact_feasible_keys.intersection(exact_infeasible_keys)
    if overlap:
        raise RuntimeError(
            "[surrogate_feasibility_screen] Active family dataset contains contradictory exact labels."
        )

    return SurrogateFeasibilityScreen(
        constraint_name=str(
            getattr(train_cfg, "feasibility_screen_constraint_name", "surrogate_feasible_probability_guard")
        ),
        min_feasible_probability=threshold,
        neighbors=neighbors,
        family_hash=family_hash,
        bounds_names=list(bounds_names),
        lower=lower,
        span=span,
        classifier=classifier,
        exact_feasible_keys=exact_feasible_keys,
        exact_infeasible_keys=exact_infeasible_keys,
        n_feasible=int(feasible_X.shape[0]),
        n_infeasible=int(infeasible_X.shape[0]),
    )
