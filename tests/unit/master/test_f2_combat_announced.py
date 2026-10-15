# 19ф Ф2а (docs/19F-PLAN.md п.1 Ф2а): announces_combat и тег combat_announced -- рассказ объявил
# бой («начинается бой!»), а start_combat не вызван. Только тег для репорта: служебного вызова
# и повтора хода нет.
import pytest
from game_kit import start_combat_call
from master_kit import combat_ctx, make_ctx, make_session, scripted, text_step, tools_step

from ai_dm.master.session import announces_combat
from ai_dm.protocol.apply import apply

ANNOUNCE = "Гоблин выхватывает нож, поднимая оружие.\n\n*(В этот момент начинается бой!)*"


def go(steps, tmp_path, registry, cfg, role="narrator", mode="explore"):
    adapter = scripted(steps)
    session, _, _, _ = make_session(adapter, tmp_path, role=role)
    ctx = make_ctx(registry, cfg, mode=mode)
    return adapter, session.run(ctx, "Иду.", apply, mode), ctx


# announces_combat

@pytest.mark.parametrize("text", [
    ANNOUNCE,
    "Бой начался.",
    "Бой начинается.",
    "Начинается бой!",
    "Начнётся бой.",
    "Бой начнется сейчас.",
    "Бой начнётся на рассвете.",
    "Завязывается бой.",
    "К бою!",
    "Враги рычат.\n\nВ бой!",
    "НАЧИНАЕТСЯ БОЙ",
])
def test_announces_combat_true(text):
    assert announces_combat(text) is True


@pytest.mark.parametrize("text", [
    "боярин начинается с",
    "Боярин начался с",
    "Бойня началась.",
    "Вы идёте по Бойной улице.",
    "Он не начинает бой.",
    "Где-то вдали идёт бой.",
    "Ты стоишь у двери.",
    "",
    "   ",
    "\n\n",
])
def test_announces_combat_false(text):
    assert announces_combat(text) is False


def test_announces_combat_phrase_not_in_last_paragraph_is_false():
    assert announces_combat("Начинается бой!\n\nНо потом всё стихло.") is False


def test_announces_combat_checks_last_non_empty_paragraph():
    assert announces_combat("Сцена.\n\nНачинается бой!\n\n") is True


# сессия

def test_explore_announce_without_calls_gets_tag(tmp_path, registry, cfg):
    adapter, result, _ = go([text_step(ANNOUNCE)], tmp_path, registry, cfg)
    assert result.report_tags == ["combat_announced"]
    assert len(adapter.requests) == 1


def test_announce_tag_does_not_change_narration(tmp_path, registry, cfg):
    _, result, _ = go([text_step(ANNOUNCE)], tmp_path, registry, cfg)
    assert result.narration == ANNOUNCE


def test_no_tag_when_start_combat_accepted_in_same_turn(tmp_path, registry, cfg):
    steps = [tools_step(start_combat_call()), text_step(ANNOUNCE)]
    _, result, ctx = go(steps, tmp_path, registry, cfg)
    assert "start_combat" in result.accepted
    assert ctx.bundle.session.active_combat is not None
    assert result.report_tags == []


def test_no_tag_in_explore_when_combat_is_already_active(tmp_path, registry, cfg):
    adapter = scripted([text_step(ANNOUNCE)])
    session, _, _, _ = make_session(adapter, tmp_path)
    ctx = combat_ctx(registry, cfg, "explore")
    result = session.run(ctx, "Иду.", apply, "explore")
    assert result.report_tags == []


def test_no_tag_in_combat_narrate(tmp_path, registry, cfg):
    adapter = scripted([text_step(ANNOUNCE)])
    session, _, _, _ = make_session(adapter, tmp_path)
    ctx = combat_ctx(registry, cfg, "combat_narrate")
    result = session.run(ctx, "Бью.", apply, "combat_narrate")
    assert result.report_tags == []


@pytest.mark.parametrize("role", ["world", "summarizer"])
def test_no_tag_for_other_roles(tmp_path, registry, cfg, role):
    _, result, _ = go([text_step(ANNOUNCE)], tmp_path, registry, cfg, role=role)
    assert result.report_tags == []


def test_no_tag_for_plain_text(tmp_path, registry, cfg):
    _, result, _ = go([text_step("Ты идёшь дальше.")], tmp_path, registry, cfg)
    assert result.report_tags == []
