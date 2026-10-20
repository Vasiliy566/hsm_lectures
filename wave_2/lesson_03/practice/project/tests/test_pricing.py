import unittest

from shop.pricing import apply_discount


class TestPricing(unittest.TestCase):
    def test_discount(self):
        self.assertEqual(apply_discount(1000, 15), 850.0)

    def test_too_big(self):
        with self.assertRaises(ValueError):
            apply_discount(1000, 70)


if __name__ == "__main__":
    unittest.main()
