import unittest
import sys
from pathlib import Path

# Add project root to path so we can import hooks.handoff_guard
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hooks.handoff_guard import evaluate

class TestHandoffGuard(unittest.TestCase):

    def test_evaluate_percent_missing_window(self):
        policy = {"unit": "percent", "warn": 80, "max": 95}
        level, value = evaluate(500, None, policy)
        self.assertEqual(level, "unknown")
        self.assertIsNone(value)

        level, value = evaluate(500, 0, policy)
        self.assertEqual(level, "unknown")
        self.assertIsNone(value)

    def test_evaluate_percent_ok(self):
        policy = {"unit": "percent", "warn": 80, "max": 95}
        # ctx = 50, window = 100 => 50%
        level, value = evaluate(50, 100, policy)
        self.assertEqual(level, "ok")
        self.assertEqual(value, 50.0)

    def test_evaluate_percent_warn(self):
        policy = {"unit": "percent", "warn": 80, "max": 95}
        # ctx = 85, window = 100 => 85%
        level, value = evaluate(85, 100, policy)
        self.assertEqual(level, "warn")
        self.assertEqual(value, 85.0)

        # ctx = 80, window = 100 => 80% (exactly at warn)
        level, value = evaluate(80, 100, policy)
        self.assertEqual(level, "warn")
        self.assertEqual(value, 80.0)

    def test_evaluate_percent_max(self):
        policy = {"unit": "percent", "warn": 80, "max": 95}
        # ctx = 99, window = 100 => 99%
        level, value = evaluate(99, 100, policy)
        self.assertEqual(level, "max")
        self.assertEqual(value, 99.0)

        # ctx = 95, window = 100 => 95% (exactly at max)
        level, value = evaluate(95, 100, policy)
        self.assertEqual(level, "max")
        self.assertEqual(value, 95.0)

    def test_evaluate_tokens_ok(self):
        policy = {"unit": "tokens", "warn": 8000, "max": 9500}
        # ctx = 5000 tokens
        level, value = evaluate(5000, None, policy)
        self.assertEqual(level, "ok")
        self.assertEqual(value, 5000)

    def test_evaluate_tokens_warn(self):
        policy = {"unit": "tokens", "warn": 8000, "max": 9500}
        # ctx = 8500 tokens
        level, value = evaluate(8500, None, policy)
        self.assertEqual(level, "warn")
        self.assertEqual(value, 8500)

        # ctx = 8000 tokens (exactly at warn)
        level, value = evaluate(8000, None, policy)
        self.assertEqual(level, "warn")
        self.assertEqual(value, 8000)

    def test_evaluate_tokens_max(self):
        policy = {"unit": "tokens", "warn": 8000, "max": 9500}
        # ctx = 9900 tokens
        level, value = evaluate(9900, None, policy)
        self.assertEqual(level, "max")
        self.assertEqual(value, 9900)

        # ctx = 9500 tokens (exactly at max)
        level, value = evaluate(9500, None, policy)
        self.assertEqual(level, "max")
        self.assertEqual(value, 9500)


if __name__ == '__main__':
    unittest.main()
