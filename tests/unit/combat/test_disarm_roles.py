# Партия К7х, п. 3.3: [disarm].enemy_chance -- роль обезоруживающего при старте боя
# (docs/plan-k7x.md, В4).
#   disarm.assign_roles(engine), вызывается из CombatEngine.start() после
#     cast.convert_pending_marks и до
#   инициативы: при enemy_chance == 0 -- ни одного обращения к RNG (golden и сетка не сдвигаются);
#   при > 0 для каждого участника side == "enemies", монстра (не героя), без тега disarmer и с
#     оружием
#   (disarm.weapon_ids не пуст): rng.randbelow(100) < chance -> ActiveEffect(id="disarmer",
#     kind="flag",
#   source=ref) и лог «  <имя> метит выбить оружие». ScriptedRng: очередь "d100" (грань 10 -> 9 <
#     50).
#   may_disarm: герой всегда; монстр -- тег disarmer ИЛИ флаг disarmer, и нет флага disarm_used.
#   settle_ground снимает disarmer вместе с disarmed / disarm_used.
from combat_kit import ScriptedRng, creature, make_engine, make_fighter, mon, option_ids, part

from ai_dm.combat import disarm
from ai_dm.combat.controllers import EngineTactics
from ai_dm.combat.end import settle_ground
from ai_dm.config.settings import load_rules_config
from ai_dm.state.creature import ActiveEffect, Equipment


def chance(percent):
    return load_rules_config(toml_text=f"[disarm]\nenemy_chance = {percent}\n")


def fresh(registry, cfg, rng, goblins=2, named=False):
    monsters = [mon(f"goblin_{i}", "goblin_warrior", "hall", named=named)
                for i in range(1, goblins + 1)]
    return make_engine(
        registry, cfg, heroes=[make_fighter(registry)], rng=rng, monsters=monsters,
        started=False,
    )


def roles(engine, ref):
    return [e for e in creature(engine, ref).active_effects if e.id == "disarmer"]


def initiative(count):
    return [10] * count


# --- enemy_chance = 0 ---

def test_zero_chance_gives_no_roles(registry, cfg):
    engine = fresh(registry, cfg, ScriptedRng(d20=initiative(3)))
    engine.start()
    assert roles(engine, "goblin_1") == []
    assert roles(engine, "goblin_2") == []


def test_zero_chance_makes_no_percentile_rolls(registry, cfg):
    rng = ScriptedRng(d20=initiative(3))
    fresh(registry, cfg, rng).start()
    assert rng.calls == ["d20", "d20", "d20"]


def test_zero_chance_leaves_the_log_without_marks(registry, cfg):
    engine = fresh(registry, cfg, ScriptedRng(d20=initiative(3)))
    engine.start()
    assert not any("метит" in line for line in engine.state.log)


# --- enemy_chance = 100 ---

def test_full_chance_marks_every_armed_enemy(registry):
    engine = fresh(registry, chance(100), ScriptedRng(d20=initiative(3), d100=[50, 50]))
    engine.start()
    assert len(roles(engine, "goblin_1")) == 1
    assert len(roles(engine, "goblin_2")) == 1


def test_role_flag_is_a_flag_from_the_monster_itself(registry):
    engine = fresh(registry, chance(100), ScriptedRng(d20=initiative(3), d100=[50, 50]))
    engine.start()
    flag = roles(engine, "goblin_1")[0]
    assert (flag.kind, flag.source) == ("flag", "goblin_1")


def test_role_log_line_names_the_goblin(registry):
    engine = fresh(registry, chance(100), ScriptedRng(d20=initiative(2), d100=[50]), goblins=1)
    engine.start()
    assert "  Воин-гоблин метит выбить оружие" in engine.state.log


def test_full_chance_rolls_once_per_goblin(registry):
    rng = ScriptedRng(d20=initiative(3), d100=[50, 50])
    fresh(registry, chance(100), rng).start()
    assert rng.left("d100") == 0
    assert rng.calls.count("d100") == 2


def test_full_chance_marks_a_named_npc(registry):
    engine = fresh(registry, chance(100), ScriptedRng(d20=initiative(2), d100=[50]),
                   goblins=1, named=True)
    engine.start()
    assert len(roles(engine, "goblin_1")) == 1


