# Ожидаемый API: ai_dm.state.triggers (только модели, вычисление условий -- партия 4)
#   Condition -- discriminated union по полю type:
#     AllOf(type="all", items: list[Condition])  AnyOf(type="any", items)  NotOf(type="not", item)
#       (классы названы AllOf/AnyOf/NotOf, чтобы не затенять typing.Any; YAML-тип по-прежнему
#       all/any/not)
#     Flag(type="flag", name: str, value: bool = True)
#     HeroHas(type="hero_has", item: str)
#     NpcStatus(type="npc_status", id: str, is_: str (alias "is"))
#     HeroAt(type="hero_at", location: str)      NpcAt(type="npc_at", id: str, at: str)
#     TimeAfter(type="time_after", seconds: int)
#     Attitude(type="attitude", npc: str, gte: int | None, lte: int | None)
#     Favor(type="favor", god: str, gte: int | None, lte: int | None)
#     EventActive(type="event_active", event: str)
#     HeroDead(type="hero_dead")                 Narrative(type="narrative", text: str)
#   Короткая запись (model_validator(mode="before")), полная запись -- {"type": ..., поля}:
#     {hero_has: x} == {type: hero_has, item: x}
#     {flag: x}, {hero_at: x}, {event_active: x}, {narrative: text}, {hero_dead: true}
#     {npc_status: {id, is}}, {npc_at: {id, at}}, {attitude: {npc, gte}}, {favor: {god, gte}}
#     {time_after: секунды}; {all: [...]}, {any: [...]}, {not: условие}
#   Trigger(id, if_ (alias "if", populate_by_name=True), then: str, once=False,
#           state: "active" | "fired" | "disabled" = "active",
#           cooldown: str | None = None ("7d"; проверяется через Duration.parse -- мусор ->
#           ValidationError), key=False, fired_count=0, last_fired_at=None)
#   Secret(id, text, reveal_if: Condition, revealed=False)
#   Неизвестный вид условия -> pydantic.ValidationError, в str(err) -- имя вида; loc содержит "if".
#   Модели: extra="forbid".
import pytest
from pydantic import ValidationError

from ai_dm.state.triggers import AllOf, AnyOf, HeroHas, Narrative, NotOf, Secret, Trigger


def loc_names(error):
    names = []
    for item in error.errors():
        names.extend(str(part) for part in item["loc"])
    return names


def test_short_trigger_builds_hero_has_condition():
    trigger = Trigger.model_validate(
        {"id": "steal_grail", "if": {"hero_has": "blood_grail"}, "then": "выкрадет", "once": True}
    )
    assert isinstance(trigger.if_, HeroHas)
    assert trigger.if_.item == "blood_grail"


def test_short_and_full_trigger_are_equal():
    short = Trigger.model_validate(
        {"id": "steal_grail", "if": {"hero_has": "blood_grail"}, "then": "выкрадет", "once": True}
    )
    full = Trigger.model_validate(
        {
            "id": "steal_grail",
            "if": {"type": "hero_has", "item": "blood_grail"},
            "then": "выкрадет",
            "once": True,
        }
    )
    assert short == full


def test_short_and_full_trigger_have_same_json():
    short = Trigger.model_validate({"id": "t", "if": {"hero_has": "x"}, "then": "a"})
    full = Trigger.model_validate({"id": "t", "if": {"type": "hero_has", "item": "x"}, "then": "a"})
    assert short.model_dump_json() == full.model_dump_json()


def test_trigger_accepts_python_field_name_if_():
    trigger = Trigger(id="t", if_={"hero_has": "x"}, then="a")
    assert trigger.if_.item == "x"


def test_trigger_defaults():
    trigger = Trigger.model_validate({"id": "t", "if": {"flag": "x"}, "then": "a"})
    assert trigger.state == "active"
    assert trigger.once is False
    assert trigger.cooldown is None
    assert trigger.key is False
    assert trigger.fired_count == 0
    assert trigger.last_fired_at is None


