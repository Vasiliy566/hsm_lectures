"""Проверка установки без API: всё, что работает локально, должно пройти.

Запуск: python selfcheck.py
"""
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ok_all = True


def check(title: str, condition: bool) -> None:
    global ok_all
    ok_all &= condition
    print(f"{'✓' if condition else '✗'} {title}")


def main() -> None:
    from check_answer import check as check_text
    from skills_lib import discover
    from tools import Permissions, execute_call, reset_sandbox

    reset_sandbox()
    p = Permissions()
    out, ok = execute_call("list_files", '{"folder": "."}', p)
    check("list_files возвращает имена файлов", ok and "shop/orders.py" in json.loads(out)["files"])
    out, ok = execute_call("run_tests", "{}", p)
    check("в исходном проекте 2 теста падают", ok and json.loads(out)["summary"] == "FAILED (failures=2)")
    for name, args, code in [("read_file", '{"file": "x"}', "bad_arguments"),
                             ("delete_file", "{}", "unknown_tool"),
                             ("read_file", '{"path": "../.env"}', "access_denied"),
                             ("read_file", '{"path": ".env"}', "access_denied"),
                             ("read_file", '{"path": "shop/payment.py"}', "not_found"),
                             ("write_file", '{"path": "a.py", "content": ""}', "access_denied")]:
        out, ok = execute_call(name, args, p)
        check(f"{name} {args} → {code}", not ok and json.loads(out)["error"] == code)

    expected = {"manual_1_text.txt": "json", "manual_3_two_files.json": "schema",
                "manual_6_no_such_file.json": "facts", "manual_7_wrong_file.json": "facts",
                "manual_8_good.json": None}
    for name, fails_at in expected.items():
        r = check_text((HERE / "answers" / name).read_text(encoding="utf-8"))
        first_fail = next((lvl for lvl in ("json", "schema", "facts") if r[lvl] is False), None)
        check(f"{name}: останавливается на {fails_at or 'ничём'}", first_fail == fails_at)

    tu = subprocess.run([sys.executable, "01_test_user.py", "--check",
                         '{"name": "А", "age": "тридцать", "email": "a@example.com", "role": "guest", "bio": "-"}'],
                        cwd=HERE, capture_output=True, text=True)
    check("01_test_user.py: Pydantic ловит неверный тип и значение", "ValidationError" in tu.stdout and "role" in tu.stdout)

    check("найдены оба skills", set(discover()) >= {"fix-failing-test", "explain-project"})

    fixed = (HERE / "project/shop/orders.py").read_text(encoding="utf-8").replace(
        '("new", "paid", "picking")', '("new", "paid")')
    report = {"status": "fixed", "changed_files": ["shop/orders.py"], "tests_passed": True,
              "skill_used": "fix-failing-test", "summary": "ручная проверка"}
    lines = ['load_skill {"name": "fix-failing-test"}',
             "write_file " + json.dumps({"path": "shop/orders.py", "content": fixed}, ensure_ascii=False),
             "run_tests {}", "ответ: " + json.dumps(report, ensure_ascii=False)]
    proc = subprocess.run([sys.executable, "05_mini_coder.py", "selfcheck", "--manual", "--allow-write"],
                          cwd=HERE, input="\n".join(lines) + "\n", capture_output=True, text=True)
    check("05_mini_coder.py в ручном режиме: отчёт сходится с фактами",
          proc.returncode == 0 and proc.stdout.count("  ✓") == 4 and "  ✗" not in proc.stdout)
    reset_sandbox()

    try:
        import dotenv, openai  # noqa: F401
        check(f"openai {openai.__version__} и python-dotenv установлены", True)
    except ImportError:
        check("openai и python-dotenv установлены (нужны для настоящих запросов)", False)

    print("\nВсё готово." if ok_all else "\nЕсть ошибки — см. строки с ✗.")
    sys.exit(0 if ok_all else 1)


if __name__ == "__main__":
    main()
