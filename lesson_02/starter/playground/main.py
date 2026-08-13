from calculator import calculate


try:
    num1 = float(input("Введите первое число: "))
    num2 = float(input("Введите второе число: "))
    num3 = float(input("Введите третье число: "))

    result = calculate(num1, num2, num3)
    print(f"Сумма: {result}")
except ValueError:
    print("Пожалуйста, введите корректные числа.")
