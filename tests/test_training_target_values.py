from __future__ import annotations

import unittest

from Learning.training.target_values import resolve_teacher_target_row


class ResolveTeacherTargetRowTests(unittest.TestCase):
    def test_uses_objectives_and_exported_flows(self) -> None:
        row = resolve_teacher_target_row(
            ["npc_eur", "E_import_grid_kWh", "explicit_zero_flow"],
            {"npc_eur": 12.5},
            {"E_import_grid_kWh": 34.0, "explicit_zero_flow": 0.0},
        )

        self.assertEqual(row, [12.5, 34.0, 0.0])

    def test_missing_target_fails_instead_of_inventing_zero(self) -> None:
        with self.assertRaisesRegex(KeyError, "missing_target"):
            resolve_teacher_target_row(
                ["npc_eur", "missing_target"],
                {"npc_eur": 12.5},
                {"E_import_grid_kWh": 34.0},
            )


if __name__ == "__main__":
    unittest.main()
