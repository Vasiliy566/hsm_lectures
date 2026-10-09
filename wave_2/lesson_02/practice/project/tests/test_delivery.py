import unittest

from shop.delivery import estimate_days


class TestDelivery(unittest.TestCase):
    def test_known_city(self):
        self.assertEqual(estimate_days("Казань"), 3)

    def test_express(self):
        self.assertEqual(estimate_days("Москва", express=True), 1)

    def test_unknown_city(self):
        self.assertEqual(estimate_days("Тверь"), 7)


if __name__ == "__main__":
    unittest.main()
