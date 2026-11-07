"""Daily step count (ceil(252*T)) and scalar/vectorized dt agreement."""
import math
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
import unittest

import approach1_q2 as a1


class TestDailySteps(unittest.TestCase):
    def test_whole_years(self):
        self.assertEqual(a1.daily_steps(1.0), 252)
        self.assertEqual(a1.daily_steps(0.5), 126)
        self.assertEqual(a1.daily_steps(0.25), 63)

    def test_uses_ceiling_not_rounding(self):
        self.assertEqual(a1.daily_steps(1 / 252 + 1e-12), 2)
        self.assertEqual(a1.daily_steps(0.005), 2)
        self.assertEqual(a1.daily_steps(1 / 252), 1)
        self.assertEqual(a1.daily_steps(1.0 + 1e-10), 253)

    def test_at_least_one_step(self):
        self.assertEqual(a1.daily_steps(1e-9), 1)


class TestScalarVectorizedAgreement(unittest.TestCase):
    """Both engines share dt = T/steps; zero volatility makes them deterministic."""

    def closed_form_average(self, spot, rate, steps, dt):
        return spot * sum(math.exp(rate * dt * k) for k in range(1, steps + 1)) / steps

    def test_deterministic_average_matches_closed_form(self):
        spot, rate = 100.0, 0.05
        for maturity in (1.0, 0.5, 0.005):
            steps = a1.daily_steps(maturity)
            dt = maturity / steps
            expected = self.closed_form_average(spot, rate, steps, dt)
            scalar = a1.scalar_average_price(spot, 0.0, rate, steps, dt, 64)
            vectorized = a1.vectorized_average_price(spot, 0.0, rate, steps, dt, 64)
            self.assertAlmostEqual(scalar, expected, places=9, msg=f"maturity={maturity}")
            self.assertAlmostEqual(vectorized, expected, places=9, msg=f"maturity={maturity}")
            self.assertAlmostEqual(scalar, vectorized, places=9, msg=f"maturity={maturity}")

    def test_nonannualized_step_grid_would_disagree_for_short_maturities(self):
        spot, rate, maturity = 100.0, 0.05, 0.005
        steps = a1.daily_steps(maturity)
        dt_fixed = maturity / steps
        old_annualized_dt = 1.0 / a1.STEPS_PER_YEAR
        self.assertEqual(steps, 2)
        self.assertNotAlmostEqual(dt_fixed, old_annualized_dt, places=6)
        correct = self.closed_form_average(spot, rate, steps, dt_fixed)
        stale = self.closed_form_average(spot, rate, steps, old_annualized_dt)
        self.assertNotAlmostEqual(correct, stale, places=9)
        self.assertAlmostEqual(
            a1.scalar_average_price(spot, 0.0, rate, steps, dt_fixed, 64), correct, places=9
        )

    def test_performance_comparison_reports_ceil_steps(self):
        performance = a1.performance_comparison(100.0, 0.0, 0.05, 0.005)
        self.assertEqual(performance["steps"], a1.daily_steps(0.005))
        self.assertEqual(performance["paths"], a1.PERF_PATHS)


if __name__ == "__main__":
    unittest.main()
