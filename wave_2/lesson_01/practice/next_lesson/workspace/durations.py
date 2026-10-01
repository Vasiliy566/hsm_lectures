import re

UNITS = {"h": 3600, "m": 60, "s": 1}


def parse_duration(text: str) -> int:
    """Переводит строку вроде "1h 30m" в секунды."""
    total = 0
    for number, unit in re.findall(r"(\d+)([hms])", text):
        total += int(number) * UNITS[unit]
    return total
