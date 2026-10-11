# Тактика и правки ревью партии «Отбор оружия» (docs/decisions/combat-disarm-review.md):
#   EngineTactics.pick_special: escape > pickup > disarm; герою (в том числе авто-герою через
#   EngineTactics) pickup и disarm не выбираются; монстру без таких опций -- None.
#   AutoHeroController берёт pickup только при пустой main_hand.
#   Монстр с тегом disarmer пробует обезоружить героя один раз, дальше атакует.
#   Трофей при победе выдаётся один раз. Герой на стороне врагов не ломает меню (переговоры).
from combat_kit import ScriptedRng, make_engine, make_fighter, mon, part

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
