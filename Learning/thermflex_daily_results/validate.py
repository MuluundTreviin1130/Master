from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
from sklearn.model_selection import GroupShuffleSplit
from sklearn.model_selection import StratifiedShuffleSplit


@dataclass(frozen=True)
class SplitResult:
    train_index: list[int]
    test_index: list[int]
    group_column: str
    train_groups: list[str]
    test_groups: list[str]
    split_strategy: str = "group_shuffle"
    stratify_column: str | None = None


def build_grouped_holdout_split(
    *,
    truth_df: pd.DataFrame,
    group_column: str = "split_group_bundle",
    test_size: float = 0.34,
    random_state: int = 42,
    split_strategy: str = "group_shuffle",
    stratify_column: str | None = None,
) -> SplitResult:
    """Build one grouped holdout split for the curated ThermFlex day dataset."""

    strategy = str(split_strategy).strip().lower()
    if group_column not in truth_df.columns:
        raise ValueError(
            "[thermflex_daily_results] grouped split column missing from truth dataframe: "
            f"{group_column}"
        )
    if truth_df.empty:
        raise ValueError("[thermflex_daily_results] cannot split an empty truth dataframe.")
    groups = truth_df[group_column].astype(str)
    unique_groups = sorted(groups.unique().tolist())
    if len(unique_groups) < 2:
        raise ValueError(
            "[thermflex_daily_results] grouped holdout requires at least two distinct groups in "
            f"{group_column}, got {len(unique_groups)}"
        )
    if strategy == "group_shuffle":
        splitter = GroupShuffleSplit(n_splits=1, test_size=test_size, random_state=random_state)
        train_idx, test_idx = next(splitter.split(truth_df, groups=groups))
    elif strategy == "group_stratified_shuffle":
        train_idx, test_idx = _build_group_stratified_indices(
            truth_df=truth_df,
            group_column=group_column,
            stratify_column=stratify_column,
            test_size=test_size,
            random_state=random_state,
        )
    else:
        raise ValueError(
            "[thermflex_daily_results] unsupported grouped split strategy: "
            f"{split_strategy}"
        )
    train_groups = sorted(groups.iloc[train_idx].unique().tolist())
    test_groups = sorted(groups.iloc[test_idx].unique().tolist())
    return SplitResult(
        train_index=[int(idx) for idx in train_idx],
        test_index=[int(idx) for idx in test_idx],
        group_column=group_column,
        train_groups=train_groups,
        test_groups=test_groups,
        split_strategy=strategy,
        stratify_column=str(stratify_column) if stratify_column is not None else None,
    )


def _build_group_stratified_indices(
    *,
    truth_df: pd.DataFrame,
    group_column: str,
    stratify_column: str | None,
    test_size: float,
    random_state: int,
) -> tuple[list[int], list[int]]:
    """Split whole groups while preserving one explicit group-level stratum."""

    if stratify_column is None:
        raise ValueError(
            "[thermflex_daily_results] group_stratified_shuffle requires an explicit stratify_column."
        )
    stratify_name = str(stratify_column)
    if stratify_name not in truth_df.columns:
        raise ValueError(
            "[thermflex_daily_results] grouped stratified split column missing from truth dataframe: "
            f"{stratify_name}"
        )
    group_frame = _single_row_per_group(
        truth_df=truth_df,
        group_column=group_column,
        stratify_column=stratify_name,
    )
    stratum_counts = group_frame[stratify_name].astype(str).value_counts()
    too_small = stratum_counts.loc[stratum_counts < 2]
    if not too_small.empty:
        raise ValueError(
            "[thermflex_daily_results] grouped stratified split requires at least two groups per stratum; "
            f"too small: {too_small.to_dict()}"
        )
    n_groups = int(len(group_frame))
    n_test = int(round(float(test_size) * n_groups)) if float(test_size) < 1.0 else int(test_size)
    n_test = max(1, min(n_groups - 1, n_test))
    n_strata = int(group_frame[stratify_name].astype(str).nunique())
    if n_test < n_strata or (n_groups - n_test) < n_strata:
        raise ValueError(
            "[thermflex_daily_results] grouped stratified split has too few train/test groups "
            f"for {n_strata} strata: n_groups={n_groups}, n_test={n_test}"
        )
    splitter = StratifiedShuffleSplit(
        n_splits=1,
        test_size=n_test,
        random_state=random_state,
    )
    train_group_pos, test_group_pos = next(
        splitter.split(
            group_frame[[group_column]],
            group_frame[stratify_name].astype(str),
        )
    )
    train_groups = set(group_frame.iloc[train_group_pos][group_column].astype(str))
    test_groups = set(group_frame.iloc[test_group_pos][group_column].astype(str))
    row_groups = truth_df[group_column].astype(str)
    train_idx = truth_df.index[row_groups.isin(train_groups)].astype(int).tolist()
    test_idx = truth_df.index[row_groups.isin(test_groups)].astype(int).tolist()
    return train_idx, test_idx


def _single_row_per_group(
    *,
    truth_df: pd.DataFrame,
    group_column: str,
    stratify_column: str,
) -> pd.DataFrame:
    """Return one group-level stratum row and fail on mixed groups."""

    grouped = truth_df.loc[:, [group_column, stratify_column]].copy()
    grouped[group_column] = grouped[group_column].astype(str)
    grouped[stratify_column] = grouped[stratify_column].astype(str)
    nunique = grouped.groupby(group_column, sort=True)[stratify_column].nunique()
    mixed = nunique.loc[nunique > 1]
    if not mixed.empty:
        raise ValueError(
            "[thermflex_daily_results] grouped stratified split requires one stratum per group; "
            f"mixed groups: {mixed.index.astype(str).tolist()[:5]}"
        )
    return grouped.drop_duplicates(subset=[group_column]).reset_index(drop=True)
