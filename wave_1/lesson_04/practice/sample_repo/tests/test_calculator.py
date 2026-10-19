from calculator import average


def test_average_of_values() -> None:
    assert average([2.0, 4.0, 6.0]) == 4.0


def test_average_of_empty_list() -> None:
    assert average([]) == 0.0
