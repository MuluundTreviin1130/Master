from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
from sklearn.model_selection import GroupShuffleSplit


@dataclass(frozen=True)
class SplitResult:
    train_index: list[int]
    test_index: list[int]
    train_groups: list[str]
    test_groups: list[str]


def build_grouped_holdout_split(
    *,
    truth_df: pd.DataFrame,
    group_column: str = "split_group_case",
    test_size: float = 0.25,
    random_state: int = 42,
) -> SplitResult:
    """Create a grouped holdout split without leaking the same case family across train and test."""

    if group_column not in truth_df.columns:
        raise ValueError(f"[thermflex_system_results] missing split group column: {group_column}")
    groups = truth_df[group_column].astype(str).to_numpy()
    distinct_group_count = int(pd.Series(groups).nunique())
    if distinct_group_count < 2:
        raise ValueError(
            "[thermflex_system_results] grouped split requires at least two distinct groups, "
            f"got {distinct_group_count}."
        )
    splitter = GroupShuffleSplit(n_splits=1, test_size=test_size, random_state=random_state)
    train_index, test_index = next(splitter.split(truth_df, groups=groups))
    train_groups = sorted(pd.Series(groups[train_index]).astype(str).unique().tolist())
    test_groups = sorted(pd.Series(groups[test_index]).astype(str).unique().tolist())
    return SplitResult(
        train_index=train_index.tolist(),
        test_index=test_index.tolist(),
        train_groups=train_groups,
        test_groups=test_groups,
    )

