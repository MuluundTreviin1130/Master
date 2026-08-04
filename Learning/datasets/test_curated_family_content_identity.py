from __future__ import annotations

import hashlib
import json
import unittest
from unittest import mock

import pandas as pd

from Learning.thermflex_daily_results.dataset_builder import _selected_bundle_signatures
from Learning.thermflex_hourly_dispatch.dataset_builder import (
    _selected_bundle_signatures as hourly_dispatch_signatures,
)
from Learning.thermflex_hourly_mechanism.dataset_builder import (
    _selected_bundle_signatures as hourly_mechanism_signatures,
)


def _hash_signatures(signatures: list[dict]) -> str:
    payload = json.dumps(
        {"selected_bundle_signatures": signatures},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


class CuratedFamilyContentIdentityTest(unittest.TestCase):
    def test_hourly_mechanism_revised_target_changes_signature_hash(self) -> None:
        original = pd.DataFrame(
            {
                "source_bundle_name": ["mech_bundle"],
                "source_hourly_csv": ["/tmp/mech.csv"],
                "case_label": ["upper_only"],
                "cohort_key": ["cold"],
                "timestamp": [pd.Timestamp("2024-01-01T00:00:00")],
                "heating_kwh": [100.0],
            }
        )
        revised = original.copy()
        revised.loc[0, "heating_kwh"] = 130.0

        self.assertNotEqual(
            _hash_signatures(hourly_mechanism_signatures(original)),
            _hash_signatures(hourly_mechanism_signatures(revised)),
        )

    def test_hourly_dispatch_revised_target_changes_signature_hash(self) -> None:
        original = pd.DataFrame(
            {
                "source_bundle_name": ["dispatch_bundle"],
                "source_hourly_csv": ["/tmp/dispatch.csv"],
                "source_hourly_kind": ["final"],
                "flex_case_label": ["baseline"],
                "flex_override_name": ["none"],
                "date": [pd.Timestamp("2024-01-01")],
                "district_heat_demand_kwh": [50.0],
            }
        )
        revised = original.copy()
        revised.loc[0, "district_heat_demand_kwh"] = 75.0

        self.assertNotEqual(
            _hash_signatures(hourly_dispatch_signatures(original)),
            _hash_signatures(hourly_dispatch_signatures(revised)),
        )

    def test_daily_results_revised_selected_target_changes_signature_hash(self) -> None:
        truth = pd.DataFrame(
            {
                "source_bundle_name": ["daily_bundle"],
                "source_screen_csv": ["/tmp/daily_bundle/heating_season_day_screen.csv"],
                "source_screen_kind": ["final"],
                "source_schema_version": ["v1"],
                "date": [pd.Timestamp("2024-01-01")],
            }
        )
        selected = pd.DataFrame(
            {
                "source_bundle_name": ["daily_bundle"],
                "date": [pd.Timestamp("2024-01-01")],
                "heat_cost_eur": [200.0],
            }
        )
        revised = selected.copy()
        revised.loc[0, "heat_cost_eur"] = 250.0

        with mock.patch(
            "Learning.thermflex_daily_results.dataset_builder._read_bundle_failure_summary",
            return_value={"known_failure_rows": 0, "known_failure_dates": []},
        ):
            original_hash = _hash_signatures(
                _selected_bundle_signatures(truth=truth, selected=selected)
            )
            revised_hash = _hash_signatures(
                _selected_bundle_signatures(truth=truth, selected=revised)
            )

        self.assertNotEqual(original_hash, revised_hash)


if __name__ == "__main__":
    unittest.main()
