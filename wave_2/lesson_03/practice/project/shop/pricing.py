"""Цены."""


def apply_discount(price: float, percent: float) -> float:
    """Цена со скидкой, округлённая до копеек. Скидка от 0 до 50 %."""
    if not 0 <= percent <= 50:
        raise ValueError("скидка должна быть от 0 до 50 %")
    return round(price * (1 - percent / 100), 2)