def test_trigger_keeps_cooldown_text():
    trigger = Trigger.model_validate(
        {"id": "t", "if": {"flag": "x"}, "then": "a", "cooldown": "7d"}
    )
    assert trigger.cooldown == "7d"


def test_trigger_roundtrip_through_json_keeps_condition():
    trigger = Trigger.model_validate({"id": "t", "if": {"hero_has": "x"}, "then": "a"})
    again = Trigger.model_validate_json(trigger.model_dump_json())
    assert again == trigger


def test_all_condition_with_nested_short_forms():
    trigger = Trigger.model_validate(
        {
            "id": "t",
            "then": "a",
            "if": {
                "all": [
                    {"hero_has": "blood_grail"},
                    {"npc_status": {"id": "mentor_aldric", "is": "alive"}},
                ]
            },
        }
    )
    assert isinstance(trigger.if_, AllOf)
    assert len(trigger.if_.items) == 2


def test_any_condition_short_form():
    trigger = Trigger.model_validate(
        {"id": "t", "then": "a", "if": {"any": [{"flag": "a"}, {"flag": "b"}]}}
    )
    assert isinstance(trigger.if_, AnyOf)
    assert len(trigger.if_.items) == 2


def test_not_condition_short_form():
    trigger = Trigger.model_validate({"id": "t", "then": "a", "if": {"not": {"flag": "a"}}})
    assert isinstance(trigger.if_, NotOf)
    assert trigger.if_.item.type == "flag"


def test_narrative_condition_short_form():
    trigger = Trigger.model_validate(
        {"id": "t", "then": "a", "if": {"narrative": "Герой узнаёт тайну"}}
    )
    assert isinstance(trigger.if_, Narrative)
    assert trigger.if_.text == "Герой узнаёт тайну"


def test_mixed_all_with_narrative_validates():
    trigger = Trigger.model_validate(
        {
            "id": "t",
            "then": "a",
            "if": {"all": [{"flag": "met"}, {"narrative": "Герой узнаёт тайну"}]},
        }
    )
    assert [c.type for c in trigger.if_.items] == ["flag", "narrative"]


@pytest.mark.parametrize(
    "short, kind",
    [
        ({"flag": "met"}, "flag"),
        ({"hero_has": "blood_grail"}, "hero_has"),
        ({"npc_status": {"id": "aldric", "is": "dead"}}, "npc_status"),
        ({"hero_at": "tavern"}, "hero_at"),
        ({"npc_at": {"id": "aldric", "at": "tavern"}}, "npc_at"),
        ({"time_after": 3600}, "time_after"),
        ({"attitude": {"npc": "aldric", "gte": 60}}, "attitude"),
        ({"favor": {"god": "morrah", "gte": 3}}, "favor"),
        ({"event_active": "grey_plague"}, "event_active"),
        ({"hero_dead": True}, "hero_dead"),
        ({"narrative": "что-то случилось"}, "narrative"),
    ],
)
def test_every_condition_kind_has_short_form(short, kind):
    trigger = Trigger.model_validate({"id": "t", "then": "a", "if": short})
    assert trigger.if_.type == kind


def test_unknown_condition_kind_in_short_form_raises_validation_error():
    with pytest.raises(ValidationError) as exc:
        Trigger.model_validate({"id": "t", "then": "a", "if": {"banana": "x"}})
    assert "banana" in str(exc.value)


def test_unknown_condition_kind_error_has_path_to_if():
    with pytest.raises(ValidationError) as exc:
        Trigger.model_validate({"id": "t", "then": "a", "if": {"banana": "x"}})
    names = loc_names(exc.value)
    assert "if" in names or "if_" in names


def test_unknown_condition_kind_in_full_form_raises_validation_error():
    with pytest.raises(ValidationError):
        Trigger.model_validate({"id": "t", "then": "a", "if": {"type": "banana"}})


