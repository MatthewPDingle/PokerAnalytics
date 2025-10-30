"""Unit tests for stake filtering utilities."""

from __future__ import annotations

import os
import unittest
from unittest import mock

from poker_analytics.data.stakes import StakePolicy


class StakePolicyTests(unittest.TestCase):
    def test_matches_target_stake(self) -> None:
        policy = StakePolicy(allowed_big_blinds=(0.10,))
        self.assertTrue(policy.matches(0.10))
        self.assertTrue(policy.matches(0.1001))  # within tolerance
        self.assertFalse(policy.matches(0.25))
        self.assertFalse(policy.matches(None))

    def test_unrestricted_policy_matches_anything(self) -> None:
        policy = StakePolicy(allowed_big_blinds=())
        self.assertTrue(policy.matches(None))
        self.assertTrue(policy.matches(10.0))

    def test_cache_token_generation(self) -> None:
        policy = StakePolicy(allowed_big_blinds=(0.10, 0.25))
        self.assertEqual(policy.cache_token(), "bb_0p1_0p25")

    def test_from_environment_star_disables_filter(self) -> None:
        with mock.patch.dict(os.environ, {"POKER_ANALYTICS_ALLOWED_BIG_BLINDS": "*"}):
            policy = StakePolicy.from_environment()
        self.assertTrue(policy.is_unrestricted())

    def test_from_environment_parses_multiple_values(self) -> None:
        with mock.patch.dict(os.environ, {"POKER_ANALYTICS_ALLOWED_BIG_BLINDS": "0.10,0.25"}):
            policy = StakePolicy.from_environment()
        self.assertEqual(policy.allowed_big_blinds, (0.10, 0.25))


if __name__ == "__main__":
    unittest.main()
