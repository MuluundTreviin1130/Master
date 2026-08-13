"""Lock the charge+discharge BESS throughput contract used by Gold, teacher, and NPC.

This test loads ``replacements.py`` by file path so it does not import
``Data.__init__`` (pandas/profile loaders).
"""

from __future__ import annotations

import importlib.util
import math
import sys
import unittest
from pathlib import Path


def _load_replacements():
    path = Path(__file__).resolve().parents[1] / "replacements.py"
    spec = importlib.util.spec_from_file_location("data_assembly_replacements_under_test", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load replacements module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_replacements = _load_replacements()
annual_bess_throughput_kwh = _replacements.annual_bess_throughput_kwh
compute_bess_replacement = _replacements.compute_bess_replacement


def _bess_params(*, lifetime: float, cal_life: float, max_cycles: float, dod: float) -> dict:
    return {
        "lifetime": lifetime,
        "BESS": {
            "battery_lifetime": cal_life,
            "max_cycles": max_cycles,
            "DoD": dod,
        },
    }


class BessThroughputContractTests(unittest.TestCase):
    def test_throughput_is_charge_plus_discharge(self) -> None:
        self.assertEqual(
            annual_bess_throughput_kwh(charged_kwh=10.0, discharged_kwh=8.0),
            18.0,
        )

    def test_rejects_negative_charge_or_discharge(self) -> None:
        with self.assertRaises(ValueError):
            annual_bess_throughput_kwh(charged_kwh=-1.0, discharged_kwh=0.0)
        with self.assertRaises(ValueError):
            annual_bess_throughput_kwh(charged_kwh=0.0, discharged_kwh=-1.0)

    def test_one_equivalent_cycle_per_year_matches_max_cycles(self) -> None:
        # One equivalent full cycle: charge ≈ E*DoD and discharge ≈ E*DoD.
        # Charge+discharge throughput then yields usage_interval = max_cycles.
        bess_kwh = 10.0
        dod = 0.8
        max_cycles = 10.0
        throughput = annual_bess_throughput_kwh(
            charged_kwh=bess_kwh * dod,
            discharged_kwh=bess_kwh * dod,
        )
        info = compute_bess_replacement(
            _bess_params(lifetime=25.0, cal_life=40.0, max_cycles=max_cycles, dod=dod),
            bess_kwh=bess_kwh,
            annual_bess_throughput_kwh=throughput,
        )
        self.assertAlmostEqual(info.interval_years, max_cycles, places=9)
        self.assertEqual(info.replacement_years, [10.0, 20.0])

    def test_charge_only_skips_replacements_that_charge_plus_discharge_keeps(self) -> None:
        # Concrete trigger: 10 kWh BESS, DoD 0.8, 6000 cycles, 2 equivalent
        # cycles per day. Gold/NPC use charge+discharge; the old teacher path
        # passed charge only and dropped two in-lifetime replacements.
        bess_kwh = 10.0
        dod = 0.8
        max_cycles = 6000.0
        cycles_per_year = 730.0
        charged = bess_kwh * dod * cycles_per_year
        discharged = bess_kwh * dod * cycles_per_year
        params = _bess_params(lifetime=25.0, cal_life=40.0, max_cycles=max_cycles, dod=dod)

        gold_info = compute_bess_replacement(
            params,
            bess_kwh=bess_kwh,
            annual_bess_throughput_kwh=annual_bess_throughput_kwh(
                charged_kwh=charged,
                discharged_kwh=discharged,
            ),
        )
        teacher_old_info = compute_bess_replacement(
            params,
            bess_kwh=bess_kwh,
            annual_bess_throughput_kwh=charged,
        )

        self.assertGreater(len(gold_info.replacement_years), len(teacher_old_info.replacement_years))
        self.assertEqual(len(gold_info.replacement_years), 3)
        self.assertEqual(len(teacher_old_info.replacement_years), 1)
        self.assertTrue(math.isfinite(gold_info.interval_years))
        self.assertAlmostEqual(gold_info.interval_years * 2.0, teacher_old_info.interval_years, places=9)


if __name__ == "__main__":
    unittest.main()