def test_unknown_kind_inside_all_raises_validation_error():
    with pytest.raises(ValidationError) as exc:
        Trigger.model_validate({"id": "t", "then": "a", "if": {"all": [{"banana": "x"}]}})
    assert "banana" in str(exc.value)


def test_trigger_without_condition_raises_validation_error():
    with pytest.raises(ValidationError):
        Trigger.model_validate({"id": "t", "then": "a"})


def test_trigger_extra_field_raises_validation_error():
    with pytest.raises(ValidationError):
        Trigger.model_validate({"id": "t", "if": {"flag": "x"}, "then": "a", "bogus": 1})


def test_secret_reveal_if_accepts_short_form():
    secret = Secret.model_validate({"id": "s1", "text": "тайна", "reveal_if": {"flag": "found"}})
    assert secret.reveal_if.type == "flag"


def test_secret_is_not_revealed_by_default():
    secret = Secret.model_validate({"id": "s1", "text": "тайна", "reveal_if": {"flag": "found"}})
    assert secret.revealed is False


def test_secret_unknown_condition_kind_raises_validation_error():
    with pytest.raises(ValidationError) as exc:
        Secret.model_validate({"id": "s1", "text": "тайна", "reveal_if": {"banana": 1}})
    assert "banana" in str(exc.value)


# AllOf/AnyOf/NotOf: YAML-типы остались all/any/not

def test_all_of_has_yaml_type_all():
    assert AllOf(items=[]).type == "all"


def test_any_of_has_yaml_type_any():
    assert AnyOf(items=[]).type == "any"


def test_not_of_has_yaml_type_not():
    assert NotOf(item={"flag": "a"}).type == "not"


def test_full_form_all_gives_all_of():
    trigger = Trigger.model_validate(
        {"id": "t", "then": "a", "if": {"type": "all", "items": [{"flag": "a"}]}}
    )
    assert isinstance(trigger.if_, AllOf)


def test_condition_classes_are_not_named_all_any_not():
    from ai_dm.state import triggers

    assert not hasattr(triggers, "All")
    assert not hasattr(triggers, "Any")
    assert not hasattr(triggers, "Not")


# Trigger.state

@pytest.mark.parametrize("state", ["active", "fired", "disabled"])
def test_trigger_accepts_known_state(state):
    trigger = Trigger.model_validate({"id": "t", "if": {"flag": "x"}, "then": "a", "state": state})
    assert trigger.state == state


def test_trigger_unknown_state_raises_validation_error():
    with pytest.raises(ValidationError):
        Trigger.model_validate({"id": "t", "if": {"flag": "x"}, "then": "a", "state": "sleeping"})


def test_trigger_state_survives_json_roundtrip():
    data = {"id": "t", "if": {"flag": "x"}, "then": "a", "state": "fired"}
    trigger = Trigger.model_validate(data)
    assert Trigger.model_validate_json(trigger.model_dump_json()).state == "fired"


# Trigger.cooldown

@pytest.mark.parametrize("cooldown", ["7d", "12h", "30m"])
def test_trigger_accepts_valid_cooldown(cooldown):
    trigger = Trigger.model_validate(
        {"id": "t", "if": {"flag": "x"}, "then": "a", "cooldown": cooldown}
    )
    assert trigger.cooldown == cooldown


@pytest.mark.parametrize("cooldown", ["soon", "7", "d7", "1 day", "", "-1d", "1.5h"])
def test_trigger_invalid_cooldown_raises_validation_error(cooldown):
    with pytest.raises(ValidationError):
        Trigger.model_validate({"id": "t", "if": {"flag": "x"}, "then": "a", "cooldown": cooldown})


def test_trigger_invalid_cooldown_error_path_contains_cooldown():
    with pytest.raises(ValidationError) as exc:
        Trigger.model_validate({"id": "t", "if": {"flag": "x"}, "then": "a", "cooldown": "soon"})
    assert "cooldown" in loc_names(exc.value)
