# Ж1 (docs/plan-zh1.md, п. 3), коммит 1 -- часть движка: мок-прогон выживших боя без сети.
# Бой с двумя гоблинами завершает мастер (ended_by_master): оба остаются в мире NPC со скрытым
# именем. До знакомства журнал (/lore) и сейв показывают вид существа, настоящее имя в журнал
# не попадает; имя, которое прозвучало в рассказе хода, открывается и в журнале, и после
# сейва/загрузки.
# Имя придумывает рассказчик (npc_update name -- коммит 2), здесь оно задано в мире напрямую.
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unit" / "game"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unit" / "protocol"))

from game_kit import (  # noqa: E402
    end_turn_number,
    make_app,
    script_then_react,
    scripted,
    start_combat_call,
    start_combat_input,
    text_step,
    tools_step,
)
from protocol_kit import make_bundle  # noqa: E402

REAL_NAME = "Мурк"
LABEL = "Воин-гоблин 1"
PATTERN = r"goblin_warrior_t\d+_[12]"


def fought_app(registry, tmp_path):
    steps = [tools_step(start_combat_call()), text_step("Гоблины бросаются на вас.")]
    app = make_app(
        registry, tmp_path, script_then_react(steps, end_combat=True), bundle=make_bundle(registry)
    )
    app.handle("Бью ногой дверь")
    app.handle(str(end_turn_number(app.runner)))
    return app


def lore_text(app):
    return "\n".join(app.handle("/lore").lines)


def npc_of(app):
    return app.bundle.world.npcs[sorted(engine_ids(app))[0]]


def engine_ids(app):
    return [i for i, n in app.bundle.world.npcs.items() if n.origin == "engine"]


def tell_name(app, narration):
    app.runner.set_adapter(scripted([text_step(narration)]))
    app.handle("Слушаю")


def test_fight_end_leaves_two_hidden_survivors(registry, tmp_path):
    app = fought_app(registry, tmp_path)
    assert app.bundle.session.active_combat is None
    ids = engine_ids(app)
    assert len(ids) == 2
    assert all(re.fullmatch(PATTERN, i) for i in ids)


def new_fight_input():
    # новый бой с врагами goblin_1 и goblin_2 (ref не совпадают с id выживших)
    data = start_combat_input()
    for enemy, ref in zip(data["enemies"], ("goblin_1", "goblin_2"), strict=True):
        enemy["ref"] = ref
    data["groups"][0]["leader"] = "goblin_1"
    return data


def test_new_enemy_after_fight_has_full_hp_and_survivor_is_untouched(registry, tmp_path):
    app = fought_app(registry, tmp_path)
    survivor = npc_of(app)
    survivor.creature.hp_current = 1
    call = {"id": "sc-2", "name": "start_combat", "input": new_fight_input()}
    app.runner.set_adapter(scripted([tools_step(call), text_step("Новые гоблины.")]))
    app.handle("Иду дальше")
    state = app.bundle.session.active_combat
    fresh = [p for p in state.participants if p.ref.startswith("goblin_")]
    assert len(fresh) == 2
    assert all(p.creature.hp_current == p.creature.hp_max for p in fresh)
    assert app.bundle.world.npcs[sorted(engine_ids(app))[0]].creature.hp_current == 1
    assert len(engine_ids(app)) == 2


def test_lore_shows_survivors_by_label(registry, tmp_path):
    app = fought_app(registry, tmp_path)
    assert f"{LABEL} — 1 зап." in lore_text(app)


def test_real_name_is_not_in_lore_before_it_is_spoken(registry, tmp_path):
    app = fought_app(registry, tmp_path)
    npc_of(app).name = REAL_NAME
    assert REAL_NAME not in lore_text(app)


def test_other_narration_does_not_open_the_name(registry, tmp_path):
    app = fought_app(registry, tmp_path)
    npc_of(app).name = REAL_NAME
    tell_name(app, "Гоблин жмётся к стене.")
    assert npc_of(app).known_name is None
    assert REAL_NAME not in lore_text(app)


def test_spoken_name_opens_in_state_and_lore(registry, tmp_path):
    app = fought_app(registry, tmp_path)
    npc_of(app).name = REAL_NAME
    tell_name(app, f"Гоблин хрипит: меня зовут {REAL_NAME}.")
    assert npc_of(app).known_name == REAL_NAME
    text = lore_text(app)
    assert f"{REAL_NAME} — 1 зап." in text
    assert LABEL not in text


def test_hidden_state_survives_save_and_load(registry, tmp_path):
    app = fought_app(registry, tmp_path)
    npc_of(app).name = REAL_NAME
    app.save_current("auto")
    app.load("auto")
    assert (npc_of(app).known_name, npc_of(app).origin) == (None, "engine")
    assert REAL_NAME not in lore_text(app)


def test_opened_name_survives_save_and_load(registry, tmp_path):
    app = fought_app(registry, tmp_path)
    npc_of(app).name = REAL_NAME
    tell_name(app, f"Гоблин шепчет: {REAL_NAME}.")
    app.save_current("auto")
    app.load("auto")
    assert npc_of(app).known_name == REAL_NAME
    assert f"{REAL_NAME} — 1 зап." in lore_text(app)
