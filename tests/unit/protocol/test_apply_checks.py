# Ожидаемый API: ai_dm.protocol.apply.apply(ctx, request) -- см. контракт в protocol_kit.py.
# skill_check / saving_throw (ТЗ 2.1, 2.3): СЛ только категорией (очень лёгкая 5 ... почти
# невозможная 30), бросает движок через rules.checks, бросок кладётся в журнал хода (roll_ref),
# position (controlled/risky/desperate) попадает в tags броска (RollResult.tags["position"]),
# desperate -- ещё critical_moment, строка броска -- первая в
# Decision.log, rng движется только броском движка.
import pytest
from protocol_kit import ScriptedRng, dump, make_ctx, req

from ai_dm.protocol.apply import apply
from ai_dm.protocol.decision import Decision

DCS = [
    ("very_easy", 5), ("easy", 10), ("medium", 15), ("hard", 20), ("very_hard", 25),
    ("nearly_impossible", 30),
]


@pytest.mark.parametrize("category, dc", DCS)
def test_skill_check_translates_category_to_dc(category, dc, registry, cfg):
    ctx = make_ctx(registry, cfg, ScriptedRng(d20=[10]))
    d = apply(ctx, req("skill_check", skill="athletics", category=category))
    assert isinstance(d, Decision)
    assert d.status == "accepted"
    assert d.result["dc"] == dc
    assert ctx.rolls[d.result["roll_ref"]].dc == dc


@pytest.mark.parametrize("category, dc", DCS)
def test_saving_throw_translates_category_to_dc(category, dc, registry, cfg):
    ctx = make_ctx(registry, cfg, ScriptedRng(d20=[10]))
    d = apply(ctx, req("saving_throw", ability="con", category=category))
    assert d.status == "accepted"
    assert d.result["dc"] == dc


def test_skill_check_success_outcome(registry, cfg):
    ctx = make_ctx(registry, cfg, ScriptedRng(d20=[20]))
    d = apply(ctx, req("skill_check", skill="athletics", category="medium"))
    assert d.result["outcome"] == "success"
    assert ctx.rolls["r1"].outcome == "success"


def test_skill_check_fail_outcome(registry, cfg):
    ctx = make_ctx(registry, cfg, ScriptedRng(d20=[1]))
    d = apply(ctx, req("skill_check", skill="persuasion", category="medium"))
    assert d.result["outcome"] == "fail"


def test_failed_check_is_still_accepted(registry, cfg):
    ctx = make_ctx(registry, cfg, ScriptedRng(d20=[1]))
    d = apply(ctx, req("skill_check", skill="persuasion", category="very_hard"))
    assert d.status == "accepted"
    assert d.report_tag is None


def test_skill_check_total_matches_roll(registry, cfg):
    ctx = make_ctx(registry, cfg, ScriptedRng(d20=[12]))
    d = apply(ctx, req("skill_check", skill="athletics", category="easy"))
    assert d.result["total"] == ctx.rolls["r1"].total


def test_skill_check_roll_line_is_first_log_line(registry, cfg):
    ctx = make_ctx(registry, cfg, ScriptedRng(d20=[12]))
    d = apply(ctx, req("skill_check", skill="athletics", category="easy"))
    assert d.log[0] == ctx.rolls["r1"].log.text
    assert "против СЛ 10" in d.log[0]


def test_skill_check_uses_exactly_one_d20(registry, cfg):
    rng = ScriptedRng(d20=[12, 13])
    ctx = make_ctx(registry, cfg, rng)
    apply(ctx, req("skill_check", skill="athletics", category="easy"))
    assert rng.calls == ["d20"]


def test_check_moves_rng_draws(registry, cfg):
    ctx = make_ctx(registry, cfg)
    before = ctx.rng.draws
    apply(ctx, req("skill_check", skill="athletics", category="easy"))
    assert ctx.rng.draws > before


@pytest.mark.parametrize("position", ["controlled", "risky", "desperate"])
def test_position_is_passed_to_roll_tags(position, registry, cfg):
    ctx = make_ctx(registry, cfg, ScriptedRng(d20=[10]))
    apply(ctx, req("skill_check", skill="stealth", category="hard", position=position))
    assert ctx.rolls["r1"].tags["position"] == position


@pytest.mark.parametrize("position", ["controlled", "risky", "desperate"])
def test_saving_throw_position_is_passed_to_roll_tags(position, registry, cfg):
    ctx = make_ctx(registry, cfg, ScriptedRng(d20=[10]))
    apply(ctx, req("saving_throw", ability="dex", category="hard", position=position))
    assert ctx.rolls["r1"].tags["position"] == position


def test_desperate_check_has_critical_moment_tag(registry, cfg):
    ctx = make_ctx(registry, cfg, ScriptedRng(d20=[10]))
    apply(ctx, req("skill_check", skill="stealth", category="hard", position="desperate"))
    assert ctx.rolls["r1"].tags["critical_moment"] is True


