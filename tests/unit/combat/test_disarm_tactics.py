# Тактика и правки ревью партии «Отбор оружия» (docs/plan-combat-disarm.md):
#   EngineTactics.pick_special: escape > pickup > disarm; герою (в том числе авто-герою через
#   EngineTactics) pickup и disarm не выбираются; монстру без таких опций -- None.
#   AutoHeroController берёт pickup только при пустой main_hand.
#   Монстр с тегом disarmer пробует обезоружить героя один раз, дальше атакует.
#   Трофей при победе выдаётся один раз. Герой на стороне врагов не ломает меню (переговоры).
# К7х, п. 4 (docs/plan-k7x.md, В5): EngineTactics.step_to_weapon(options, ref) -- порядок в
# choose_turn:
#   pick_special (escape > pickup > disarm), pick_shove, step_to_weapon, мультиатака, атака.
#   Монстр с выбитым СВОИМ оружием (ground_items.owner_ref == он, can_pick), у которого в своей
#     зоне нет
#   боеспособного врага, идёт в соседнюю зону с оружием (move:<зона>); подбор -- на том же ходу
#     (pickup:N).
#   Герой, монстр без потерь, чужое оружие, оружие дальше соседней зоны, враг в своей зоне, нет
#     хода -- None.
from combat_kit import ScriptedRng, creature, make_engine, make_fighter, make_line, mon, part

from ai_dm.combat.available import ActionOption
from ai_dm.combat.controllers import AutoHeroController, EngineTactics
from ai_dm.rules.inventory import count_item, remove_item
from ai_dm.state.combat import GroundItem
from ai_dm.state.creature import ActiveEffect


def duel(registry, cfg, rng=None, hero=None):
    return make_engine(
        registry, cfg, heroes=[hero or make_fighter(registry)], rng=rng,
        monsters=[mon("goblin_1", "goblin_warrior", "hall")],
    )


def opt(kind, option_id=None):
    return ActionOption(id=option_id or f"{kind}:1", kind=kind, label=kind)


ALL = [opt("attack", "attack:x:y"), opt("disarm"), opt("pickup"), opt("escape")]


def test_pick_special_prefers_escape(registry, cfg):
    engine = duel(registry, cfg)
    assert EngineTactics(engine).pick_special(ALL, "goblin_1") == "escape:1"


def test_pick_special_prefers_pickup_to_disarm(registry, cfg):
    engine = duel(registry, cfg)
    options = [opt("disarm"), opt("pickup")]
    assert EngineTactics(engine).pick_special(options, "goblin_1") == "pickup:1"


def test_pick_special_takes_disarm_when_nothing_else(registry, cfg):
    engine = duel(registry, cfg)
    assert EngineTactics(engine).pick_special([opt("attack", "a:b:c"), opt("disarm")],
                                              "goblin_1") == "disarm:1"


def test_pick_special_is_none_without_special_options(registry, cfg):
    engine = duel(registry, cfg)
    assert EngineTactics(engine).pick_special([opt("attack", "a:b:c")], "goblin_1") is None


def test_hero_does_not_pick_pickup_or_disarm_by_tactics(registry, cfg):
    engine = duel(registry, cfg)
    assert EngineTactics(engine).pick_special([opt("disarm"), opt("pickup")], "hero") is None


def test_hero_still_escapes_by_tactics(registry, cfg):
    engine = duel(registry, cfg)
    assert EngineTactics(engine).pick_special(ALL, "hero") == "escape:1"


def test_auto_hero_with_an_empty_hand_picks_up(registry, cfg):
    hero = make_fighter(registry)
    hero.equipped.main_hand = None
    engine = duel(registry, cfg, hero=hero)
    options = [opt("attack", "attack:longsword:goblin_1"), opt("pickup", "pickup:0")]
    assert AutoHeroController(engine).choose_turn(options, "hero") == "pickup:0"


def test_auto_hero_with_a_weapon_in_hand_does_not_pick_up(registry, cfg):
    engine = duel(registry, cfg)
    options = engine.available_actions("hero") + [opt("pickup", "pickup:0")]
    assert AutoHeroController(engine).choose_turn(options, "hero").startswith("attack:")


def test_auto_hero_never_disarms(registry, cfg):
    engine = duel(registry, cfg)
    options = engine.available_actions("hero")
    assert "disarm:goblin_1:scimitar" in [o.id for o in options]
    assert AutoHeroController(engine).choose_turn(options, "hero").startswith("attack:")


