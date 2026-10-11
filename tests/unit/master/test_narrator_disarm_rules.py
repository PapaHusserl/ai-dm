# Правила рассказчика (narrator_rules.md): отбор оружия идёт пунктом «Обезоружить» из
# combat.options, improvise disarm -- только для нестандартных способов; подобрать --
# пункт «Подобрать» из combat.options.
from importlib import resources


def rules_text():
    return (resources.files("ai_dm.master") / "prompts" / "narrator_rules.md").read_text(
        encoding="utf-8"
    )


def test_rules_send_disarming_to_the_menu_item():
    assert "пункт «Обезоружить» из `combat.options`" in rules_text()


def test_rules_keep_improvise_disarm_for_unusual_ways():
    assert "`improvise` с эффектом disarm — только для нестандартных способов" in rules_text()


def test_rules_send_picking_up_to_the_menu_item():
    assert "пункт «Подобрать» из `combat.options`" in rules_text()