def test_desperate_save_has_critical_moment_tag(registry, cfg):
    ctx = make_ctx(registry, cfg, ScriptedRng(d20=[10]))
    apply(ctx, req("saving_throw", ability="dex", category="hard", position="desperate"))
    assert ctx.rolls["r1"].tags["critical_moment"] is True


@pytest.mark.parametrize("position", ["controlled", "risky"])
def test_non_desperate_check_has_no_critical_moment_tag(position, registry, cfg):
    ctx = make_ctx(registry, cfg, ScriptedRng(d20=[10]))
    apply(ctx, req("skill_check", skill="stealth", category="hard", position=position))
    assert "critical_moment" not in ctx.rolls["r1"].tags


def test_no_position_means_controlled_tag(registry, cfg):
    ctx = make_ctx(registry, cfg, ScriptedRng(d20=[10]))
    apply(ctx, req("skill_check", skill="stealth", category="hard"))
    assert ctx.rolls["r1"].tags["position"] == "controlled"


def test_no_stakes_tag_in_roll(registry, cfg):
    ctx = make_ctx(registry, cfg, ScriptedRng(d20=[10]))
    apply(ctx, req("skill_check", skill="stealth", category="hard", position="risky"))
    assert "stakes" not in ctx.rolls["r1"].tags


@pytest.mark.parametrize("position", ["controlled", "risky", "desperate"])
def test_roll_result_has_position(position, registry, cfg):
    ctx = make_ctx(registry, cfg, ScriptedRng(d20=[10]))
    d = apply(ctx, req("skill_check", skill="stealth", category="hard", position=position))
    assert d.result["position"] == position


def test_saving_throw_result_has_position(registry, cfg):
    ctx = make_ctx(registry, cfg, ScriptedRng(d20=[10]))
    d = apply(ctx, req("saving_throw", ability="dex", category="hard", position="risky"))
    assert d.result["position"] == "risky"


def test_roll_line_has_position_word(registry, cfg):
    ctx = make_ctx(registry, cfg, ScriptedRng(d20=[7]))
    d = apply(ctx, req("skill_check", skill="stealth", category="medium", position="risky"))
    assert "рискованно:" in d.log[0]


def test_saving_throw_roll_is_a_save(registry, cfg):
    ctx = make_ctx(registry, cfg, ScriptedRng(d20=[10]))
    apply(ctx, req("saving_throw", ability="wis", category="easy"))
    assert ctx.rolls["r1"].kind == "save"


def test_check_does_not_change_hero_or_world(registry, cfg):
    ctx = make_ctx(registry, cfg, ScriptedRng(d20=[10]))
    before = dump(ctx)
    apply(ctx, req("skill_check", skill="athletics", category="easy"))
    assert dump(ctx) == before


def test_failed_check_spends_inspiration_and_adds_spent_line(registry, cfg):
    ctx = make_ctx(registry, cfg, ScriptedRng(d20=[1, 20]))
    ctx.hero.heroic_inspiration = True
    d = apply(ctx, req("skill_check", skill="athletics", category="medium"))
    assert ctx.hero.heroic_inspiration is False
    assert d.result["outcome"] == "success"
    assert len(d.log) == 2
    assert "→ вдохновение 20" in d.log[0]
    assert d.log[1] == "Вдохновение потрачено"


def test_failed_save_spends_inspiration_and_adds_spent_line(registry, cfg):
    ctx = make_ctx(registry, cfg, ScriptedRng(d20=[1, 20]))
    ctx.hero.heroic_inspiration = True
    d = apply(ctx, req("saving_throw", ability="con", category="medium"))
    assert ctx.hero.heroic_inspiration is False
    assert d.log[1:] == ["Вдохновение потрачено"]


def test_successful_check_keeps_inspiration_and_has_one_log_line(registry, cfg):
    ctx = make_ctx(registry, cfg, ScriptedRng(d20=[20]))
    ctx.hero.heroic_inspiration = True
    d = apply(ctx, req("skill_check", skill="athletics", category="medium"))
    assert ctx.hero.heroic_inspiration is True
    assert d.log == [ctx.rolls["r1"].log.text]


def test_failed_check_without_inspiration_has_one_log_line(registry, cfg):
    ctx = make_ctx(registry, cfg, ScriptedRng(d20=[1]))
    d = apply(ctx, req("skill_check", skill="athletics", category="medium"))
    assert len(d.log) == 1


def test_two_checks_give_two_refs(registry, cfg):
    ctx = make_ctx(registry, cfg, ScriptedRng(d20=[10, 15]))
    a = apply(ctx, req("skill_check", skill="athletics", category="easy"))
    b = apply(ctx, req("skill_check", skill="athletics", category="easy"))
    assert a.result["roll_ref"] != b.result["roll_ref"]
