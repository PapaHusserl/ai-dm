# Сквозной сценарий У1 П3 (docs/plan-u1.md, П3 п. 6): последствия платной близости и гигиена.
# Мир «Вейл»; риски компании ставятся конфигом (СЛ 99 -- спасбросок всегда проваливается,
# 0 -- проверки нет), чтобы исход не зависел от сида.
#   * болезнь: покупка при провале -> у героя «болен» (/sheet), деньги −; храм снимает болезнь;
#   * кража: покупка при провале -> кошелёк полегчал на 10-40 % (строка «Кошелёк полегчал»);
#   * ревность: спутница с целью love -> отношение −10, в памяти betrayal;
#   * гигиена: месяц без мытья + граница сцены -> «вонь» в /sheet, Убеждение идёт с помехой «вонь»,
#     услуга bath -> чисто.
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unit" / "game"))

import game_kit  # noqa: E402
from game_kit import (  # noqa: E402
    OPUS,
    SAVED_AT,
    advance_call,
    end_scene_call,
    make_app,
    settings,
    skill_check_call,
)
from slots_kit import WORLD_TEXT  # noqa: E402

from ai_dm.game.scene import hero_of  # noqa: E402
from ai_dm.game.starter import new_world  # noqa: E402
from ai_dm.llm.mock import ScriptedAdapter  # noqa: E402
from ai_dm.state.relations import NpcGoal  # noqa: E402
from ai_dm.state.world import NPC  # noqa: E402


def risks(monkeypatch, disease_dc, theft_dc, kind="companion_common"):
    base = game_kit.settings

    def patched():
        loaded = base()
        loaded.rules.services.kinds[kind].risks.disease_dc = disease_dc
        loaded.rules.services.kinds[kind].risks.theft_dc = theft_dc
        return loaded

    monkeypatch.setattr(game_kit, "settings", patched)


def service_call(npc_id, service_id, call_id="sv-1"):
    return {
        "id": call_id, "name": "service",
        "input": {
            "type": "service", "npc_id": npc_id, "direction": "buy",
            "service_id": service_id, "qty": 1,
        },
    }


def world_app(registry, root, turns, money=3000, npcs=()):
    bundle = new_world(
        registry, settings().rules, hero="arn", seed=7, world_id="vale-inn", saved_at=SAVED_AT
    )
    hero = bundle.heroes[0]
    hero.money_cp = money
    for npc_id, name, services, fields in npcs:
        bundle.world.npcs[npc_id] = NPC(
            id=npc_id, name=name, means=["услуги"], services=list(services),
            location_id=hero.location_id, **fields,
        )
    steps = []
    for calls, text in turns:
        steps += [{"tool_calls": calls}, {"text": text}]
    adapter = ScriptedAdapter(steps, provider="anthropic", model=OPUS)
    return make_app(registry, root, adapter, bundle=bundle, world_text=WORLD_TEXT, model=OPUS)


def conditions(app):
    return [c.id for c in hero_of(app.bundle).creature.conditions]


def sheet(app):
    return app.handle("/sheet").lines


MARA = ("mara", "Мара", ["companion_common"], {})
ILDA = ("ilda", "Ильда", ["uncurse_temple"], {})
BRUM = ("brum", "Брум", ["bath"], {})


# болезнь и храм

def sick_app(registry, root, monkeypatch):
    risks(monkeypatch, disease_dc=99, theft_dc=0)
    turns = [
        ([service_call("mara", "companion_common")], "Час прошёл."),
        ([service_call("ilda", "uncurse_temple")], "Обряд."),
    ]
    return world_app(registry, root, turns, npcs=[MARA, ILDA])


def test_failed_disease_save_makes_hero_diseased(registry, tmp_path, monkeypatch):
    app = sick_app(registry, tmp_path, monkeypatch)
    reply = app.handle("Беру компанию на час")
    assert reply.turn.committed is True
    assert reply.turn.requests == ["service"]
    assert conditions(app) == ["diseased"]
    assert hero_of(app.bundle).money_cp == 3000 - 100


def test_disease_turn_shows_save_and_sickness_lines(registry, tmp_path, monkeypatch):
    app = sick_app(registry, tmp_path, monkeypatch)
    lines = app.handle("Беру компанию на час").turn.lines
    assert any(line.startswith("Спасбросок Тел") for line in lines)
    assert f"{hero_of(app.bundle).name}: болезнь" in lines


def test_sheet_shows_sickness_after_purchase(registry, tmp_path, monkeypatch):
    app = sick_app(registry, tmp_path, monkeypatch)
    app.handle("Беру компанию на час")
    assert "Состояния: болен" in sheet(app)