def test_hero_is_never_marked(registry):
    engine = fresh(registry, chance(100), ScriptedRng(d20=initiative(2), d100=[50]), goblins=1)
    engine.start()
    assert roles(engine, "hero") == []


# --- 50 %: бросок на каждого ---

def test_fifty_percent_marks_by_the_roll(registry):
    engine = fresh(registry, chance(50), ScriptedRng(d20=initiative(3), d100=[10, 90]))
    engine.start()
    assert len(roles(engine, "goblin_1")) == 1
    assert roles(engine, "goblin_2") == []


def test_roll_equal_to_the_chance_does_not_mark(registry):
    # randbelow(100) = 49 < 50 -- метит; грань 51 -> 50, не меньше 50 -- нет
    engine = fresh(registry, chance(50), ScriptedRng(d20=initiative(3), d100=[50, 51]))
    engine.start()
    assert len(roles(engine, "goblin_1")) == 1
    assert roles(engine, "goblin_2") == []


def test_one_percent_marks_only_the_lowest_roll(registry):
    engine = fresh(registry, chance(1), ScriptedRng(d20=initiative(3), d100=[1, 2]))
    engine.start()
    assert len(roles(engine, "goblin_1")) == 1
    assert roles(engine, "goblin_2") == []


def test_only_marked_goblin_logs_the_line(registry):
    engine = fresh(registry, chance(50), ScriptedRng(d20=initiative(3), d100=[10, 90]))
    engine.start()
    assert sum("метит выбить оружие" in line for line in engine.state.log) == 1


# --- кого не бросаем ---

def test_goblin_with_the_disarmer_tag_does_not_roll(registry, monkeypatch):
    monkeypatch.setattr(registry.get("monster", "goblin_warrior"), "tags", ["disarmer"])
    rng = ScriptedRng(d20=initiative(2), d100=[50])
    engine = fresh(registry, chance(100), rng, goblins=1)
    engine.start()
    assert rng.left("d100") == 1
    assert roles(engine, "goblin_1") == []


def test_hero_on_the_enemy_side_does_not_roll(registry):
    engine = make_engine(
        registry, chance(100), heroes=[make_fighter(registry), make_fighter(registry, "rival")],
        rng=ScriptedRng(d20=initiative(3), d100=[50]),
        monsters=[mon("goblin_1", "goblin_warrior", "hall")], started=False,
    )
    part(engine, "rival").side = "enemies"
    part(engine, "rival").group_id = "goblins"
    engine.start()
    assert roles(engine, "rival") == []
    assert len(roles(engine, "goblin_1")) == 1
    assert engine.rng.left("d100") == 0


def test_ally_monster_on_the_hero_side_does_not_roll(registry):
    engine = make_engine(
        registry, chance(100), heroes=[make_fighter(registry)],
        rng=ScriptedRng(d20=initiative(3), d100=[50]),
        monsters=[mon("goblin_1", "goblin_warrior", "hall"),
                  mon("goblin_2", "goblin_warrior", "hall", side="heroes", group="allies")],
        started=False,
    )
    engine.start()
    assert roles(engine, "goblin_2") == []
    assert len(roles(engine, "goblin_1")) == 1
    assert engine.rng.left("d100") == 0


def test_unarmed_goblin_does_not_roll(registry):
    engine = fresh(registry, chance(100), ScriptedRng(d20=initiative(2), d100=[50]), goblins=1)
    part(engine, "goblin_1").equipment = Equipment()
    engine.start()
    assert roles(engine, "goblin_1") == []
    assert engine.rng.left("d100") == 1


# --- may_disarm ---

def add_flag(engine, flag_id, ref="goblin_1"):
    creature(engine, ref).active_effects.append(ActiveEffect(id=flag_id, source=ref, kind="flag"))


def test_may_disarm_is_false_for_a_plain_goblin(registry, cfg):
    engine = fresh(registry, cfg, ScriptedRng(), goblins=1)
    assert disarm.may_disarm(engine, "goblin_1") is False


def test_may_disarm_is_true_for_the_role_flag(registry, cfg):
    engine = fresh(registry, cfg, ScriptedRng(), goblins=1)
    add_flag(engine, "disarmer")
    assert disarm.may_disarm(engine, "goblin_1") is True


