# Реестр услуг, партия П1 (docs/plan-u0.md): секция [services] конфига.
#   ServicesConfig(extra="forbid"): paid_rest = true, kinds: dict[str, ServiceKind].
#   ServiceKind(extra="forbid"): name, price_cp >= 0, unit (night|meal|hour|once),
#       effect (lodging|meal|heal|rest_short|cure), description,
#       heal (кубики, parse_dice; обязателен при effect=heal),
#       cures (id состояний; обязателен непустым при effect=cure, П3).
import pytest
from pydantic import ValidationError

from ai_dm.config.settings import ServiceKind, load_rules_config


def services():
    return load_rules_config().services


def kind(**fields):
    data = {"name": "x", "price_cp": 1, "unit": "meal", "effect": "meal"}
    data.update(fields)
    return ServiceKind(**data)


def test_paid_rest_is_on_by_default():
    assert services().paid_rest is True


def test_default_kinds_present():
    assert set(services().kinds) == {
        "room_poor", "room_modest", "room_comfortable", "room_wealthy",
        "meal_poor", "meal_modest", "meal_comfortable", "ale", "wine_common",
        "heal_barber", "heal_temple", "bed_hour",
        "uncurse_temple",
    }


def test_default_room_prices():
    kinds = services().kinds
    assert [kinds[k].price_cp for k in ("room_poor", "room_modest", "room_comfortable")] == [
        10, 50, 80,
    ]
    assert kinds["room_wealthy"].price_cp == 200


def test_rooms_are_lodging_per_night():
    room = services().kinds["room_modest"]
    assert (room.effect, room.unit) == ("lodging", "night")


def test_heal_kinds_have_dice_and_prices():
    kinds = services().kinds
    assert (kinds["heal_barber"].heal, kinds["heal_barber"].price_cp) == ("1d8", 50)
    assert (kinds["heal_temple"].heal, kinds["heal_temple"].price_cp) == ("2d8+4", 200)


def test_room_has_description_for_the_master():
    assert services().kinds["room_modest"].description


def test_ale_has_no_description():
    assert services().kinds["ale"].description == ""


def test_heal_without_dice_is_error():
    with pytest.raises(ValidationError):
        kind(effect="heal", unit="once")


def test_heal_with_dice_is_accepted():
    assert kind(effect="heal", unit="once", heal="1d8").heal == "1d8"


def test_bad_dice_is_error():
    with pytest.raises(ValueError):
        kind(effect="heal", unit="once", heal="lots")


def test_bad_dice_on_non_heal_effect_is_error():
    with pytest.raises(ValueError):
        kind(heal="lots")


def test_heal_not_required_for_meal():
    assert kind().heal == ""


def test_negative_price_is_error():
    with pytest.raises(ValidationError):
        kind(price_cp=-1)


def test_zero_price_is_allowed():
    assert kind(price_cp=0).price_cp == 0


def test_unknown_unit_is_error():
    with pytest.raises(ValidationError):
        kind(unit="week")


def test_unknown_effect_is_error():
    with pytest.raises(ValidationError):
        kind(effect="bless")


def test_extra_field_is_error():
    with pytest.raises(ValidationError):
        kind(bonus=1)


def test_custom_kind_loads_from_toml():
    toml = (
        '[services.kinds.massage]\nname = "массаж"\nprice_cp = 30\nunit = "hour"\n'
        'effect = "rest_short"\n'
    )
    loaded = load_rules_config(toml_text=toml).services.kinds
    assert loaded["massage"].price_cp == 30
    assert "room_modest" in loaded


# cure (П3): effect = "cure" требует непустой cures

def test_uncurse_temple_is_cure_of_cursed_for_25_gold():
    temple = services().kinds["uncurse_temple"]
    assert (temple.effect, temple.unit, temple.cures) == ("cure", "once", ["cursed"])
    assert temple.price_cp == 2500
    assert temple.name == "снятие проклятия"


def test_cures_default_is_empty_for_other_effects():
    assert kind().cures == []
    assert services().kinds["heal_temple"].cures == []


def test_cure_without_cures_is_error():
    with pytest.raises(ValidationError):
        kind(effect="cure", unit="once")


def test_cure_with_empty_cures_is_error():
    with pytest.raises(ValidationError):
        kind(effect="cure", unit="once", cures=[])


def test_cure_with_cures_is_accepted():
    assert kind(effect="cure", unit="once", cures=["cursed"]).cures == ["cursed"]


def test_cures_not_required_for_other_effects():
    assert kind(effect="heal", unit="once", heal="1d8").cures == []


def test_cure_kind_without_cures_in_toml_is_error():
    toml = (
        '[services.kinds.exorcism]\nname = "обряд"\nprice_cp = 1\nunit = "once"\n'
        'effect = "cure"\n'
    )
    with pytest.raises(ValueError):
        load_rules_config(toml_text=toml)


def test_cure_kind_with_cures_in_toml_loads():
    toml = (
        '[services.kinds.exorcism]\nname = "обряд"\nprice_cp = 1\nunit = "once"\n'
        'effect = "cure"\ncures = ["cursed", "poisoned"]\n'
    )
    assert load_rules_config(toml_text=toml).services.kinds["exorcism"].cures == [
        "cursed", "poisoned",
    ]


def test_heal_kind_without_dice_in_toml_is_error():
    toml = (
        '[services.kinds.miracle]\nname = "чудо"\nprice_cp = 1\nunit = "once"\n'
        'effect = "heal"\n'
    )
    with pytest.raises(ValueError):
        load_rules_config(toml_text=toml)
