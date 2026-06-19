from __future__ import annotations

import unittest

from Learning.training.targets import resolve_target_values


class ResolveTargetValuesTest(unittest.TestCase):
    def test_objectives_take_precedence_over_raw_flows(self) -> None:
        values = resolve_target_values(
            targets=["npc_eur", "E_import_grid_kWh"],
            objectives={"npc_eur": 12.5},
            flows_L={"npc_eur": 99.0, "E_import_grid_kWh": 7.0},
        )

        self.assertEqual(values, [12.5, 7.0])

    def test_missing_required_target_raises_instead_of_zero_label(self) -> None:
        with self.assertRaisesRegex(KeyError, "missing required target"):
            resolve_target_values(
                targets=["dh_total_peak_change_kw"],
                objectives={},
                flows_L={"E_import_grid_kWh": 7.0},
            )


if __name__ == "__main__":
    unittest.main()
