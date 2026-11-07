"""Fractional-tail empirical CVaR on tiny explicit loss vectors."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
import unittest

import torch

import approach2_q2 as a2


class TestFractionalTailCvar(unittest.TestCase):
    def setUp(self):
        self.losses = torch.arange(1.0, 11.0, dtype=torch.float64)

    def test_fractional_tail_at_default_alpha(self):
        # alpha=0.95, 10 samples -> tail_count 0.5 -> CVaR equals the single largest loss.
        self.assertAlmostEqual(float(a2.cvar(self.losses)), 10.0, places=12)

    def test_integer_tail_equals_tail_mean(self):
        self.assertAlmostEqual(float(a2.cvar(self.losses, alpha=0.8)), 9.5, places=12)
        self.assertAlmostEqual(float(a2.cvar(self.losses, alpha=0.5)), 8.0, places=12)

    def test_alpha_ninety_keeps_only_max(self):
        self.assertAlmostEqual(float(a2.cvar(self.losses, alpha=0.9)), 10.0, places=12)

    def test_fractional_weight_interpolates_between_order_statistics(self):
        losses = torch.arange(1.0, 6.0, dtype=torch.float64)  # 1..5
        # alpha=0.86 -> tail_count 0.7, entirely inside the largest loss -> max.
        self.assertAlmostEqual(float(a2.cvar(losses, alpha=0.86)), 5.0, places=12)
        # 20 samples, alpha=0.935 -> tail_count 1.3: (20 + 0.3*19)/1.3.
        twenty = torch.arange(1.0, 21.0, dtype=torch.float64)
        self.assertAlmostEqual(float(a2.cvar(twenty, alpha=0.935)), 25.7 / 1.3, places=10)

    def test_monotone_in_alpha_increasing(self):
        prev = -float("inf")
        for alpha in (0.5, 0.8, 0.9, 0.95):
            value = float(a2.cvar(self.losses, alpha=alpha))
            self.assertGreaterEqual(value, prev)
            prev = value


if __name__ == "__main__":
    unittest.main()
