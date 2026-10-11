# Имена в логе боя (ревью партии 5, п. 16): в state.log участник выводится по Participant.name,
# а не по ref ("goblin_1"). Если у нескольких участников одно имя ("Воин-гоблин" у трёх безымянных
# монстров), к имени добавляется номер по порядку в state.participants: "Воин-гоблин 1",
# "Воин-гоблин 2". Уникальное имя -- без номера. Герой -- имя из листа ("Арн").
# combat_kit.make_engine даёт безымянным монстрам name="Воин-гоблин".
from combat_kit import ScriptedRng, make_engine, make_fighter, mon, set_hp

from ai_dm.combat.controllers import ScriptedController


def log_text(engine):
    return "\n".join(engine.state.log)


def test_log_uses_the_monster_name_not_the_ref(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[make_fighter(registry)], rng=ScriptedRng(d20=[15], d8=[4]),
        monsters=[mon("goblin_1", "goblin_warrior", "hall")],
    )
    engine.perform("hero", "attack:longsword:goblin_1")
    text = log_text(engine)
    assert "Воин-гоблин" in text
    assert "goblin_1" not in text


def test_unique_name_has_no_number(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[make_fighter(registry)], rng=ScriptedRng(d20=[15], d8=[4]),
        monsters=[mon("goblin_1", "goblin_warrior", "hall")],
    )
    engine.perform("hero", "attack:longsword:goblin_1")
    assert "Воин-гоблин 1" not in log_text(engine)


def test_same_names_get_numbers(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[make_fighter(registry)], rng=ScriptedRng(d20=[15, 15], d8=[4, 4]),
        monsters=[mon("goblin_1", "goblin_warrior", "hall"),
                  mon("goblin_2", "goblin_warrior", "hall")],
    )
    set_hp(engine, "goblin_1", 30)
    set_hp(engine, "goblin_2", 30)
    engine.perform("hero", "attack:longsword:goblin_1")
    engine.state.participants[0].turn.action = True
    engine.perform("hero", "attack:longsword:goblin_2")
    text = log_text(engine)
    assert "Арн -> Воин-гоблин 1" in text
    assert "Арн -> Воин-гоблин 2" in text
    assert "goblin_1" not in text
    assert "goblin_2" not in text


def test_three_goblins_in_a_turn_header(registry, cfg):
    controllers = {
        "hero": ScriptedController([]), "goblin_1": ScriptedController([]),
        "goblin_2": ScriptedController([]), "goblin_3": ScriptedController([]),
    }
    engine = make_engine(
        registry, cfg, heroes=[make_fighter(registry)], controllers=controllers,
        monsters=[mon("goblin_1", "goblin_warrior", "hall"),
                  mon("goblin_2", "goblin_warrior", "hall"),
                  mon("goblin_3", "goblin_warrior", "hall")],
    )
    for _ in range(4):
        engine.step()
    headers = [line for line in engine.state.log if line.startswith("--- раунд")]
    assert headers[0].endswith("ход: Арн ---")
    assert headers[1].endswith("ход: Воин-гоблин 1 ---")
    assert headers[2].endswith("ход: Воин-гоблин 2 ---")
    assert headers[3].endswith("ход: Воин-гоблин 3 ---")


def test_numbers_do_not_change_the_participant_ref(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[make_fighter(registry)], rng=ScriptedRng(d20=[15], d8=[4]),
        monsters=[mon("goblin_1", "goblin_warrior", "hall"),
                  mon("goblin_2", "goblin_warrior", "hall")],
    )
    engine.perform("hero", "attack:longsword:goblin_2")
    assert [p.ref for p in engine.state.participants] == ["hero", "goblin_1", "goblin_2"]
    assert [p.name for p in engine.state.participants][1:] == ["Воин-гоблин", "Воин-гоблин"]
