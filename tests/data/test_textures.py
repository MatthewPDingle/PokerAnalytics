"""Unit tests for flop texture helpers."""

from __future__ import annotations

import unittest

from poker_analytics.data.textures import FLOP_TEXTURE_SPECS, detect_textures, parse_flop, texture_keys


class TextureTests(unittest.TestCase):
    def _keys(self, flop: str | None) -> set[str]:
        return {spec.key for spec in detect_textures(flop)}

    def test_detect_monotone_high(self) -> None:
        keys = self._keys("Ad Kd Qd")
        self.assertIn("monotone", keys)
        self.assertIn("high", keys)
        self.assertNotIn("rainbow", keys)

    def test_detect_two_tone_connected_ace_high(self) -> None:
        keys = self._keys("As 3c 4s")
        self.assertIn("two_tone", keys)
        self.assertIn("connected", keys)
        self.assertIn("ace_high", keys)
        self.assertNotIn("low", keys)

    def test_detect_rainbow_low(self) -> None:
        keys = self._keys("2d 6c 9h")
        self.assertIn("rainbow", keys)
        self.assertIn("low", keys)
        self.assertNotIn("high", keys)

    def test_detect_paired(self) -> None:
        keys = self._keys("Jh Jc 4d")
        self.assertIn("paired", keys)

    def test_detect_handles_ten_token(self) -> None:
        keys = self._keys("10h Jd Qs")
        self.assertIn("high", keys)
        self.assertNotIn("low", keys)

    def test_parse_flop_resilience(self) -> None:
        cards = parse_flop("ah kd qd")
        self.assertEqual(len(cards), 3)
        self.assertTrue(all(card.rank.isalpha() for card in cards))

    def test_empty_or_invalid_input(self) -> None:
        self.assertEqual(detect_textures(None), [])
        self.assertEqual(texture_keys(""), [])

    def test_texture_order_stable(self) -> None:
        spec_keys = [spec.key for spec in FLOP_TEXTURE_SPECS]
        expected = [
            "rainbow",
            "monotone",
            "two_tone",
            "paired",
            "connected",
            "ace_high",
            "low",
            "high",
        ]
        self.assertEqual(spec_keys, expected)


if __name__ == "__main__":
    unittest.main()
