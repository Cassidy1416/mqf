"""Affine-control regression and control-coefficient tests."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
import unittest

import numpy as np

from approach1_q2 import control_coefficient


class TestControlCoefficient(unittest.TestCase):
    def test_beta_exactly_two_for_affine_control(self):
        rng = np.random.default_rng(0)
        y = rng.normal(0.0, 2.0, size=5000)
        x = 2.0 * y + 7.5
        if float(np.ptp(y)) == 0.0:
            self.fail("nonconstant target required")
        beta = float(control_coefficient(x, y, axis=0))
        self.assertAlmostEqual(beta, 2.0, places=10)

    def test_beta_two_with_noise(self):
        rng = np.random.default_rng(1)
        y = rng.normal(0.0, 1.0, size=20000)
        x = 2.0 * y - 1.0 + rng.normal(0.0, 0.5, size=y.size)
        self.assertAlmostEqual(float(control_coefficient(x, y, axis=0)), 2.0, delta=0.01)

    def test_mixing_normalizations_would_scale_beta(self):
        rng = np.random.default_rng(2)
        y = rng.normal(0.0, 1.0, size=1000)
        x = 2.0 * y + 1.0
        n = y.size
        population_cov = float(np.mean((y - y.mean()) * (x - x.mean())))
        sample_var = float(np.var(y, ddof=1))
        self.assertAlmostEqual(
            population_cov / sample_var, 2.0 * (n - 1) / n, places=10
        )
        self.assertAlmostEqual(float(control_coefficient(x, y, axis=0)), 2.0, places=9)
        self.assertNotAlmostEqual(
            population_cov / sample_var, float(control_coefficient(x, y, axis=0)), places=6
        )

    def test_matches_sample_moments_reference(self):
        rng = np.random.default_rng(3)
        target = rng.normal(0.0, 1.0, size=400)
        control = 0.6 * target + rng.normal(0.0, 0.2, size=400)
        reference = np.cov(target, control, ddof=1)[0, 1] / np.var(control, ddof=1)
        self.assertAlmostEqual(
            float(control_coefficient(target, control, axis=0)), float(reference), places=12
        )

    def test_rowwise_beta_on_matrix(self):
        y = np.array([-2.0, -1.0, 0.0, 1.0, 2.0])
        matrix = np.vstack([1.0 * y, 2.0 * y + 3.0, -0.5 * y + 9.0])
        beta = control_coefficient(matrix, y, axis=1)
        np.testing.assert_allclose(beta, [1.0, 2.0, -0.5], rtol=1e-9)

    def test_degenerate_column_of_twos(self):
        target = np.ones((3, 5))
        control = np.arange(5.0) * 0.0 + 1.0
        beta = control_coefficient(target, control, axis=1)
        np.testing.assert_allclose(beta, [0.0, 0.0, 0.0])

    def test_requires_two_samples(self):
        with self.assertRaises(ValueError):
            control_coefficient([1.0], [1.0])


if __name__ == "__main__":
    unittest.main()