def test_may_disarm_is_false_for_the_role_flag_after_the_attempt(registry, cfg):
    engine = fresh(registry, cfg, ScriptedRng(), goblins=1)
    add_flag(engine, "disarmer")
    add_flag(engine, "disarm_used")
    assert disarm.may_disarm(engine, "goblin_1") is False


def test_may_disarm_is_false_for_the_tag_after_the_attempt(registry, cfg, monkeypatch):
    monkeypatch.setattr(registry.get("monster", "goblin_warrior"), "tags", ["disarmer"])
    engine = fresh(registry, cfg, ScriptedRng(), goblins=1)
    add_flag(engine, "disarm_used")
    assert disarm.may_disarm(engine, "goblin_1") is False


def test_may_disarm_is_true_for_the_tag(registry, cfg, monkeypatch):
    monkeypatch.setattr(registry.get("monster", "goblin_warrior"), "tags", ["disarmer"])
    engine = fresh(registry, cfg, ScriptedRng(), goblins=1)
    assert disarm.may_disarm(engine, "goblin_1") is True


def test_may_disarm_is_always_true_for_a_hero(registry, cfg):
    engine = fresh(registry, cfg, ScriptedRng(), goblins=1)
    assert disarm.may_disarm(engine, "hero") is True


def test_other_flags_do_not_give_the_role(registry, cfg):
    engine = fresh(registry, cfg, ScriptedRng(), goblins=1)
    add_flag(engine, "shove_used")
    assert disarm.may_disarm(engine, "goblin_1") is False


# --- роль в бою ---

def started(registry, cfg, rng, goblins=1):
    monsters = [mon(f"goblin_{i}", "goblin_warrior", "hall") for i in range(1, goblins + 1)]
    return make_engine(
        registry, cfg, heroes=[make_fighter(registry)], rng=rng, monsters=monsters,
    )


def test_role_flag_gives_the_goblin_a_disarm_option(registry, cfg):
    engine = started(registry, cfg, ScriptedRng())
    add_flag(engine, "disarmer")
    assert "disarm:hero:longsword" in option_ids(engine, "goblin_1")


def test_goblin_without_the_role_has_no_disarm_option(registry, cfg):
    engine = started(registry, cfg, ScriptedRng())
    assert not [i for i in option_ids(engine, "goblin_1") if i.startswith("disarm")]


def test_tactics_disarm_once_then_attack(registry, cfg):
    engine = started(registry, cfg, ScriptedRng(d20=[1, 1, 20, 2], d6=[1]))
    add_flag(engine, "disarmer")
    first = EngineTactics(engine).choose_turn(engine.available_actions("goblin_1"), "goblin_1")
    assert first == "disarm:hero:longsword"
    engine.perform("goblin_1", first)
    part(engine, "goblin_1").turn.action = True
    second = EngineTactics(engine).choose_turn(engine.available_actions("goblin_1"), "goblin_1")
    assert second.startswith("attack:")


def test_role_disarm_attempt_marks_the_used_flag(registry, cfg):
    engine = started(registry, cfg, ScriptedRng(d20=[1, 1, 20, 2]))
    add_flag(engine, "disarmer")
    engine.perform("goblin_1", "disarm:hero:longsword")
    assert [e.id for e in creature(engine, "goblin_1").active_effects].count("disarm_used") == 1


# --- settle_ground ---

def test_settle_ground_removes_the_role_flag(registry, cfg):
    engine = started(registry, cfg, ScriptedRng())
    add_flag(engine, "disarmer")
    settle_ground(engine)
    assert roles(engine, "goblin_1") == []


def test_settle_ground_removes_all_four_fight_flags(registry, cfg):
    engine = started(registry, cfg, ScriptedRng())
    for flag_id in ("disarmer", "disarm_used", "shove_used"):
        add_flag(engine, flag_id)
    creature(engine, "goblin_1").active_effects.append(
        ActiveEffect(id="disarmed", source="hero", kind="flag", params={"weapon_id": "scimitar"})
    )
    settle_ground(engine)
    assert creature(engine, "goblin_1").active_effects == []


def test_role_flag_on_a_named_npc_is_removed_after_the_fight(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[make_fighter(registry)], rng=ScriptedRng(),
        monsters=[mon("goblin_1", "goblin_warrior", "hall", named=True)],
    )
    add_flag(engine, "disarmer")
    settle_ground(engine)
    assert roles(engine, "goblin_1") == []
