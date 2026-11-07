import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
from unittest.mock import patch
import unittest
import numpy as np
import approach1_q2 as pricing


class RMSEReference(unittest.TestCase):
    def test_small_end_to_end_rmse_study_uses_supplied_asian_reference(self):
        reference = {"price": 3.0, "standard_error": .01, "pairs": 1000, "steps": 3, "beta": 1.0, "control_price": 2.9}
        with patch.object(pricing, "RMSE_PATH_COUNTS", [20, 40]), patch.object(pricing, "RMSE_REPS", [8, 8]):
            result = pricing.rmse_study(np.random.default_rng(42), 100., .2, .02, .01, reference, 3.1)
        self.assertEqual(result["asian_truth"], 3.)
        self.assertEqual(len(result["series"]), 5)
        self.assertTrue(all(np.isfinite(v["rmse"]).all() for v in result["series"].values()))

    def test_reference_standard_error_uses_independent_pair_averages(self):
        states = {"average": np.array([110., 130., 90., 120.]), "geometric": np.array([105., 125., 90., 115.]), "pairs": 2, "steps": 2}
        target_pairs = np.array([5., 25.])
        control_pairs = np.array([2.5, 20.])
        beta = pricing.control_coefficient(target_pairs, control_pairs, axis=0)
        adjusted = target_pairs - beta * (control_pairs - 4.)
        with patch.object(pricing, "REFERENCE_PAIRS", 2), patch.object(pricing, "antithetic_states", return_value=states), patch.object(pricing, "geometric_asian_call", return_value=4.):
            result = pricing.asian_reference(np.random.default_rng(42), 100., .2, 0., 1.)
        self.assertAlmostEqual(result["price"], adjusted.mean())
        self.assertAlmostEqual(result["standard_error"], adjusted.std(ddof=1) / np.sqrt(2))


if __name__ == "__main__":
    unittest.main()
