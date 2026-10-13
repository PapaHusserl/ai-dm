# Метка охотника и концентрация (docs/decisions/stage3-live-mark.md, H1, H2).
# H1: удар по герою с концентрацией -- строка
#   «Концентрация (Спасбросок Тел): ... против СЛ 10 → провал»
#   и «<имя> теряет концентрацию — ... снята»; успех -- «концентрация удержана».
# H2: цель метки упала, концентрация держится -- бонусное действие transfer_mark:<цель> без ячейки.
from combat_kit import ScriptedRng, creature, mon, option_ids, part, set_hp
from test_ranger_combat import SHOOT, marks, pool, ranger_engine

MARK = "cast:hunters_mark:1:goblin_1"
TWO = [mon("goblin_1", "goblin_warrior", "hall"), mon("goblin_2", "goblin_warrior", "hall")]


def hit_hero(registry, cfg, d20):
    # гоблин в зоне героя; урон 3 + 2 = 5, СЛ 10, Тел +1
    engine = ranger_engine(
        registry, cfg, ScriptedRng(d20=d20, d6=[3]),
        monsters=[mon("goblin_1", "goblin_warrior", "door")],
    )
    engine.perform("hero", MARK)
    engine.perform("goblin_1", "attack:скимитар:hero")
    return engine


def kill_marked(registry, cfg):
    # метка на goblin_1, он падает от выстрела; бонусное действие вернули для проверки переноса
    engine = ranger_engine(
        registry, cfg, ScriptedRng(d20=[15], d8=[5], d6=[4]), monsters=TWO,
    )
    engine.perform("hero", MARK)
    set_hp(engine, "goblin_1", 1)
    engine.perform("hero", SHOOT)
    part(engine, "hero").turn.bonus = True
    return engine


# H1

def test_failed_save_line_names_the_check(registry, cfg):
    engine = hit_hero(registry, cfg, [19, 2])
    assert any("Концентрация (Спасбросок Тел)" in line for line in engine.state.log)


def test_failed_save_line_shows_dc_and_failure(registry, cfg):
    engine = hit_hero(registry, cfg, [19, 2])
    line = next(line for line in engine.state.log if "Концентрация (Спасбросок Тел)" in line)
    assert "СЛ 10" in line
    assert "провал" in line


def test_lost_concentration_line_names_the_spell(registry, cfg):
    engine = hit_hero(registry, cfg, [19, 2])
    line = next(line for line in engine.state.log if "теряет концентрацию" in line)
    assert "Метка охотника" in line
    assert "снята" in line


def test_failed_save_removes_the_mark_from_target(registry, cfg):
    engine = hit_hero(registry, cfg, [19, 2])
    assert marks(engine, "goblin_1") == []
    assert engine.heroes["hero"].creature.concentration is None


def test_held_save_line_says_so(registry, cfg):
    engine = hit_hero(registry, cfg, [19, 18])
    assert any("концентрация удержана" in line for line in engine.state.log)
    assert not any("теряет концентрацию" in line for line in engine.state.log)


def test_held_save_keeps_the_mark(registry, cfg):
    engine = hit_hero(registry, cfg, [19, 18])
    assert len(marks(engine, "goblin_1")) == 1
    assert engine.heroes["hero"].creature.concentration.spell_id == "hunters_mark"


# H2

def test_transfer_is_not_offered_while_the_marked_target_stands(registry, cfg):
    engine = ranger_engine(registry, cfg, ScriptedRng(), monsters=TWO)
    engine.perform("hero", MARK)
    part(engine, "hero").turn.bonus = True
    assert not [i for i in option_ids(engine, "hero") if i.startswith("transfer_mark")]


def test_transfer_is_offered_after_the_marked_target_fell(registry, cfg):
    engine = kill_marked(registry, cfg)
    assert "transfer_mark:goblin_2" in option_ids(engine, "hero")


def test_transfer_is_not_offered_for_the_fallen_target(registry, cfg):
    engine = kill_marked(registry, cfg)
    assert "transfer_mark:goblin_1" not in option_ids(engine, "hero")


