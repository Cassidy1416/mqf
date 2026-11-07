"""CLI argument validation: seed rejection and epoch/patience/min-delta bounds."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
import unittest

import approach1_q2 as a1
import approach2_q2 as a2


class TestApproach1Args(unittest.TestCase):
    def test_negative_seed_rejected(self):
        with self.assertRaises(SystemExit):
            a1._parse_args(["--seed", "-1"])

    def test_default_seed_is_42(self):
        self.assertEqual(a1._parse_args([]).seed, 42)

    def test_zero_and_positive_seeds_accepted(self):
        self.assertEqual(a1._parse_args(["--seed", "0"]).seed, 0)

    def test_nonpositive_maturity_rejected(self):
        with self.assertRaises(SystemExit):
            a1._parse_args(["--maturity-years", "0"])
        with self.assertRaises(SystemExit):
            a1._parse_args(["--maturity-years", "-2"])


class TestApproach2Args(unittest.TestCase):
    def test_negative_seed_rejected(self):
        with self.assertRaises(SystemExit):
            a2._parse_args(["--seed", "-7"])

    def test_defaults_early_stopping_parameters(self):
        args = a2._parse_args([])
        self.assertEqual(args.epochs, 100)
        self.assertEqual(args.patience, 10)
        self.assertAlmostEqual(args.min_delta, 1e-5, places=15)

    def test_epochs_above_maximum_rejected(self):
        with self.assertRaises(SystemExit):
            a2._parse_args(["--epochs", "101"])
        self.assertEqual(a2._parse_args(["--epochs", "100"]).epochs, 100)

    def test_epochs_zero_rejected(self):
        with self.assertRaises(SystemExit):
            a2._parse_args(["--epochs", "0"])

    def test_patience_and_min_delta_bounds(self):
        with self.assertRaises(SystemExit):
            a2._parse_args(["--patience", "0"])
        with self.assertRaises(SystemExit):
            a2._parse_args(["--min-delta=-1e-6"])
        parsed = a2._parse_args(["--patience", "3", "--min-delta", "1e-4"])
        self.assertEqual(parsed.patience, 3)
        self.assertAlmostEqual(parsed.min_delta, 1e-4, places=15)


if __name__ == "__main__":
    unittest.main()
