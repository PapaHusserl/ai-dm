# Подписи слагаемых в строках бросков (stage3-live-rolls R1-R5): bonus_parts, label, damage_type.
from ranger_kit import make_ranger
from test_roll_pipeline import ScriptedRng, make_request

from ai_dm.rules.derived import (
    attack_bonus,
    attack_parts,
    damage_bonus,
    damage_parts,
    saving_throw_bonus,
    saving_throw_parts,
    skill_bonus,
    skill_parts,
)
from ai_dm.rules.roll_pipeline import roll


def bow_request(**kwargs):
    fields = {
        "bonus": 8, "dc": 13, "label": "длинный лук",
        "bonus_parts": [("Лов", 4), ("мастерство", 2), ("Стрельба", 2)],
    }
    fields.update(kwargs)
    return make_request(**fields)


# атака героя

def test_attack_line_has_title_and_signed_parts(registry):
    result = roll(bow_request(), ScriptedRng((20, 14)), registry)
    assert result.log.text == (
        "Атака (длинный лук): d20 (14) + 4 Лов + 2 мастерство + 2 Стрельба = 22 "
        "против КД 13 → попадание"
    )


def test_attack_parts_sum_equals_total(registry):
    result = roll(bow_request(), ScriptedRng((20, 14)), registry)
    assert result.total == 14 + 4 + 2 + 2


def test_zero_part_is_not_printed(registry):
    request = bow_request(bonus=6, bonus_parts=[("Лов", 4), ("мастерство", 2), ("Стрельба", 0)])
    result = roll(request, ScriptedRng((20, 14)), registry)
    assert "Стрельба" not in result.log.text
    assert result.total == 20


def test_negative_part_is_printed_with_minus(registry):
    request = bow_request(bonus=1, bonus_parts=[("Лов", -1), ("мастерство", 2)])
    result = roll(request, ScriptedRng((20, 14)), registry)
    assert "d20 (14) - 1 Лов + 2 мастерство = 15" in result.log.text


def test_attack_without_label_has_no_title(registry):
    result = roll(bow_request(label=""), ScriptedRng((20, 14)), registry)
    assert result.log.text.startswith("d20 (14)")


# монстр: одно слагаемое

def test_monster_attack_bonus_is_one_part(registry):
    request = make_request(bonus=4, label="скимитар")
    result = roll(request, ScriptedRng((20, 10)), registry)
    assert result.log.text == (
        "Атака (скимитар): d20 (10) + 4 бонус атаки = 14 против КД 15 → промах"
    )


# проверка и спасбросок

def test_check_line_has_signed_parts(registry):
    request = make_request(
        "check", skill="survival", dc=12, bonus=4, bonus_parts=[("Мдр", 2), ("мастерство", 2)]
    )
    result = roll(request, ScriptedRng((20, 11)), registry)
    assert "d20 (11) + 2 Мдр + 2 мастерство = 15 против СЛ 12 → успех" in result.log.text


def test_check_line_keeps_skill_title(registry):
    request = make_request(
        "check", skill="survival", ability="wis", dc=12, bonus=4,
        bonus_parts=[("Мдр", 2), ("мастерство", 2)],
    )
    result = roll(request, ScriptedRng((20, 11)), registry)
    assert result.log.text.startswith("Выживание (Мдр): ")


def test_save_line_has_signed_parts(registry):
    request = make_request(
        "save", ability="con", dc=12, bonus=3, bonus_parts=[("Тел", 1), ("мастерство", 2)]
    )
    result = roll(request, ScriptedRng((20, 8)), registry)
    assert result.log.text.startswith("Спасбросок Тел: ")
    assert "d20 (8) + 1 Тел + 2 мастерство = 11 против СЛ 12 → провал" in result.log.text


def test_save_without_parts_keeps_total(registry):
    request = make_request("save", ability="con", dc=12, bonus=3)
    result = roll(request, ScriptedRng((20, 8)), registry)
    assert result.total == 11


# урон

def damage_request(**kwargs):
    fields = {
        "kind": "damage", "dice": "1d8", "bonus": 4, "label": "Урон (длинный лук)",
        "damage_type": "piercing", "bonus_parts": [("Лов", 4)],
    }
    fields.update(kwargs)
    return make_request(**fields)


def test_damage_line_has_title_part_and_type(registry):
    result = roll(damage_request(), ScriptedRng((8, 5)), registry)
    assert result.log.text == "Урон (длинный лук): 1d8 (5) + 4 Лов = 9 колющий"


def test_damage_crit_line_says_dice_doubled(registry):
    result = roll(damage_request(tags={"crit": True}), ScriptedRng((8, 5), (8, 3)), registry)
    assert result.log.text.endswith("(крит, кубики ×2)")


def test_extra_damage_line_has_own_source_and_no_bonus(registry):
    request = make_request(
        "damage", dice="1d6", bonus=0, label="Метка охотника", damage_type="force"
    )
    result = roll(request, ScriptedRng((6, 3)), registry)
    assert result.log.text == "Метка охотника: 1d6 (3) силовой"


# раскладка героя из derived: сумма слагаемых = итог

def test_grey_attack_parts_sum_equals_attack_bonus(registry):
    hero = make_ranger(registry)
    parts = attack_parts(hero, registry, "longbow")
    assert sum(value for _, value in parts) == attack_bonus(hero, registry, "longbow")


def test_grey_attack_parts_are_dex_and_proficiency(registry):
    hero = make_ranger(registry)
    assert attack_parts(hero, registry, "longbow") == [("Лов", 3), ("мастерство", 2)]


def test_grey_archery_adds_a_signed_part_to_the_bow(registry):
    hero = make_ranger(registry)
    hero.sheet.feats.append("archery")
    parts = attack_parts(hero, registry, "longbow")
    assert ("Стрельба", 2) in parts
    assert sum(value for _, value in parts) == attack_bonus(hero, registry, "longbow")


def test_grey_archery_does_not_sign_a_melee_weapon(registry):
    hero = make_ranger(registry)
    hero.sheet.feats.append("archery")
    labels = [label for label, _ in attack_parts(hero, registry, "scimitar")]
    assert "Стрельба" not in labels


def test_grey_damage_parts_sum_equals_damage_bonus(registry):
    hero = make_ranger(registry)
    parts = damage_parts(hero, registry, "longbow")
    assert parts == [("Лов", 3)]
    assert sum(value for _, value in parts) == damage_bonus(hero, registry, "longbow")


def test_grey_skill_parts_sum_equals_skill_bonus(registry):
    hero = make_ranger(registry)
    parts = skill_parts(hero, registry, "survival")
    assert parts == [("Мдр", 2), ("мастерство", 2)]
    assert sum(value for _, value in parts) == skill_bonus(hero, registry, "survival")


def test_grey_save_parts_sum_equals_saving_throw_bonus(registry):
    hero = make_ranger(registry)
    for ability in ("str", "dex", "con", "wis"):
        parts = saving_throw_parts(hero, registry, ability)
        assert sum(value for _, value in parts) == saving_throw_bonus(hero, registry, ability)


def test_grey_save_without_proficiency_has_only_ability_part(registry):
    hero = make_ranger(registry)
    assert saving_throw_parts(hero, registry, "wis") == [("Мдр", 2)]