def test_temple_cures_the_disease(registry, tmp_path, monkeypatch):
    app = sick_app(registry, tmp_path, monkeypatch)
    app.handle("Беру компанию на час")
    reply = app.handle("Иду в храм, плачу за очищение")
    assert reply.turn.requests == ["service"]
    assert conditions(app) == []
    assert hero_of(app.bundle).money_cp == 3000 - 100 - 2500
    assert len([line for line in reply.turn.lines if line.startswith("Болезнь снята")]) == 1
    assert not [line for line in sheet(app) if line.startswith("Состояния")]


# кража

def test_failed_theft_save_takes_part_of_the_purse(registry, tmp_path, monkeypatch):
    risks(monkeypatch, disease_dc=0, theft_dc=99)
    app = world_app(
        registry, tmp_path, [([service_call("mara", "companion_common")], "Час прошёл.")],
        money=1100, npcs=[MARA],
    )
    reply = app.handle("Беру компанию на час")
    # после оплаты 1000 мм: потеря 10-40 % = 100-400 мм
    assert 600 <= hero_of(app.bundle).money_cp <= 900
    assert any(line.startswith("Кошелёк полегчал") for line in reply.turn.lines)
    assert conditions(app) == []


def test_passed_saves_cost_only_the_price(registry, tmp_path, monkeypatch):
    risks(monkeypatch, disease_dc=0, theft_dc=0)
    app = world_app(
        registry, tmp_path, [([service_call("mara", "companion_common")], "Час прошёл.")],
        money=1100, npcs=[MARA],
    )
    reply = app.handle("Беру компанию на час")
    assert hero_of(app.bundle).money_cp == 1000
    assert conditions(app) == []
    assert not [line for line in reply.turn.lines if line.startswith("Кошелёк")]


# ревность

def test_companion_in_love_loses_attitude_and_remembers_betrayal(registry, tmp_path, monkeypatch):
    risks(monkeypatch, disease_dc=0, theft_dc=0)
    love = NpcGoal(kind="love", target="hero", since_s=0)
    lover = ("lira", "Лира", [], {"attitude": 50, "follows": "hero", "goals": [love]})
    app = world_app(
        registry, tmp_path, [([service_call("mara", "companion_common")], "Час прошёл.")],
        npcs=[MARA, lover],
    )
    reply = app.handle("Беру компанию на час")
    lira = app.bundle.world.npcs["lira"]
    assert lira.attitude == 40
    assert [e.kind for m in lira.memory for e in m.events] == ["betrayal"]
    assert any("Лира" in line and "измена раскрыта" in line for line in reply.turn.lines)


# гигиена

def smelly_app(registry, root, monkeypatch):
    risks(monkeypatch, disease_dc=0, theft_dc=0)
    turns = [
        ([advance_call(category="month"), end_scene_call()], "Месяц в пути."),
        ([skill_check_call(skill="persuasion")], "Ты пытаешься убедить."),
        ([service_call("brum", "bath")], "Ты вымылся."),
    ]
    return world_app(registry, root, turns, npcs=[BRUM])


def test_month_without_wash_makes_hero_smelly_after_scene_boundary(
    registry, tmp_path, monkeypatch
):
    app = smelly_app(registry, tmp_path, monkeypatch)
    reply = app.handle("Месяц в дороге")
    assert reply.turn.committed is True
    assert conditions(app) == ["smelly"]
    assert "Состояния: вонь" in sheet(app)


def test_persuasion_of_smelly_hero_is_rolled_with_stench_disadvantage(
    registry, tmp_path, monkeypatch
):
    app = smelly_app(registry, tmp_path, monkeypatch)
    app.handle("Месяц в дороге")
    reply = app.handle("Пытаюсь убедить стражника")
    assert reply.turn.requests == ["skill_check"]
    assert any("вонь" in line for line in reply.turn.lines)


def test_bath_washes_the_stench_away(registry, tmp_path, monkeypatch):
    app = smelly_app(registry, tmp_path, monkeypatch)
    app.handle("Месяц в дороге")
    app.handle("Пытаюсь убедить стражника")
    reply = app.handle("Иду в баню")
    assert conditions(app) == []
    assert hero_of(app.bundle).money_cp == 3000 - 10
    assert "Бонус: чист — вонь смыта" in reply.turn.lines
    assert not [line for line in sheet(app) if line.startswith("Состояния")]


def test_week_alone_is_not_enough_after_the_first_tick(registry, tmp_path, monkeypatch):
    # отсчёт идёт с первого тика: неделя пути от нуля героя ещё не пачкает
    risks(monkeypatch, disease_dc=0, theft_dc=0)
    turns = [([advance_call(category="week"), end_scene_call()], "Неделя в пути.")]
    app = world_app(registry, tmp_path, turns)
    app.handle("Неделя в дороге")
    assert conditions(app) == []
