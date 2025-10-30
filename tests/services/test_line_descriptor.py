import unittest

from poker_analytics.services.line_descriptor import LineDescriptor, LineStep, parse_line_descriptor


class LineDescriptorTests(unittest.TestCase):
    def test_parse_line_descriptor_basic(self) -> None:
        payload = {
            "steps": [
                {
                    "street": "flop",
                    "actor": "responder",
                    "action": "call",
                    "qualifiers": ["multiway"],
                },
                {
                    "street": "turn",
                    "actor": "bettor",
                    "action": "bet",
                    "sizing": {"bucket_keys": ["pct_40_60"], "ratio_min": 0.4, "ratio_max": 0.6},
                },
            ],
            "focus": "response",
            "annotation": "Flop call then turn bet",
        }

        descriptor = parse_line_descriptor(payload)

        self.assertIsInstance(descriptor, LineDescriptor)
        self.assertEqual(len(descriptor.steps), 2)
        first_step = descriptor.steps[0]
        self.assertIsInstance(first_step, LineStep)
        self.assertEqual(first_step.street, "flop")
        self.assertIn("multiway", first_step.qualifiers)
        second_step = descriptor.steps[1]
        self.assertIsNotNone(second_step.sizing)
        self.assertEqual(second_step.sizing.bucket_keys, ("pct_40_60",))

    def test_parse_line_descriptor_invalid_action(self) -> None:
        payload = {
            "steps": [
                {
                    "street": "flop",
                    "actor": "responder",
                    "action": "invalid",
                }
            ]
        }

        with self.assertRaises(ValueError):
            parse_line_descriptor(payload)


if __name__ == "__main__":
    unittest.main()