# --- disarmer не зацикливается ---

def test_disarmer_attacks_on_the_second_turn(registry, cfg, monkeypatch):
    monkeypatch.setattr(registry.get("monster", "goblin_warrior"), "tags", ["disarmer"])
    engine = duel(registry, cfg, ScriptedRng(d20=[20, 20, 2, 2, 2], d6=[1]))
    engine.state.turn_index = 1
    engine.step()
    assert any("обезоруживание" in line for line in engine.state.log)
    before = len(engine.state.log)
    engine.state.turn_index = 1
    engine.step()
    new = engine.state.log[before:]
    assert not any("обезоруживание" in line for line in new)
    assert any("Атака" in line for line in new)


# --- трофей один раз ---

def test_trophy_is_given_once(registry, cfg):
    hero = make_fighter(registry)
    engine = duel(registry, cfg, ScriptedRng(d20=[15], d8=[4]), hero=hero)
    engine.creature("goblin_1").hp_current = 1
    engine.state.ground_items.append(
        GroundItem(item_id="scimitar", zone_id="hall", owner_ref="goblin_1", cost_cp=0)
    )
    engine.perform("hero", "attack:longsword:goblin_1")
    assert count_item(hero, "scimitar") == 1
    assert sum(1 for line in engine.state.log if "скимитар: достаётся" in line) == 1


# --- герой на стороне врагов ---

def test_menu_of_a_hero_facing_an_enemy_hero_does_not_crash(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[make_fighter(registry), make_fighter(registry, "rival")],
        monsters=[mon("goblin_1", "goblin_warrior", "hall")],
    )
    part(engine, "rival").side = "enemies"
    part(engine, "rival").group_id = "goblins"
    ids = [o.id for o in engine.available_actions("hero")]
    assert "disarm:rival:longsword" in ids
    assert [o.id for o in engine.available_actions("rival")]


def test_unarmed_rival_cannot_be_disarmed(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[make_fighter(registry), make_fighter(registry, "rival")],
        monsters=[mon("goblin_1", "goblin_warrior", "hall")],
    )
    part(engine, "rival").side = "enemies"
    part(engine, "rival").group_id = "goblins"
    remove_item(engine.heroes["rival"], "longsword")
    ids = [o.id for o in engine.available_actions("hero")]
    assert "disarm:rival:longsword" not in ids


# --- опции: подписи и пропуски ---

def two_goblins(registry, cfg, zones):
    return make_engine(
        registry, cfg, heroes=[make_fighter(registry)],
        monsters=[mon("goblin_1", "goblin_warrior", zones[0]),
                  mon("goblin_2", "goblin_warrior", zones[1])],
    )


def test_disarm_label_names_the_weapon_and_the_target(registry, cfg):
    engine = duel(registry, cfg)
    labels = [o.label for o in engine.available_actions("hero") if o.kind == "disarm"]
    assert "Обезоружить: скимитар → Воин-гоблин" in labels


def test_disarm_options_skip_a_far_target_but_keep_the_next_one(registry, cfg):
    engine = two_goblins(registry, cfg, ["balcony", "hall"])
    targets = {o.params["target"] for o in engine.available_actions("hero") if o.kind == "disarm"}
    assert targets == {"goblin_2"}


def test_disarm_options_skip_a_downed_target_but_keep_the_next_one(registry, cfg):
    engine = two_goblins(registry, cfg, ["hall", "hall"])
    part(engine, "goblin_1").status = "down"
    targets = {o.params["target"] for o in engine.available_actions("hero") if o.kind == "disarm"}
    assert targets == {"goblin_2"}


def test_pickup_options_skip_items_of_other_zones(registry, cfg):
    engine = duel(registry, cfg)
    engine.state.ground_items.append(GroundItem(item_id="scimitar", zone_id="door", cost_cp=0))
    engine.state.ground_items.append(GroundItem(item_id="shortbow", zone_id="hall", cost_cp=0))
    labels = [o.label for o in engine.available_actions("hero") if o.kind == "pickup"]
    assert labels == ["Подобрать: короткий лук"]


def test_extra_attack_labels_of_attacks_and_disarms(registry, cfg):
    engine = duel(registry, cfg)
    part(engine, "hero").turn.action = False
    part(engine, "hero").turn.attacks_left = 1
    options = engine.available_actions("hero")
    marked = [o for o in options if o.kind in ("attack", "disarm")]
    assert marked
    assert all(o.label.endswith(" (ещё 1 из 2)") and len(o.label) > 20 for o in marked)
    assert all(not o.label.endswith("(ещё 1 из 2)") for o in options if o.kind == "end_turn")


