from __future__ import annotations

import unittest

import pandas as pd

from Learning.thermflex_daily_results.schema import (
    HEAT_COST_TOTAL_CO2_ABSOLUTE_TARGET_COLUMNS,
    OPTIONAL_DISPATCH_ECONOMICS_TARGET_COLUMNS,
    TABLE_09_PAPER_TARGET_COLUMNS,
    TARGET_COLUMNS,
)
from Learning.thermflex_daily_results.target_completeness import require_complete_requested_targets


class DailyResultsTargetCompletenessTests(unittest.TestCase):
    def test_heat_cost_profile_fails_when_optional_column_is_nan(self) -> None:
        """
        Concrete trigger: historic daily screens omit heat-boundary economics.

        The dataset builder fills missing optional targets with NaN. Training
        with `heat_cost_total_co2_absolute` must not silently drop the NaN
        cost target and still register under that profile name.
        """

        truth_df = pd.DataFrame(
            {
                "dispatch_heat_operating_cost_eur_delta": [1.0, float("nan"), 3.0],
                "co2_emissions_total_t_delta": [0.1, 0.2, 0.3],
            }
        )

        with self.assertRaisesRegex(ValueError, "incomplete truth targets"):
            require_complete_requested_targets(
                truth_df=truth_df,
                requested_target_names=list(HEAT_COST_TOTAL_CO2_ABSOLUTE_TARGET_COLUMNS),
                target_profile="heat_cost_total_co2_absolute",
            )

    def test_all_profile_fails_when_optional_economics_are_nan(self) -> None:
        truth_df = pd.DataFrame({target: [0.0, 1.0] for target in TARGET_COLUMNS})
        for column in OPTIONAL_DISPATCH_ECONOMICS_TARGET_COLUMNS:
            truth_df[column] = float("nan")

        with self.assertRaisesRegex(
            ValueError,
            "dispatch_heat_operating_cost_eur_delta",
        ):
            require_complete_requested_targets(
                truth_df=truth_df,
                requested_target_names=list(TARGET_COLUMNS),
                target_profile="all",
            )

    def test_complete_table_09_profile_passes(self) -> None:
        truth_df = pd.DataFrame(
            {target: [0.0, 1.0, 2.0] for target in TABLE_09_PAPER_TARGET_COLUMNS}
        )

        require_complete_requested_targets(
            truth_df=truth_df,
            requested_target_names=list(TABLE_09_PAPER_TARGET_COLUMNS),
            target_profile="table_09_paper",
        )


if __name__ == "__main__":
    unittest.main()
