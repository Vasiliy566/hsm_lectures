"""Проверка задачи SEV-418. Мини-кодер её не видит: запускает программа после работы агента.

Регламент, ред. 3, п. 4.2: адрес можно менять до начала сборки (new, paid),
а для экспресс-доставки — только до оплаты (new).
"""
import unittest

from shop.orders import can_change_address


class TestSev418(unittest.TestCase):
    def test_express_only_before_payment(self):
        self.assertTrue(can_change_address("new", express=True))
        self.assertFalse(can_change_address("paid", express=True))
        self.assertFalse(can_change_address("picking", express=True))

    def test_regular_order_unchanged(self):
        self.assertTrue(can_change_address("paid"))
        self.assertTrue(can_change_address("paid", express=False))
        self.assertFalse(can_change_address("picking"))


if __name__ == "__main__":
    unittest.main()
