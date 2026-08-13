from calculator import calculate


def test_calculate_three_numbers() -> None:
    assert calculate(1, 2, 3) == 6
