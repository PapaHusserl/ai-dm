# Партия К7х, п. 2.4-2.5: политика ИИ для толчка (docs/K7X-PLAN.md, Q1 (а)).
#   EngineTactics.pick_shove(options, ref) -> id | None:
#     среди пунктов kind "shove" берёт с наибольшей разницей высот (elevation зоны цели минус
#       elevation зоны
#     толчка), только если она >= 1; при равенстве -- первый; None, если у монстра уже есть
#       shove_used
#     (один толчок за бой) или намерение группы не kill / drive_off (capture, spare, rob -- не
#       толкает);
#     вровень и вверх не толкает.
#   choose_turn: escape / pickup / disarm (pick_special) раньше толчка, толчок раньше multiattack и
#     атаки.
#   Ключевой NPC (controller="external") и ведомый скриптом участник видят shove:* в меню и могут
#     выбрать.
import pytest
from combat_kit import (
    ScriptedRng,
    creature,
    hp,
    make_engine,
    make_fighter,
    mon,
    option_ids,
    part,
)

from ai_dm.combat.available import ActionOption
from ai_dm.combat.controllers import AutoHeroController, EngineTactics, ScriptedController
from ai_dm.content.models.monsters import Monster
from ai_dm.state.combat import GroundItem, Zone
from ai_dm.state.creature import ActiveEffect


def zones():
    return [
        Zone(id="door", name="У двери", adjacent=["hall"]),
        Zone(id="hall", name="Центр зала", adjacent=["door", "balcony"]),
        Zone(id="balcony", name="Балкон", adjacent=["hall"], elevation=1),
    ]


def terraces():
    # верх (2) с двумя спусками: ступень (1) и яма (-1)
    return [
        Zone(id="top", name="Верх", adjacent=["step", "pit"], elevation=2),
        Zone(id="step", name="Ступень", adjacent=["top"], elevation=1),
        Zone(id="pit", name="Яма", adjacent=["top"], elevation=-1),
    ]


def twin_steps():
    # два одинаковых спуска: порядок зон задаёт «первый»
    return [
        Zone(id="top", name="Верх", adjacent=["left", "right"], elevation=1),
        Zone(id="left", name="Слева", adjacent=["top"]),
        Zone(id="right", name="Справа", adjacent=["top"]),
    ]


def roof(registry, cfg, rng=None, monster="goblin_warrior", zone_list=None, spot="balcony",
         reg=None, **kwargs):
    return make_engine(
        reg or registry, cfg, heroes=[(make_fighter(registry), spot)], rng=rng,
        zones=zone_list or zones(), monsters=[mon("goblin_1", monster, spot)], **kwargs,
    )


def pick(engine, ref="goblin_1"):
    return EngineTactics(engine).pick_shove(engine.available_actions(ref), ref)


def choose(engine, ref="goblin_1"):
    return EngineTactics(engine).choose_turn(engine.available_actions(ref), ref)


def add_flag(engine, flag_id, ref="goblin_1"):
    creature(engine, ref).active_effects.append(ActiveEffect(id=flag_id, source=ref, kind="flag"))


# --- pick_shove ---

def test_goblin_on_the_balcony_shoves_the_hero_down_when_killing(registry, cfg):
    assert pick(roof(registry, cfg)) == "shove:hero:hall"


def test_goblin_shoves_when_driving_off(registry, cfg):
    assert pick(roof(registry, cfg, intent="drive_off")) == "shove:hero:hall"


@pytest.mark.parametrize("intent", ["capture", "spare", "rob"])
def test_goblin_does_not_shove_with_a_gentle_intent(registry, cfg, intent):
    assert pick(roof(registry, cfg, intent=intent)) is None


def test_no_shove_from_the_door_level(registry, cfg):
    engine = roof(registry, cfg, spot="door")
    assert pick(engine) is None


def test_no_shove_when_no_neighbour_is_lower(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[(make_fighter(registry), "hall")], rng=ScriptedRng(),
        zones=zones(), monsters=[mon("goblin_1", "goblin_warrior", "hall")],
    )
    ids = [o.id for o in engine.available_actions("goblin_1") if o.kind == "shove"]
    assert ids
    assert pick(engine) is None


