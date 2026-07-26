from __future__ import annotations

import pandas as pd


def require_complete_requested_targets(
    *,
    truth_df: pd.DataFrame,
    requested_target_names: list[str],
    target_profile: str,
) -> None:
    """
    Fail when any requested profile target is missing or contains NaN.

    Historic screens may omit optional dispatch-economics columns; the dataset
    builder stores those as NaN. Callers must choose a profile that only asks
    for fully populated targets instead of silently training a subset.
    """

    missing_columns = [target for target in requested_target_names if target not in truth_df.columns]
    if missing_columns:
        raise ValueError(
            "[thermflex_daily_results] requested target profile is missing truth columns: "
            + ", ".join(missing_columns)
        )
    incomplete_targets = [
        target for target in requested_target_names if truth_df[target].isna().any()
    ]
    if incomplete_targets:
        raise ValueError(
            "[thermflex_daily_results] requested target profile "
            f"'{target_profile}' has incomplete truth targets (NaN present): "
            + ", ".join(incomplete_targets)
            + ". Choose a narrower profile whose targets are fully populated, "
            "or export truth that includes those columns."
        )
