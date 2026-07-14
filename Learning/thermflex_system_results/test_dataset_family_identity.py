from __future__ import annotations

import hashlib
import json
import unittest

import pandas as pd

from Learning.thermflex_system_results.family_identity import (
    build_selected_run_signatures,
)


class SystemResultsFamilyIdentityTest(unittest.TestCase):
    def _family_hash(self, truth: pd.DataFrame) -> str:
        family_spec = {
            "family_name": "thermflex_system_results",
            "selected_run_names": ["20260714_110000_thermflex"],
            "selected_run_signatures": build_selected_run_signatures(truth),
        }
        payload = json.dumps(
            family_spec,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def test_revised_truth_under_same_run_name_changes_family_hash(self) -> None:
        original = pd.DataFrame(
            {
                "source_run_name": ["20260714_110000_thermflex"],
                "signature_hash": ["design-a"],
                "dispatch_cost_eur": [100.0],
            }
        )
        revised = original.copy()
        revised.loc[0, "dispatch_cost_eur"] = 125.0

        self.assertNotEqual(self._family_hash(original), self._family_hash(revised))

    def test_appended_truth_under_same_run_name_changes_family_hash(self) -> None:
        original = pd.DataFrame(
            {
                "source_run_name": ["20260714_110000_thermflex"],
                "signature_hash": ["design-a"],
                "dispatch_cost_eur": [100.0],
            }
        )
        appended = pd.concat(
            [
                original,
                pd.DataFrame(
                    {
                        "source_run_name": ["20260714_110000_thermflex"],
                        "signature_hash": ["design-b"],
                        "dispatch_cost_eur": [90.0],
                    }
                ),
            ],
            ignore_index=True,
        )

        self.assertNotEqual(self._family_hash(original), self._family_hash(appended))

    def test_dataframe_column_order_does_not_change_family_hash(self) -> None:
        truth = pd.DataFrame(
            {
                "source_run_name": ["20260714_110000_thermflex"],
                "signature_hash": ["design-a"],
                "dispatch_cost_eur": [100.0],
            }
        )

        self.assertEqual(
            self._family_hash(truth),
            self._family_hash(truth.loc[:, list(reversed(truth.columns))]),
        )


if __name__ == "__main__":
    unittest.main()
