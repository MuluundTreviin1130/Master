from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from Learning.thermflex_daily_results.dataset_builder import collect_unique_screen_tables


class DailyResultsDuplicateBundleSelectionTest(unittest.TestCase):
    def test_more_complete_duplicate_bundle_replaces_earlier_snapshot_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            bundle_name = "daily_thermflex_screen_case_20260513_000000"
            stale_csv = _write_screen_csv(
                tmp_path / "snapshot" / bundle_name / "heating_season_day_screen.csv",
                rows=("2023-01-01,1.0",),
            )
            live_csv = _write_screen_csv(
                tmp_path / "gold" / bundle_name / "heating_season_day_screen.csv",
                rows=("2023-01-01,1.0", "2023-01-02,2.0"),
            )

            selected, skipped = collect_unique_screen_tables(
                source_roots=[stale_csv.parents[1], live_csv.parents[1]]
            )

            self.assertEqual([live_csv.resolve()], selected)
            self.assertEqual(
                "duplicate_bundle_name_replaced_by_more_complete_source",
                skipped[0]["reason"],
            )
            self.assertEqual(str(stale_csv.resolve()), skipped[0]["skipped_screen_csv"])

    def test_equal_rank_duplicate_bundle_with_different_content_fails_fast(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            bundle_name = "daily_thermflex_screen_case_20260513_000000"
            first_csv = _write_screen_csv(
                tmp_path / "snapshot" / bundle_name / "heating_season_day_screen.csv",
                rows=("2023-01-01,1.0",),
            )
            second_csv = _write_screen_csv(
                tmp_path / "gold" / bundle_name / "heating_season_day_screen.csv",
                rows=("2023-01-01,9.0",),
            )

            with self.assertRaisesRegex(ValueError, "conflicting content"):
                collect_unique_screen_tables(source_roots=[first_csv.parents[1], second_csv.parents[1]])


def _write_screen_csv(path: Path, *, rows: tuple[str, ...]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("date,value\n" + "\n".join(rows) + "\n", encoding="utf-8")
    return path


if __name__ == "__main__":
    unittest.main()
