# Партия К7д, шаг 0.2: снимок derived.armor_class_parts до разгрузки (кабан делит функцию на
# base_armor_parts / feat_ac_parts / effect_ac_parts / pierce_parts). Ожидания сняты с кода на
# 187d319: список слагаемых (подпись, значение, пояснение) -- байт-в-байт тот же.
import pytest
from test_derived import make_fighter

from ai_dm.rules.derived import armor_class, armor_class_parts
from ai_dm.state.creature import ActiveEffect, Expiry


def with_effects(hero):
    effects = hero.creature.active_effects
    effects.append(ActiveEffect(
        id="e1", source="x", kind="ac", params={"label": "Щит веры", "amount": 2, "magic": True},
        expires=Expiry(kind="seconds", value=3600),
    ))
    valor = {"label": "Доблесть", "amount": 1}
    effects.append(ActiveEffect(id="e2", source="x", kind="ac", params=valor))
    return hero


def with_feats(hero, feats):
    hero.sheet.feats = feats
    return hero


def with_resist(hero):
    effects = hero.creature.active_effects
    effects.append(ActiveEffect(id="r", source="x", kind="resist", params={"damage_type": "fire"}))
    valor = {"label": "Доблесть", "amount": 1}
    effects.append(ActiveEffect(id="e2", source="x", kind="ac", params=valor))
    return hero


def with_defense(hero):
    hero.sheet.feats = ["savage_attacker", "defense"]
    return hero


LEATHER = ("Кожаный доспех", 11, "")
DEX1 = ("Лов", 1, "")
SHIELD = ("Щит", 2, "")
CHAIN_DEX = ("Лов", 0, "предел тяжёлого доспеха 0")
FAITH = ("Щит веры", 2, "до 01:00")
VALOR = ("Доблесть", 1, "")

CASES = {
    "bare": (lambda: make_fighter(), {}, [("Без доспеха", 10, ""), DEX1]),
    "leather_shield": (
        lambda: make_fighter(armor="leather_armor", shield="shield"), {}, [LEATHER, DEX1, SHIELD],
    ),
    "chain_mail_shield": (
        lambda: make_fighter(armor="chain_mail", shield="shield"), {},
        [("Кольчуга", 16, ""), CHAIN_DEX, SHIELD],
    ),
    "pierce_chain_mail_shield": (
        lambda: make_fighter(armor="chain_mail", shield="shield"), {"pierce": True},
        [("Кольчуга", 12, ""), CHAIN_DEX],
    ),
    "pierce_leather": (
        lambda: make_fighter(armor="leather_armor"), {"pierce": True}, [LEATHER, DEX1],
    ),
    "effects": (
        lambda: with_effects(make_fighter(armor="leather_armor", shield="shield")),
        {"now_s": 100}, [LEATHER, DEX1, SHIELD, FAITH, VALOR],
    ),
    "effects_ignore_magic": (
        lambda: with_effects(make_fighter(armor="leather_armor", shield="shield")),
        {"now_s": 100, "ignore_magic": True}, [LEATHER, DEX1, SHIELD, VALOR],
    ),
    "effects_expired": (
        lambda: with_effects(make_fighter(armor="leather_armor", shield="shield")),
        {"now_s": 7200}, [LEATHER, DEX1, SHIELD, VALOR],
    ),
    "pierce_effects": (
        lambda: with_effects(make_fighter(armor="leather_armor", shield="shield")),
        {"now_s": 100, "pierce": True}, [LEATHER, DEX1, FAITH, VALOR],
    ),
    "pierce_bare_shield": (
        lambda: make_fighter(shield="shield"), {"pierce": True},
        [("Без доспеха", 10, ""), DEX1],
    ),
    "feats_before_defense": (
        lambda: with_feats(
            make_fighter(armor="chain_mail"), ["nope", "savage_attacker", "defense"]
        ),
        {}, [("Кольчуга", 16, ""), CHAIN_DEX, ("Защита", 1, "")],
    ),
    "non_ac_effect_first": (
        lambda: with_resist(make_fighter(armor="leather_armor")),
        {"now_s": 100}, [LEATHER, DEX1, VALOR],
    ),
    "defense_armored": (
        lambda: with_defense(make_fighter(armor="chain_mail")), {},
        [("Кольчуга", 16, ""), CHAIN_DEX, ("Защита", 1, "")],
    ),
    "defense_unarmored": (
        lambda: with_defense(make_fighter()), {}, [("Без доспеха", 10, ""), DEX1],
    ),
}


@pytest.mark.parametrize("name", sorted(CASES))
def test_armor_class_parts_snapshot(registry, name):
    make, kwargs, expected = CASES[name]
    assert armor_class_parts(make(), registry, **kwargs) == expected


@pytest.mark.parametrize("name", sorted(CASES))
def test_armor_class_is_the_sum_of_parts(registry, name):
    make, kwargs, expected = CASES[name]
    assert armor_class(make(), registry, **kwargs) == sum(v for _, v, _ in expected)