def test_transfer_is_not_offered_without_concentration(registry, cfg):
    engine = ranger_engine(registry, cfg, ScriptedRng(d20=[15], d8=[5]), monsters=TWO)
    set_hp(engine, "goblin_1", 1)
    engine.perform("hero", SHOOT)
    assert not [i for i in option_ids(engine, "hero") if i.startswith("transfer_mark")]


def test_transfer_is_not_offered_when_concentration_is_lost(registry, cfg):
    engine = kill_marked(registry, cfg)
    creature(engine, "hero").concentration = None
    assert not [i for i in option_ids(engine, "hero") if i.startswith("transfer_mark")]


def test_transfer_is_not_offered_when_bonus_action_is_spent(registry, cfg):
    engine = kill_marked(registry, cfg)
    part(engine, "hero").turn.bonus = False
    assert not [i for i in option_ids(engine, "hero") if i.startswith("transfer_mark")]


def test_transfer_option_costs_bonus_action(registry, cfg):
    engine = kill_marked(registry, cfg)
    option = next(o for o in engine.available_actions("hero") if o.id == "transfer_mark:goblin_2")
    assert option.cost == "bonus"
    assert "Метк" in option.label


def test_transfer_puts_the_mark_on_the_new_target(registry, cfg):
    engine = kill_marked(registry, cfg)
    engine.perform("hero", "transfer_mark:goblin_2")
    assert [e.source for e in marks(engine, "goblin_2")] == ["hero"]
    assert engine.heroes["hero"].creature.concentration.spell_id == "hunters_mark"


def test_transfer_spends_bonus_action_and_no_resources(registry, cfg):
    engine = kill_marked(registry, cfg)
    slots = pool(engine, "spell_slot:1").current
    favored = pool(engine, "favored_enemy").current
    engine.perform("hero", "transfer_mark:goblin_2")
    assert part(engine, "hero").turn.bonus is False
    assert pool(engine, "spell_slot:1").current == slots
    assert pool(engine, "favored_enemy").current == favored


def test_transfer_option_is_gone_once_the_mark_is_placed(registry, cfg):
    engine = kill_marked(registry, cfg)
    engine.perform("hero", "transfer_mark:goblin_2")
    assert len(marks(engine, "goblin_2")) == 1
    assert "transfer_mark:goblin_2" not in option_ids(engine, "hero")




# К0а: концентрация -- объект Concentration(spell_id, circle); в бою круг = уровень заклинания

def test_mark_cast_in_combat_stores_spell_circle_and_end_time(registry, cfg):
    engine = ranger_engine(registry, cfg, ScriptedRng(), monsters=TWO)
    engine.perform("hero", MARK)
    held = engine.heroes["hero"].creature.concentration
    assert (held.spell_id, held.circle, held.until_s) == ("hunters_mark", 1, 3600)


def test_mark_circle_equals_the_spell_level(registry, cfg):
    engine = ranger_engine(registry, cfg, ScriptedRng(), monsters=TWO)
    engine.perform("hero", MARK)
    held = engine.heroes["hero"].creature.concentration
    assert held.circle == registry.get("spell", "hunters_mark").level


def test_transfer_keeps_the_concentration_object(registry, cfg):
    engine = kill_marked(registry, cfg)
    before = engine.heroes["hero"].creature.concentration.model_copy()
    engine.perform("hero", "transfer_mark:goblin_2")
    assert engine.heroes["hero"].creature.concentration == before


def test_transfer_is_offered_by_spell_id_of_the_object(registry, cfg):
    engine = kill_marked(registry, cfg)
    assert "transfer_mark:goblin_2" in option_ids(engine, "hero")


def test_transfer_is_not_offered_for_another_concentration_spell(registry, cfg):
    from ai_dm.state.creature import Concentration

    engine = kill_marked(registry, cfg)
    creature(engine, "hero").concentration = Concentration(spell_id="bless", circle=1)
    assert not [i for i in option_ids(engine, "hero") if i.startswith("transfer_mark")]


def test_failed_save_clears_the_object_to_none(registry, cfg):
    engine = hit_hero(registry, cfg, [19, 2])
    assert engine.heroes["hero"].creature.concentration is None
