# К0-фикс, 38 а (docs/K0-FIX-PLAN.md, шаг 1): player_action.improvise.effect -- перечисление
#   advantage|prone|extra_damage|push|disarm (+ "none" = нет); проза в effect -> ValidationError;
#   skill+category заданы, а effect none/не указан -> ValidationError «effect обязателен».
#   Схема инструмента несёт enum; обработчик в бою проверяет target/zone по состоянию боя и
#   возвращает Invalid(code движка) с подсказкой (зоны door - hall - balcony, g1/g2 в hall,
#   герой в door), состояние не меняется.
import pytest
from protocol_kit import dump, req
from pydantic import ValidationError
from test_apply_combat import start

from ai_dm.protocol.apply import apply
from ai_dm.protocol.decision import Invalid
from ai_dm.protocol.requests import ImproviseSpec, parse_request
from ai_dm.protocol.schema import tool_defs, tool_set

EFFECTS = ["advantage", "prone", "extra_damage", "push", "disarm"]


def action(improvise):
    return parse_request({"type": "player_action", "steps": [], "improvise": improvise})


def spec(effect="push", target="g1", zone="door", **fields):
    return {
        "skill": "athletics", "category": "medium", "effect": effect, "target": target,
        "zone": zone, **fields,
    }


# модель

@pytest.mark.parametrize("effect", EFFECTS)
def test_every_known_effect_passes(effect):
    assert action(spec(effect)).improvise.effect == effect


def test_prose_effect_is_invalid():
    with pytest.raises(ValidationError):
        action(spec("столкнуть дозорного с крыши во двор"))


def test_empty_effect_is_invalid():
    with pytest.raises(ValidationError):
        action(spec(""))


def test_effect_none_with_skill_and_category_requires_effect():
    with pytest.raises(ValidationError, match="effect обязателен"):
        action(spec("none"))


def test_missing_effect_with_skill_and_category_requires_effect():
    raw = {"skill": "athletics", "category": "medium"}
    with pytest.raises(ValidationError, match="effect обязателен"):
        action(raw)


def test_all_none_improvise_becomes_none():
    raw = {"skill": "none", "category": "none", "effect": "none", "target": "", "zone": ""}
    assert action(raw).improvise is None


def test_effect_without_skill_and_category_is_dropped_with_improvise():
    assert action({"skill": "none", "category": "none", "effect": "push"}).improvise is None


def test_neutral_effect_is_none_word():
    assert ImproviseSpec.NEUTRAL["effect"] == "none"


# схема

def effect_schema():
    tool = tool_defs(["player_action"])[0]
    return tool["input_schema"]["properties"]["improvise"]["properties"]["effect"]


def test_schema_effect_is_enum_of_five_plus_none():
    assert effect_schema()["enum"] == [*EFFECTS, "none"]


def test_schema_effect_description_names_every_effect():
    text = effect_schema()["description"]
    for effect in EFFECTS:
        assert effect in text


def test_combat_classify_player_action_schema_has_the_enum():
    tool = [t for t in tool_set("combat_classify") if t["name"] == "player_action"][0]
    props = tool["input_schema"]["properties"]["improvise"]["properties"]
    assert props["effect"]["enum"] == [*EFFECTS, "none"]


# обработчик

def act(ctx, **fields):
    return apply(ctx, req("player_action", steps=[], improvise=spec(**fields)))


def test_push_into_own_zone_of_target_is_invalid(registry, cfg):
    ctx, _ = start(registry, cfg)
    before = dump(ctx)
    d = act(ctx, effect="push", target="g1", zone="hall")
    assert isinstance(d, Invalid)
    assert d.code == "zone_not_adjacent"
    assert "собственная" in d.message
    assert "balcony" in d.message
    assert "door" in d.message
    assert "в зоне hall, это её собственная зона; нужна соседняя зона: door, balcony" in d.message
    assert "цель g1" in d.message
    assert dump(ctx) == before


def test_own_zone_note_follows_the_zone_of_the_target(registry, cfg):
    ctx, _ = start(registry, cfg)
    ctx.bundle.session.active_combat.participants[-1].zone_id = "balcony"
    d = act(ctx, effect="push", target="g2", zone="balcony")
    assert d.code == "zone_not_adjacent"
    assert "собственная" in d.message


def test_push_far_zone_message_has_no_own_zone_note(registry, cfg):
    ctx, _ = start(registry, cfg)
    d = act(ctx, effect="push", target="g1", zone="nowhere")
    assert d.code == "zone_not_adjacent"
    assert "собственная" not in d.message
    assert "nowhere" in d.message
    assert "цель g1 стоит в зоне hall; нужна соседняя зона: door, balcony" in d.message


def test_push_without_zone_names_neighbours(registry, cfg):
    ctx, _ = start(registry, cfg)
    before = dump(ctx)
    d = act(ctx, effect="push", target="g1", zone="")
    assert isinstance(d, Invalid)
    assert d.code == "zone_required"
    assert "door" in d.message
    assert "balcony" in d.message
    assert "hall" in d.message
    assert "соседняя с зоной цели g1 (hall): door, balcony" in d.message
    assert dump(ctx) == before


def test_prone_without_target_lists_enemy_refs(registry, cfg):
    ctx, _ = start(registry, cfg)
    before = dump(ctx)
    d = act(ctx, effect="prone", target="", zone="")
    assert isinstance(d, Invalid)
    assert d.code == "target_required"
    assert "g1, g2" in d.message
    assert "prone" in d.message
    assert dump(ctx) == before


def test_unknown_target_ref_is_target_required(registry, cfg):
    ctx, _ = start(registry, cfg)
    d = act(ctx, effect="disarm", target="ghost", zone="")
    assert d.code == "target_required"


def test_push_into_neighbour_zone_is_accepted(registry, cfg):
    ctx, _ = start(registry, cfg)
    d = act(ctx, effect="push", target="g1", zone="door")
    assert d.status == "accepted"
    assert d.result["improvise"]["effect"] == "push"
    assert d.result["improvise"]["zone"] == "door"


def test_advantage_without_target_is_accepted(registry, cfg):
    ctx, _ = start(registry, cfg)
    d = act(ctx, effect="advantage", target="", zone="")
    assert d.status == "accepted"
    assert d.result["improvise"]["effect"] == "advantage"


def test_improvise_check_comes_after_no_active_combat(registry, cfg):
    from protocol_kit import make_ctx

    ctx = make_ctx(registry, cfg)
    d = act(ctx, effect="push", target="g1", zone="hall")
    assert d.code == "no_active_combat"


def test_player_action_without_improvise_is_unchanged(registry, cfg):
    ctx, _ = start(registry, cfg)
    d = apply(ctx, req("player_action", steps=["move:hall"]))
    assert d.status == "accepted"
    assert "improvise" not in d.result
