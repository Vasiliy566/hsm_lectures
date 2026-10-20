import unittest

from shop.orders import can_change_address, describe


class TestChangeAddress(unittest.TestCase):
    def test_before_picking(self):
        self.assertTrue(can_change_address("new"))
        self.assertTrue(can_change_address("paid"))

    def test_picking_started(self):
        # Заказ A127 из занятия 1.1: сборка началась — адрес менять нельзя.
        self.assertFalse(can_change_address("picking"))

    def test_after_shipping(self):
        self.assertFalse(can_change_address("shipped"))
        self.assertFalse(can_change_address("delivered"))

    def test_unknown_status(self):
        with self.assertRaises(ValueError):
            can_change_address("lost")

    def test_describe(self):
        self.assertEqual(describe("A127", "picking"),
                         "Заказ A127: статус picking, сменить адрес нельзя")


if __name__ == "__main__":
    unittest.main()
