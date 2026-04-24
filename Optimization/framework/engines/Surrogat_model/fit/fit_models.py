# Optimization/framework/engines/Surrogat_model/fit/fit_models.py
from __future__ import annotations

from typing import Any, Dict, List

import numpy as np
from tqdm import tqdm

from Optimization.framework.engines.Surrogat_model.fit.model_factory import make_model


def fit_models_per_column(
    X: np.ndarray,
    Y: np.ndarray | None,
    *,
    model_name: str,
    model_params: Dict[str, Any],
    seed: int,
) -> List[Any]:
    """
    Trainiert pro Zielspalte ein Modell aus der zentralen Modellfabrik.
    """
    if Y is None or (hasattr(Y, "shape") and Y.shape[1] == 0):
        return []

    models: List[Any] = []
    n_cols = int(Y.shape[1])
    desc = f"{str(model_name).upper()} fit (targets)"

    with tqdm(total=n_cols, desc=desc, unit="model") as pbar:
        for j in range(n_cols):
            y = Y[:, j]
            model = make_model(str(model_name), dict(model_params or {}), random_state=int(seed))
            model.fit(X, y)
            models.append(model)
            pbar.update(1)

    return models


def fit_random_forest_per_column(
    X: np.ndarray,
    Y: np.ndarray | None,
    n_estimators: int,
    n_jobs: int,
    seed: int,
) -> List[Any]:
    """
    Legacy-Wrapper fuer bestehende RF-Aufrufer.
    """
    return fit_models_per_column(
        X,
        Y,
        model_name="rf",
        model_params={
            "n_estimators": int(n_estimators),
            "n_jobs": int(n_jobs),
        },
        seed=int(seed),
    )
