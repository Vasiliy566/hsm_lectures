"""Заказы магазина «Север»."""

STATUSES = ("new", "paid", "picking", "shipped", "delivered")


def can_change_address(status: str) -> bool:
    """Можно ли изменить адрес доставки при таком статусе заказа."""
    if status not in STATUSES:
        raise ValueError(f"неизвестный статус: {status}")
    return status in ("new", "paid", "picking")


def describe(order_id: str, status: str) -> str:
    """Короткая строка для оператора поддержки."""
    verdict = "можно" if can_change_address(status) else "нельзя"
    return f"Заказ {order_id}: статус {status}, сменить адрес {verdict}"
