from __future__ import annotations

"""Surrogate model factory/registry.

Per-target model mixing is intentionally not implemented yet; this factory
returns one model instance per target with shared model type.
"""

from typing import Any, Dict

from sklearn.ensemble import RandomForestRegressor
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import RBF, ConstantKernel


def make_model(model_name: str, model_params: Dict[str, Any], random_state: int):
    name = str(model_name).lower().strip()
    params = dict(model_params or {})
    if name == "rf":
        params.setdefault("n_estimators", 300)
        params.setdefault("n_jobs", -1)
        params.setdefault("random_state", random_state)
        return RandomForestRegressor(**params)
    if name == "gpr":
        params.setdefault("kernel", ConstantKernel(1.0) * RBF(length_scale=1.0))
        params.setdefault("random_state", random_state)
        return GaussianProcessRegressor(**params)
    if name == "xgb":
        try:
            from xgboost import XGBRegressor
        except Exception as exc:
            raise RuntimeError("[surrogate] model='xgb' requires xgboost installed.") from exc
        params.setdefault("n_estimators", 300)
        params.setdefault("objective", "reg:squarederror")
        params.setdefault("tree_method", "hist")
        params.setdefault("max_depth", 6)
        params.setdefault("learning_rate", 0.05)
        params.setdefault("subsample", 0.8)
        params.setdefault("colsample_bytree", 0.8)
        params.setdefault("random_state", random_state)
        params.setdefault("n_jobs", -1)
        return XGBRegressor(**params)
    raise ValueError(f"[surrogate] Unknown model '{model_name}'. Supported: rf, gpr, xgb.")
