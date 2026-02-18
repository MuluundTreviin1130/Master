# Optimization/validation/sampling/strategies.py
from __future__ import annotations

from typing import Iterable, Optional
import pandas as pd

from V2H_energy_community_surrogat_datafilenew.datafile_Umstellung.Optimization.framework.Settings.settings import get_settings
from V2H_energy_community_surrogat_datafilenew.datafile_Umstellung.Optimization.validation.sampling.subsets import subset_by_strategy


def _get_subset_cfg(S, which: str):
    """
    Holt aus S.validation.{fast_subset, gold_subset} die Parameter:
      - strategy
      - k_total
      - random_seed aus S.validation.random_seed
    """
    V = getattr(S, "validation", None)
    if V is None:
        return "all", None, None

    if which == "fast":
        cfg = getattr(V, "fast_subset", None)
    elif which == "gold":
        cfg = getattr(V, "gold_subset", None)
    else:
        raise ValueError(f"[sampling] unknown subset label: {which}")

    strategy = getattr(cfg, "strategy", "all") if cfg is not None else "all"
    k_total = getattr(cfg, "k_total", None) if cfg is not None else None
    seed = getattr(V, "random_seed", None)
    return strategy, k_total, seed


def select_subset(
    X: pd.DataFrame,
    which: str,
    xschema_names: Optional[Iterable[str]] = None,
) -> pd.DataFrame:
    """
    Wählt ein Subset der Zeilen gem. zentralem Settings:
      validation.fast_subset / validation.gold_subset

    Parameter in Settings:
      - validation.fast_subset.strategy / k_total
      - validation.gold_subset.strategy / k_total
      - validation.random_seed

    which ∈ {"fast", "gold"}.
    """
    S = get_settings()
    strategy, k_total, seed = _get_subset_cfg(S, which)

    if k_total is None:
        # default: alles
        return X

    xschema = list(xschema_names) if xschema_names is not None else list(
        getattr(getattr(S, "bounds", None), "names", X.columns.to_list())
    )

    return subset_by_strategy(
        X,
        strategy=strategy,
        k_total=k_total,
        seed=seed,
        xschema_names=xschema,
    )
