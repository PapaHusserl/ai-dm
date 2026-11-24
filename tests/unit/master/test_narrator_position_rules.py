# Шаг 265, П1: рассказчик ставит позицию проверки (position) вместо stakes -- по ключевым фразам.
from importlib import resources


def rules(name):
    return (resources.files("ai_dm.master") / "prompts" / name).read_text(encoding="utf-8")


def section(title):
    text = rules("narrator_rules.md")
    start = text.index(f"## {title}")
    end = text.find("\n## ", start + 1)
    return text[start:] if end == -1 else text[start:end]


def test_checks_section_names_position_field():
    assert "position" in section("Проверки и сложность")


def test_checks_section_names_all_three_positions():
    checks = section("Проверки и сложность")
    for value in ("controlled", "risky", "desperate"):
        assert value in checks


def test_checks_section_says_risky_fail_costs_something():
    assert "провал чего-то стоит" in section("Проверки и сложность")


def test_checks_section_says_desperate_fail_may_cost_life_or_change_story():
    assert "провал может стоить жизни или изменить ход истории" in section("Проверки и сложность")


def test_checks_section_says_controlled_fail_threatens_nothing():
    assert "провал герою ничем не грозит" in section("Проверки и сложность")


def test_rules_do_not_mention_stakes():
    assert "stakes" not in rules("narrator_rules.md")


# шаг 265, П2: цена провала (п. 17 плана)

def test_checks_section_says_risky_or_desperate_fail_costs_a_price():
    checks = section("Проверки и сложность")
    assert "стоит цены" in checks
    assert "без цены движок ход не примет" in checks


def test_checks_section_names_the_tools_that_pay_the_price():
    checks = section("Проверки и сложность")
    for name in ("damage", "take_item", "curse", "delayed_condition", "start_combat"):
        assert f"`{name}`" in checks


def test_checks_section_says_the_tools_take_the_failed_roll_ref():
    assert "failed_roll_ref" in section("Проверки и сложность")


def test_checks_section_names_take_item_whys_that_pay():
    checks = section("Проверки и сложность")
    for why in ("lost", "stolen", "spent"):
        assert why in checks


def test_checks_section_gives_severity_bands_by_position():
    checks = section("Проверки и сложность")
    assert "risky — nuisance или dangerous" in checks
    assert "desperate — dangerous или deadly" in checks


def test_checks_section_says_success_and_controlled_fail_cost_nothing():
    assert "Успех и провал в controlled цены не несут." in section("Проверки и сложность")


def test_choices_section_asks_to_mark_risky_variant():
    choices = section("Выбор игроку")
    assert "(рискованно)" in choices
    assert "(отчаянно)" in choices