# --- метка disarm_used ---

def tagged_goblin(registry, cfg, monkeypatch, rng=None):
    monkeypatch.setattr(registry.get("monster", "goblin_warrior"), "tags", ["disarmer"])
    return duel(registry, cfg, rng)


def used_flags(engine, ref="goblin_1"):
    return [e for e in engine.creature(ref).active_effects if e.id == "disarm_used"]


def test_disarmer_gets_the_used_mark_after_an_attempt(registry, cfg, monkeypatch):
    engine = tagged_goblin(registry, cfg, monkeypatch, ScriptedRng(d20=[20, 20, 2]))
    engine.perform("goblin_1", "disarm:hero:longsword")
    assert len(used_flags(engine)) == 1


def test_used_mark_hides_the_disarm_option(registry, cfg, monkeypatch):
    engine = tagged_goblin(registry, cfg, monkeypatch, ScriptedRng(d20=[20, 20, 2]))
    engine.perform("goblin_1", "disarm:hero:longsword")
    part(engine, "goblin_1").turn.action = True
    assert not [o for o in engine.available_actions("goblin_1") if o.kind == "disarm"]


def test_hero_disarm_leaves_no_used_mark(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[5, 5, 15]))
    engine.perform("hero", "disarm:goblin_1:scimitar")
    assert used_flags(engine) == []
    assert used_flags(engine, "hero") == []


def test_used_mark_is_removed_after_the_fight(registry, cfg, monkeypatch):
    engine = tagged_goblin(registry, cfg, monkeypatch, ScriptedRng(d20=[15], d8=[4]))
    engine.creature("goblin_1").active_effects.append(
        ActiveEffect(id="disarm_used", source="goblin_1", kind="flag")
    )
    engine.creature("goblin_1").hp_current = 1
    engine.perform("hero", "attack:longsword:goblin_1")
    assert engine.state.outcome == "victory"
    assert used_flags(engine) == []


# --- К7х: шаг к своему оружию ---

def lost(engine, weapon_id="scimitar", ref="goblin_1"):
    creature(engine, ref).active_effects.append(
        ActiveEffect(id="disarmed", source="hero", kind="flag", params={"weapon_id": weapon_id})
    )


def lying(engine, zone, item_id="scimitar", owner="goblin_1"):
    engine.state.ground_items.append(
        GroundItem(item_id=item_id, zone_id=zone, owner_ref=owner, cost_cp=0)
    )


def far_hero_duel(registry, cfg, hero_zone="balcony", goblin_zone="hall"):
    return make_engine(
        registry, cfg, heroes=[(make_fighter(registry), hero_zone)], rng=ScriptedRng(),
        monsters=[mon("goblin_1", "goblin_warrior", goblin_zone)],
    )


def tactics(engine, ref="goblin_1"):
    return EngineTactics(engine).step_to_weapon(engine.available_actions(ref), ref)


def decide(engine, ref="goblin_1"):
    return EngineTactics(engine).choose_turn(engine.available_actions(ref), ref)


def test_goblin_walks_to_its_scimitar_in_the_next_zone(registry, cfg):
    engine = far_hero_duel(registry, cfg)
    lost(engine)
    lying(engine, "door")
    assert tactics(engine) == "move:door"
    assert decide(engine) == "move:door"


def test_goblin_picks_the_scimitar_up_on_the_same_turn(registry, cfg):
    engine = far_hero_duel(registry, cfg)
    lost(engine)
    lying(engine, "door")
    engine.perform("goblin_1", decide(engine))
    assert part(engine, "goblin_1").zone_id == "door"
    assert decide(engine) == "pickup:0"
    engine.perform("goblin_1", "pickup:0")
    assert "Воин-гоблин подбирает скимитар" in engine.state.log


def test_goblin_does_not_walk_when_the_hero_is_in_its_zone(registry, cfg):
    engine = far_hero_duel(registry, cfg, hero_zone="hall")
    lost(engine)
    lying(engine, "door")
    assert tactics(engine) is None
    assert decide(engine).startswith("attack:")


def test_goblin_with_the_weapon_in_its_own_zone_picks_it_up_instead(registry, cfg):
    engine = far_hero_duel(registry, cfg)
    lost(engine)
    lying(engine, "hall")
    assert tactics(engine) is None
    assert decide(engine) == "pickup:0"


