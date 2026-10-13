# К1 «Заклинания и дальность»: ходы с новыми параметрами воспроизводятся (--replay-report, код 0,
# «Состояние совпало»): cast_spell с circle=2; Метка охотника вне боя и затем два часа времени
# (концентрация кончается по часам); rest long с prepared_swap. Живых вызовов нет.
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unit" / "ui"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unit" / "game"))

from game_kit import advance_call, scripted, text_step, tools_step  # noqa: E402
from ui_kit import WORLD, build_app, cli  # noqa: E402

from ai_dm.state.creature import ResourcePool  # noqa: E402

MATCH = "Состояние совпало."


def reports_of(root):
    return sorted((Path(root) / WORLD / "issues").glob("*"))


def replay(path):
    return cli(["--replay-report", str(path)], env={})


def call(name, **fields):
    return {"id": f"{name}-1", "name": name, "input": {"type": name, **fields}}


def cast_call(spell_id, circle, target="", free=False):
    return call("cast_spell", spell_id=spell_id, circle=circle, target=target, free=free)


def ranger_app(registry, root, steps):
    app = build_app(registry, root, scripted(steps), hero="grey", hp=200)
    hero = app.bundle.heroes[0]
    hero.sheet.prepared_of().append("cure_wounds")
    hero.creature.resources["spell_slot:2"] = ResourcePool(current=2, max=2)
    return app


def test_turn_with_a_second_circle_cast_replays(registry, tmp_path):
    root = tmp_path / "saves"
    steps = [tools_step(cast_call("cure_wounds", 2, "hero")), text_step("Раны затягиваются.")]
    app = ranger_app(registry, root, steps)
    app.bundle.heroes[0].creature.hp_current = 100
    reply = app.handle("Лечу себя усиленно")
    assert reply.turn.requests == ["cast_spell"]
    assert app.bundle.heroes[0].creature.resources["spell_slot:2"].current == 1
    app.handle("/report апкаст")
    code, out = replay(reports_of(root)[-1])
    assert code == 0, out.text
    assert MATCH in out.lines


def test_mark_and_two_hours_replay_and_end_the_concentration(registry, tmp_path):
    root = tmp_path / "saves"
    hours = [advance_call("adv-1", category="hour"), advance_call("adv-2", category="hour")]
    steps = [
        tools_step(cast_call("hunters_mark", 1, "innkeeper", free=True)), text_step("Метка."),
        tools_step(*hours), text_step("Два часа спустя."),
    ]
    app = ranger_app(registry, root, steps)
    app.handle("Помечаю трактирщика")
    assert app.bundle.heroes[0].creature.concentration.spell_id == "hunters_mark"
    app.handle("Жду два часа")
    assert app.bundle.heroes[0].creature.concentration is None
    app.handle("/report часы")
    code, out = replay(reports_of(root)[-1])
    assert code == 0, out.text
    assert MATCH in out.lines


def test_long_rest_with_a_prepared_swap_replays(registry, tmp_path):
    root = tmp_path / "saves"
    swap = {"drop": ["cure_wounds"], "take": ["longstrider"]}
    steps = [
        tools_step(call("rest", kind="long", hit_dice=0, prepared_swap=swap)),
        text_step("Утро."),
    ]
    app = ranger_app(registry, root, steps)
    app.handle("Отдыхаю и меняю заклинание")
    assert app.bundle.heroes[0].sheet.prepared_of() == ["longstrider"]
    app.handle("/report смена")
    code, out = replay(reports_of(root)[-1])
    assert code == 0, out.text
    assert MATCH in out.lines