def test_the_deeper_drop_wins(registry, cfg):
    engine = roof(registry, cfg, zone_list=terraces(), spot="top")
    assert pick(engine) == "shove:hero:pit"


def test_equal_drops_pick_the_first_option(registry, cfg):
    engine = roof(registry, cfg, zone_list=twin_steps(), spot="top")
    first = [o.id for o in engine.available_actions("goblin_1") if o.kind == "shove"][0]
    assert pick(engine) == first
    assert first == "shove:hero:left"


def test_deeper_drop_wins_even_when_listed_later(registry, cfg):
    reordered = list(reversed(terraces()))
    engine = roof(registry, cfg, zone_list=reordered, spot="top")
    assert pick(engine) == "shove:hero:pit"


def test_shove_used_flag_stops_the_next_shove(registry, cfg):
    engine = roof(registry, cfg)
    add_flag(engine, "shove_used")
    assert pick(engine) is None


def test_other_flags_do_not_stop_the_shove(registry, cfg):
    engine = roof(registry, cfg)
    add_flag(engine, "disarm_used")
    assert pick(engine) == "shove:hero:hall"


def test_without_shove_options_pick_is_none(registry, cfg):
    engine = roof(registry, cfg)
    assert EngineTactics(engine).pick_shove([], "goblin_1") is None


def test_pick_ignores_other_option_kinds(registry, cfg):
    engine = roof(registry, cfg)
    options = [ActionOption(id="move:hall", kind="move", label="x", params={"zone": "hall"})]
    assert EngineTactics(engine).pick_shove(options, "goblin_1") is None


def test_drop_is_measured_from_the_target_zone(registry, cfg):
    # цель в зале, монстр толкает её с высоты 0 в дверь (0) -- вровень: не толкает
    engine = roof(registry, cfg, spot="hall")
    options = [ActionOption(
        id="shove:hero:door", kind="shove", label="x", params={"target": "hero", "zone": "door"}
    )]
    assert EngineTactics(engine).pick_shove(options, "goblin_1") is None


def test_shove_only_for_downward_option_among_mixed(registry, cfg):
    engine = roof(registry, cfg, spot="hall")
    options = [
        ActionOption(id="shove:hero:door", kind="shove", label="x",
                     params={"target": "hero", "zone": "door"}),
        ActionOption(id="shove:hero:balcony", kind="shove", label="x",
                     params={"target": "hero", "zone": "balcony"}),
    ]
    assert EngineTactics(engine).pick_shove(options, "goblin_1") is None


# --- порядок choose_turn ---

def test_choose_turn_shoves_instead_of_attacking(registry, cfg):
    assert choose(roof(registry, cfg)) == "shove:hero:hall"


def test_choose_turn_attacks_after_the_one_shove(registry, cfg):
    engine = roof(registry, cfg)
    add_flag(engine, "shove_used")
    assert choose(engine).startswith("attack:")


def test_choose_turn_attacks_on_a_flat_map(registry, cfg):
    engine = roof(registry, cfg, spot="hall")
    assert choose(engine).startswith("attack:")


def test_choose_turn_attacks_with_a_gentle_intent(registry, cfg):
    assert choose(roof(registry, cfg, intent="capture")).startswith("attack:")


def test_shove_comes_before_multiattack(registry, cfg):
    engine = roof(registry, cfg, monster="goblin_boss")
    assert "multiattack" in option_ids(engine, "goblin_1")
    assert choose(engine) == "shove:hero:hall"


def test_pickup_comes_before_shove(registry, cfg):
    engine = roof(registry, cfg)
    add_disarmed(engine, "scimitar")
    engine.state.ground_items.append(
        GroundItem(item_id="scimitar", zone_id="balcony", owner_ref="goblin_1", cost_cp=0)
    )
    assert choose(engine) == "pickup:0"


def test_disarm_comes_before_shove(registry, cfg, monkeypatch):
    monkeypatch.setattr(registry.get("monster", "goblin_warrior"), "tags", ["disarmer"])
    engine = roof(registry, cfg)
    assert choose(engine) == "disarm:hero:longsword"


