"""Unit tests for bet sizing helpers."""

from __future__ import annotations

import math
import unittest

from poker_analytics.data.bet_sizing import BET_SIZE_BUCKETS, BetSizeBucket, bucket_for_ratio, bucket_labels


class BetSizingTests(unittest.TestCase):
    def test_bucket_for_ratio_basic_ranges(self) -> None:
        self.assertEqual(bucket_for_ratio(0.0), BET_SIZE_BUCKETS[0])
        self.assertEqual(bucket_for_ratio(0.2499), BET_SIZE_BUCKETS[0])
        self.assertEqual(bucket_for_ratio(0.25), BET_SIZE_BUCKETS[1])
        self.assertEqual(bucket_for_ratio(0.9999), BET_SIZE_BUCKETS[4])
        self.assertEqual(bucket_for_ratio(1.25), BET_SIZE_BUCKETS[6])
        self.assertEqual(bucket_for_ratio(3.5), BET_SIZE_BUCKETS[6])

    def test_bucket_for_ratio_invalid_values(self) -> None:
        self.assertIsNone(bucket_for_ratio(None))
        self.assertIsNone(bucket_for_ratio(-0.1))
        self.assertIsNone(bucket_for_ratio(float("nan")))

    def test_bucket_contains_logic(self) -> None:
        bucket = BetSizeBucket(key="x", label="x", lower=0.5, upper=1.0)
        self.assertTrue(bucket.contains(0.5))
        self.assertTrue(bucket.contains(0.75))
        self.assertFalse(bucket.contains(1.0))
        self.assertFalse(bucket.contains(0.499))
        inf_bucket = BetSizeBucket(key="y", label="y", lower=1.0, upper=math.inf)
        self.assertTrue(inf_bucket.contains(5.0))

    def test_bucket_labels(self) -> None:
        labels = bucket_labels()
        expected = [bucket.label for bucket in BET_SIZE_BUCKETS]
        self.assertEqual(labels, expected)


if __name__ == "__main__":
    unittest.main()
