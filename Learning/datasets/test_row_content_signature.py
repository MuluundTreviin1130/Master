from __future__ import annotations

import hashlib
import json
import unittest

import pandas as pd

from Learning.datasets.row_content_signature import (
    build_selected_bundle_content_signatures,
    normalized_rows_sha256,
)


class RowContentSignatureTest(unittest.TestCase):
    def _family_hash(self, signatures: list[dict]) -> str:
        # Mirror the curated exporters: family identity is a stable JSON hash of
        # the selected-bundle signature list, so revised cells must change it.
        payload = json.dumps(
            {"selected_bundle_signatures": signatures},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def test_revised_numeric_cell_changes_digest(self) -> None:
        original = pd.DataFrame(
            {
                "source_bundle_name": ["bundle_a", "bundle_a"],
                "timestamp": ["2024-01-01T00:00:00", "2024-01-01T01:00:00"],
                "target_kwh": [10.0, 11.0],
            }
        )
        revised = original.copy()
        revised.loc[1, "target_kwh"] = 12.5

        self.assertNotEqual(
            normalized_rows_sha256(original),
            normalized_rows_sha256(revised),
        )
        self.assertNotEqual(
            self._family_hash(build_selected_bundle_content_signatures(original)),
            self._family_hash(build_selected_bundle_content_signatures(revised)),
        )

    def test_appended_row_changes_digest(self) -> None:
        original = pd.DataFrame(
            {
                "source_bundle_name": ["bundle_a"],
                "timestamp": ["2024-01-01T00:00:00"],
                "target_kwh": [10.0],
            }
        )
        appended = pd.concat(
            [
                original,
                pd.DataFrame(
                    {
                        "source_bundle_name": ["bundle_a"],
                        "timestamp": ["2024-01-01T01:00:00"],
                        "target_kwh": [11.0],
                    }
                ),
            ],
            ignore_index=True,
        )

        self.assertNotEqual(
            self._family_hash(build_selected_bundle_content_signatures(original)),
            self._family_hash(build_selected_bundle_content_signatures(appended)),
        )

    def test_column_order_does_not_change_digest(self) -> None:
        frame = pd.DataFrame(
            {
                "source_bundle_name": ["bundle_a"],
                "timestamp": ["2024-01-01T00:00:00"],
                "target_kwh": [10.0],
            }
        )
        reordered = frame.loc[:, list(reversed(frame.columns))]

        self.assertEqual(normalized_rows_sha256(frame), normalized_rows_sha256(reordered))
        self.assertEqual(
            self._family_hash(build_selected_bundle_content_signatures(frame)),
            self._family_hash(build_selected_bundle_content_signatures(reordered)),
        )


if __name__ == "__main__":
    unittest.main()
