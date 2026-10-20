"""Сроки доставки."""

DAYS_BY_CITY = {"Москва": 1, "Санкт-Петербург": 2, "Казань": 3}


def estimate_days(city: str, express: bool = False) -> int:
    """Сколько дней займёт доставка. Для неизвестного города — 7 дней."""
    days = DAYS_BY_CITY.get(city, 7)
    return max(1, days - 1) if express else days
