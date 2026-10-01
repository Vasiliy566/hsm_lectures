import unittest

from durations import parse_duration


class TestParseDuration(unittest.TestCase):
    def test_valid(self):
        cases = {
            "45s": 45, "15m": 900, "2h": 7200, "1h30m": 5400,
            "1h 30m 15s": 5415, "90m": 5400, "2H": 7200,
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(parse_duration(text), expected)

    def test_invalid(self):
        for text in ["", "10", "1.5h", "30m1h", "1h1h", "5x"]:
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    parse_duration(text)


if __name__ == "__main__":
    unittest.main()
