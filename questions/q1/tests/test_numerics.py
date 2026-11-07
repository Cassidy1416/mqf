import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
import unittest
import numpy as np
import pandas as pd
from common import zero_curve_rate, interpolate_total_variance, parity_residuals, load_market_data
from approach2_differentiable import svi_holdout_errors


class NumericalContracts(unittest.TestCase):
    def test_simple_quote_is_converted_to_zero_rate(self):
        self.assertAlmostEqual(zero_curve_rate([.04, .05], [.5, 1], 1), np.log1p(.05))
        expected = (np.log1p(.04*.5)/.5 + np.log1p(.05))/2
        self.assertAlmostEqual(zero_curve_rate([.04, .05], [.5, 1], .75), expected)
        with self.assertRaises(ValueError):
            zero_curve_rate([.04, .05], [.5, 1], 2)

    def test_variance_interpolation_is_linear_and_bounded(self):
        self.assertAlmostEqual(interpolate_total_variance([.25, 1], [.01, .04], .5), .02)
        with self.assertRaises(ValueError):
            interpolate_total_variance([.25, 1], [.01, .04], 2)

    def test_parity_counts_only_actual_call_put_pairs(self):
        frame = pd.DataFrame({"date": ["2025-01-01"]*3, "expiry": ["2026-01-01"]*3,
                              "strike": [100, 100, 110], "option_type": ["call", "put", "call"],
                              "close": [10, 10, 5], "spot": [100]*3, "rate": [0.0]*3, "tau": [1.0]*3})
        paired = parity_residuals(frame)
        self.assertEqual(len(paired), 1)
        self.assertEqual(paired.iloc[0]["parity_residual"], 0)

    def test_snapshot_curve_uses_no_future_fixings(self):
        frame = load_market_data()
        self.assertTrue((frame.fixing_date <= frame.date).all())
        self.assertTrue((frame.spot_date <= frame.date).all())
        self.assertEqual(frame.quote_id.nunique(), len(frame))

    def test_saved_holdout_results_are_paired_by_quote_id(self):
        import json
        path = Path(__file__).resolve().parents[1] / "results/approach2/differentiable/metrics.json"
        result = json.loads(path.read_text())["metrics"]["dropout_30_percent"]
        self.assertEqual(len(result["evaluation_quote_ids"]), len(result["svi_errors"]))
        self.assertEqual(len(result["svi_errors"]), len(result["neural_errors"]))


if __name__ == "__main__":
    unittest.main()
