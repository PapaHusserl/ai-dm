# 19ф Ф2б (docs/19F-PLAN.md п.1 Ф2б): MasterSession.choices_missing -- приписка CHOICES_ASK на ходу,
# которым бой закончился (victory / fled / ended_by_master) в режиме combat_narrate.
from types import SimpleNamespace

import pytest
from game_kit import start_combat_call
from master_kit import combat_ctx, make_ctx, make_session, scripted, text_step, tools_step

from ai_dm.master.session import CHOICES_ASK, COMBAT_OVER
from ai_dm.protocol.apply import apply

QUESTION = "Последний гоблин падает.\n\nЧто ты делаешь дальше?"
OFFER = {
    "id": "o1", "name": "offer_choices",
    "input": {"type": "offer_choices", "choices": ["Обыскать", "Уйти"]},
}


def result_of(narration=QUESTION, accepted=()):
    return SimpleNamespace(narration=narration, accepted=list(accepted))


def missing(registry, cfg, tmp_path, mode, outcome=None, role="narrator", **kw):
    session, _, _, _ = make_session(scripted([]), tmp_path, role=role)
    ctx = combat_ctx(registry, cfg, mode, outcome=outcome)
    return session.choices_missing(ctx, result_of(**kw), mode)


def test_combat_over_outcomes_are_victory_fled_ended_by_master():
    assert set(COMBAT_OVER) == {"victory", "fled", "ended_by_master"}


@pytest.mark.parametrize("outcome", ["victory", "fled", "ended_by_master"])
def test_missing_after_finished_combat(registry, cfg, tmp_path, outcome):
    assert missing(registry, cfg, tmp_path, "combat_narrate", outcome) is True


@pytest.mark.parametrize("outcome", [None, "hero_dying", "defeat_pending", "hero_dead"])
def test_not_missing_while_combat_goes_on_or_hero_is_down(registry, cfg, tmp_path, outcome):
    assert missing(registry, cfg, tmp_path, "combat_narrate", outcome) is False


def test_not_missing_in_combat_classify_even_after_victory(registry, cfg, tmp_path):
    assert missing(registry, cfg, tmp_path, "combat_classify", "victory") is False


def test_not_missing_when_offer_choices_accepted(registry, cfg, tmp_path):
    assert missing(
        registry, cfg, tmp_path, "combat_narrate", "victory", accepted=["offer_choices"]
    ) is False


def test_not_missing_when_text_has_no_question(registry, cfg, tmp_path):
    assert missing(
        registry, cfg, tmp_path, "combat_narrate", "victory", narration="Гоблины мертвы."
    ) is False


def test_not_missing_for_other_role(registry, cfg, tmp_path):
    assert missing(registry, cfg, tmp_path, "combat_narrate", "victory", role="world") is False


def test_explore_without_combat_is_missing_as_before(registry, cfg, tmp_path):
    session, _, _, _ = make_session(scripted([]), tmp_path)
    ctx = make_ctx(registry, cfg, mode="explore")
    assert session.choices_missing(ctx, result_of(), "explore") is True


def test_explore_with_active_combat_is_not_missing(registry, cfg, tmp_path):
    assert missing(registry, cfg, tmp_path, "explore", None) is False


@pytest.mark.parametrize("mode", ["hero_chat", "hero_sheet", "import", "world_tick"])
def test_other_modes_without_bundle_do_not_crash(tmp_path, mode):
    # режимы вне CHOICE_MODES: ранний return до чтения ctx.bundle
    session, _, _, _ = make_session(scripted([]), tmp_path)
    assert session.choices_missing(SimpleNamespace(), result_of(), mode) is False


# сессия: прогон хода

def narrate(steps, registry, cfg, tmp_path, outcome="victory"):
    adapter = scripted(steps)
    session, _, _, _ = make_session(adapter, tmp_path)
    ctx = combat_ctx(registry, cfg, "combat_narrate", outcome=outcome)
    result = session.run(ctx, "Бью.", apply, "combat_narrate")
    return adapter, result, ctx


def test_victory_question_makes_one_more_call_with_ask(registry, cfg, tmp_path):
    adapter, _, _ = narrate([text_step(QUESTION), tools_step(OFFER)], registry, cfg, tmp_path)
    assert len(adapter.requests) == 2
    assert adapter.requests[1].messages[-1].content[0].text == CHOICES_ASK


def test_victory_ask_offers_choices_and_tags_turn(registry, cfg, tmp_path):
    _, result, ctx = narrate([text_step(QUESTION), tools_step(OFFER)], registry, cfg, tmp_path)
    assert result.report_tags == ["choices_retry"]
    assert ctx.bundle.session.offered_choices == ["Обыскать", "Уйти"]
    assert [r.type for r in result.requests] == ["offer_choices"]


def test_victory_ask_answer_by_text_keeps_turn_without_menu(registry, cfg, tmp_path):
    adapter, result, ctx = narrate(
        [text_step(QUESTION), text_step("Не буду.")], registry, cfg, tmp_path
    )
    assert len(adapter.requests) == 2
    assert result.narration == QUESTION
    assert ctx.bundle.session.offered_choices == []


def test_ongoing_combat_question_is_not_asked(registry, cfg, tmp_path):
    adapter, result, _ = narrate(
        [text_step(QUESTION), text_step("лишний")], registry, cfg, tmp_path, outcome=None
    )
    assert len(adapter.requests) == 1
    assert result.report_tags == []


def test_explore_turn_that_starts_combat_is_not_asked(registry, cfg, tmp_path):
    adapter = scripted([tools_step(start_combat_call()), text_step(QUESTION), text_step("x")])
    session, _, _, _ = make_session(adapter, tmp_path)
    ctx = make_ctx(registry, cfg, mode="explore")
    result = session.run(ctx, "Нападаю.", apply, "explore")
    assert ctx.bundle.session.active_combat is not None
    assert "choices_retry" not in result.report_tags
    assert len(adapter.requests) == 2
