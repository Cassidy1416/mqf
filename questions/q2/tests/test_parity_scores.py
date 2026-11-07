"""Headline parity_z versus validation_z association in the saved metrics."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
import unittest
from datetime import date
from types import SimpleNamespace

from approach1_q2 import MC_Z_LIMIT, build_results


def fixture(price, standard_error, validation_z):
    black_scholes = 407.56830093604776
    validation = {
        "price": black_scholes - 1.9639800494268271 * 2.0213,
        "standard_error": 2.0213,
        "black_scholes": black_scholes,
        "z": validation_z,
        "history": {
            "paths": [1000, 100000],
            "running_price": [405.0, 405.5],
            "running_standard_error": [3.0, 2.2],
        },
    }
    estimates = {
        "european": {"price": price, "standard_error": standard_error},
        "asian": {"price": 30.0, "standard_error": 0.5},
        "up_and_out": {"price": 20.0, "standard_error": 0.5},
        "digital": {"price": 0.55, "standard_error": 0.01},
    }
    priced = {"strike": 3987.0, "barrier": 3987.0 * 1.5, "simulated": {"steps": 252}, "estimates": estimates}
    args = SimpleNamespace(seed=42, valuation_date=date(2025, 12, 31), maturity_years=1.0)
    rate = {"fixing_date": date(2025, 12, 30), "simple_quote": 0.02, "discount_rate": 0.0199}
    calibration_estimates = {"return_observations": 1200, "log_drift": 0.01, "level_drift": 0.02}
    payload = build_results(
        "cu0", args, {"training": 1, "validation": 2, "testing": 3}, 3987.0, 0.2,
        calibration_estimates, date(2020, 1, 2), date(2025, 12, 31), rate,
        validation, priced, 1.5,
    )
    return payload["metrics"]["european"]


class TestHeadlineValidationAssociation(unittest.TestCase):
    def test_headline_parity_z_recomputed_from_headline_price(self):
        block = fixture(405.5506487290551, 2.015212674795709, -1.9639800494268271)
        self.assertAlmostEqual((block["price"] - block["black_scholes"]) / block["standard_error"], block["parity_z"], places=12)
        self.assertAlmostEqual(block["parity_z"], -1.0012105581844728, places=9)

    def test_validation_record_keeps_its_own_z(self):
        block = fixture(405.5506487290551, 2.015212674795709, -1.9639800494268271)
        self.assertAlmostEqual(block["validation"]["validation_z"], -1.9639800494268271, places=12)

    def test_headline_and_validation_scores_are_distinct(self):
        block = fixture(405.5506487290551, 2.015212674795709, -1.9639800494268271)
        self.assertNotAlmostEqual(block["parity_z"], block["validation"]["validation_z"], places=3)

    def test_within_parity_band_flag_follows_headline_score(self):
        inside = fixture(405.5506487290551, 2.015212674795709, -1.9639800494268271)
        self.assertTrue(inside["within_parity_band"])
        four_sigma_price = inside["black_scholes"] + 4.0 * inside["standard_error"]
        outside = fixture(four_sigma_price, inside["standard_error"], 0.1)
        self.assertAlmostEqual(outside["parity_z"], 4.0, places=6)
        self.assertFalse(outside["within_parity_band"])
        self.assertLess(MC_Z_LIMIT, 4.0)


if __name__ == "__main__":
    unittest.main()