def test_escape_comes_before_shove(registry, cfg):
    engine = roof(registry, cfg)
    options = engine.available_actions("goblin_1")
    options.append(ActionOption(id="escape:1", kind="escape", label="escape"))
    assert EngineTactics(engine).choose_turn(options, "goblin_1") == "escape:1"


def add_disarmed(engine, weapon_id, ref="goblin_1"):
    creature(engine, ref).active_effects.append(
        ActiveEffect(id="disarmed", source="hero", kind="flag", params={"weapon_id": weapon_id})
    )


def test_hero_auto_controller_does_not_shove(registry, cfg):
    engine = roof(registry, cfg)
    engine.state.turn_index = 0
    options = engine.available_actions("hero")
    assert not AutoHeroController(engine).choose_turn(options, "hero").startswith("shove:")


# --- ход целиком: step() ---

def test_goblin_step_shoves_the_hero_off_the_roof(registry, cfg):
    engine = roof(registry, cfg, ScriptedRng(d20=[2], d6=[3]))
    engine.state.turn_index = 1
    engine.step()
    assert part(engine, "hero").zone_id == "hall"
    assert hp(engine, "hero") == 9


def test_goblin_step_shoves_only_once_per_fight(registry, cfg):
    engine = roof(registry, cfg, ScriptedRng(d20=[10, 15], d6=[1]))
    engine.state.turn_index = 1
    engine.step()
    before = len(engine.state.log)
    engine.state.turn_index = 1
    engine.step()
    new = engine.state.log[before:]
    assert not any("толчок" in line for line in new)
    assert any("Атака" in line for line in new)


def test_goblin_step_on_flat_ground_does_not_shove(registry, cfg):
    engine = roof(registry, cfg, ScriptedRng(d20=[3]), spot="hall")
    engine.state.turn_index = 1
    engine.step()
    assert not any("толчок" in line for line in engine.state.log)


# --- ключевой NPC и внешние контроллеры ---

def named_roof(registry, cfg, rng=None, controller=None):
    engine = make_engine(
        registry, cfg, heroes=[(make_fighter(registry), "balcony")], rng=rng, zones=zones(),
        monsters=[mon("goblin_1", "goblin_warrior", "balcony", named=True)],
    )
    part(engine, "goblin_1").controller = controller or "external"
    return engine


def test_external_npc_sees_the_shove_option(registry, cfg):
    engine = named_roof(registry, cfg)
    assert "shove:hero:hall" in option_ids(engine, "goblin_1")


def test_external_npc_still_sees_the_shove_after_one_was_used(registry, cfg):
    engine = named_roof(registry, cfg)
    add_flag(engine, "shove_used")
    assert "shove:hero:hall" in option_ids(engine, "goblin_1")


def test_scripted_controller_can_choose_the_shove(registry, cfg):
    script = ScriptedController(["shove:hero:hall", "end_turn"])
    engine = make_engine(
        registry, cfg, heroes=[(make_fighter(registry), "balcony")],
        rng=ScriptedRng(d20=[2], d6=[3]), zones=zones(), controllers={"goblin_1": script},
        monsters=[mon("goblin_1", "goblin_warrior", "balcony")],
    )
    engine.state.turn_index = 1
    engine.step()
    assert part(engine, "hero").zone_id == "hall"
    assert "shove:hero:hall" in script.seen[0].options


def test_beast_does_not_shove_by_tactics(registry, cfg):
    data = registry.get("monster", "goblin_warrior").model_dump()
    data.update(creature_type="beast", id="odd_goblin")
    reg = registry.with_items({"monster": [Monster.model_validate(data)]})
    engine = roof(registry, cfg, monster="odd_goblin", reg=reg)
    assert pick(engine) is None
    assert choose(engine).startswith("attack:")


def test_boss_attacks_with_multiattack_when_there_is_nothing_to_shove(registry, cfg):
    engine = roof(registry, cfg, monster="goblin_boss", spot="hall")
    assert choose(engine) == "multiattack"