def test_goblin_does_not_walk_two_zones_for_the_weapon(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[(make_fighter(registry), "z0")], rng=ScriptedRng(),
        zones=make_line(4), monsters=[mon("goblin_1", "goblin_warrior", "z1")],
    )
    lost(engine)
    lying(engine, "z3")
    assert tactics(engine) is None


def test_goblin_does_not_walk_for_someone_elses_weapon(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[(make_fighter(registry), "balcony")], rng=ScriptedRng(),
        monsters=[mon("goblin_1", "goblin_warrior", "hall"),
                  mon("goblin_2", "goblin_warrior", "hall")],
    )
    lost(engine)
    lying(engine, "door", owner="goblin_2")
    assert tactics(engine) is None


def test_goblin_does_not_walk_for_a_weapon_it_did_not_lose(registry, cfg):
    engine = far_hero_duel(registry, cfg)
    lost(engine, "shortbow")
    lying(engine, "door", "scimitar")
    assert tactics(engine) is None


def test_goblin_without_losses_does_not_walk_to_the_ground_items(registry, cfg):
    engine = far_hero_duel(registry, cfg)
    lying(engine, "door")
    assert tactics(engine) is None


def test_goblin_without_moves_left_stays(registry, cfg):
    engine = far_hero_duel(registry, cfg)
    lost(engine)
    lying(engine, "door")
    part(engine, "goblin_1").turn.move = 0
    assert tactics(engine) is None


def test_goblin_walks_for_a_weapon_lost_by_equipment(registry, cfg):
    from ai_dm.state.creature import Equipment

    engine = far_hero_duel(registry, cfg)
    part(engine, "goblin_1").equipment = Equipment(weapons=["shortbow"])
    lying(engine, "door")
    assert tactics(engine) == "move:door"


def test_step_to_weapon_is_none_for_a_hero(registry, cfg):
    hero = make_fighter(registry)
    hero.equipped.main_hand = None
    engine = far_hero_duel(registry, cfg, hero_zone="hall", goblin_zone="balcony")
    engine.heroes["hero"] = hero
    lying(engine, "door", owner="hero")
    assert tactics(engine, "hero") is None


def test_auto_hero_without_a_weapon_does_not_walk_to_it(registry, cfg):
    hero = make_fighter(registry)
    hero.equipped.main_hand = None
    engine = make_engine(
        registry, cfg, heroes=[(hero, "hall")], rng=ScriptedRng(),
        monsters=[mon("goblin_1", "goblin_warrior", "balcony")],
    )
    lying(engine, "door", owner="hero")
    options = engine.available_actions("hero")
    assert not AutoHeroController(engine).choose_turn(options, "hero").startswith("move:door")


def test_walk_to_the_weapon_comes_before_the_bow_shot(registry, cfg):
    # лук цел, герой в соседней зоне: по В5 оружие важнее стрельбы
    engine = far_hero_duel(registry, cfg)
    lost(engine, "scimitar")
    lying(engine, "door")
    ids = [o.id for o in engine.available_actions("goblin_1")]
    assert any(i.startswith("attack:короткий_лук") for i in ids)
    assert decide(engine) == "move:door"


def test_pickup_comes_before_the_walk(registry, cfg):
    engine = far_hero_duel(registry, cfg)
    lost(engine)
    lying(engine, "hall")
    lying(engine, "door")
    assert decide(engine) == "pickup:0"


def test_goblin_skips_a_foreign_item_and_walks_for_its_own(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[(make_fighter(registry), "balcony")], rng=ScriptedRng(),
        monsters=[mon("goblin_1", "goblin_warrior", "hall"),
                  mon("goblin_2", "goblin_warrior", "hall")],
    )
    lost(engine)
    lying(engine, "door", owner="goblin_2")
    lying(engine, "door", owner="goblin_1")
    assert tactics(engine) == "move:door"


def test_goblin_skips_an_item_in_an_unreachable_zone_and_walks_for_the_next(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[(make_fighter(registry), "z0")], rng=ScriptedRng(),
        zones=make_line(4), monsters=[mon("goblin_1", "goblin_warrior", "z1")],
    )
    lost(engine, "scimitar")
    lost(engine, "shortbow")
    lying(engine, "z3", "scimitar")
    lying(engine, "z0", "shortbow")
    assert tactics(engine) == "move:z0"
