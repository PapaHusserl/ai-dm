# Шаг 265, П2 (docs/plan-265.md, «Тесты» 12-19): обязательная цена провала вне боя.
#   Провал героя в позиции risky / desperate без цены -- «неоплаченный» (TurnContext.unpaid_fails);
#   цену закрывают damage / take_item (lost, stolen, spent) / curse / delayed_condition с
#   failed_roll_ref этого броска и принятый start_combat. Ответ броска с ценой -- price_due: true.
#   Тяжесть вреда по позиции: risky -- nuisance или dangerous, desperate -- dangerous или deadly.
import pytest
from protocol_kit import ScriptedRng, combat_request, make_ctx, req

from ai_dm.protocol.apply import apply
from ai_dm.protocol.decision import Invalid
from ai_dm.protocol.requests import parse_request

DICE = [3] * 10


def price_ctx(registry, cfg, d20=(1,), **kwargs):
    ctx = make_ctx(registry, cfg, ScriptedRng(d20=list(d20), d10=list(DICE)), **kwargs)
    ctx.bundle.session.turn_seq = 4
    return ctx


def fail(ctx, position="risky"):
    d = apply(ctx, req("skill_check", skill="persuasion", category="hard", position=position))
    return d.result["roll_ref"]


def unpaid(ctx):
    # unpaid_fails -- список roll_ref; допустимо и свойство, и метод
    value = ctx.unpaid_fails
    return list(value() if callable(value) else value)


def hit(ctx, ref, severity="dangerous"):
    return apply(
        ctx, req("damage", severity=severity, damage_type="fire", failed_roll_ref=ref)
    )


def take(ctx, ref="", why="lost", item_id="longsword"):
    return apply(ctx, req("take_item", item_id=item_id, qty=1, why=why, failed_roll_ref=ref))


# price_due в ответе броска

@pytest.mark.parametrize("position", ["risky", "desperate"])
def test_failed_check_with_price_position_has_price_due(registry, cfg, position):
    ctx = price_ctx(registry, cfg)
    d = apply(ctx, req("skill_check", skill="persuasion", category="hard", position=position))
    assert d.result["outcome"] == "fail"
    assert d.result["price_due"] is True


def test_failed_saving_throw_in_risky_has_price_due(registry, cfg):
    ctx = price_ctx(registry, cfg)
    d = apply(ctx, req("saving_throw", ability="wis", category="very_hard", position="risky"))
    assert d.result["price_due"] is True


@pytest.mark.parametrize("position", ["controlled", "risky", "desperate"])
def test_successful_check_has_no_price_due(registry, cfg, position):
    ctx = price_ctx(registry, cfg, d20=[20])
    d = apply(ctx, req("skill_check", skill="persuasion", category="easy", position=position))
    assert d.result["outcome"] == "success"
    assert "price_due" not in d.result


def test_failed_controlled_check_has_no_price_due(registry, cfg):
    ctx = price_ctx(registry, cfg)
    d = apply(ctx, req("skill_check", skill="persuasion", category="hard", position="controlled"))
    assert d.result["outcome"] == "fail"
    assert "price_due" not in d.result


def test_failed_check_without_position_has_no_price_due(registry, cfg):
    ctx = price_ctx(registry, cfg)
    d = apply(ctx, req("skill_check", skill="persuasion", category="hard"))
    assert "price_due" not in d.result


def test_fail_rescued_by_inspiration_has_no_price_due(registry, cfg):
    ctx = price_ctx(registry, cfg, d20=[1, 20])
    ctx.hero.heroic_inspiration = True
    d = apply(ctx, req("skill_check", skill="persuasion", category="medium", position="risky"))
    assert d.result["outcome"] == "success"
    assert "price_due" not in d.result


# unpaid_fails: что считается неоплаченным провалом

def test_no_rolls_means_no_unpaid_fails(registry, cfg):
    assert unpaid(price_ctx(registry, cfg)) == []


@pytest.mark.parametrize("position", ["risky", "desperate"])
def test_failed_check_with_price_position_is_unpaid(registry, cfg, position):
    ctx = price_ctx(registry, cfg)
    ref = fail(ctx, position)
    assert unpaid(ctx) == [ref]


def test_failed_save_in_risky_is_unpaid(registry, cfg):
    ctx = price_ctx(registry, cfg)
    ref = apply(
        ctx, req("saving_throw", ability="wis", category="very_hard", position="risky")
    ).result["roll_ref"]
    assert unpaid(ctx) == [ref]


def test_failed_controlled_check_is_not_unpaid(registry, cfg):
    ctx = price_ctx(registry, cfg)
    fail(ctx, "controlled")
    assert unpaid(ctx) == []


def test_failed_check_without_position_is_not_unpaid(registry, cfg):
    ctx = price_ctx(registry, cfg)
    apply(ctx, req("skill_check", skill="persuasion", category="hard"))
    assert unpaid(ctx) == []


@pytest.mark.parametrize("position", ["controlled", "risky", "desperate"])
def test_successful_check_is_not_unpaid(registry, cfg, position):
    ctx = price_ctx(registry, cfg, d20=[20])
    apply(ctx, req("skill_check", skill="persuasion", category="easy", position=position))
    assert unpaid(ctx) == []


def test_fail_rescued_by_inspiration_is_not_unpaid(registry, cfg):
    ctx = price_ctx(registry, cfg, d20=[1, 20])
    ctx.hero.heroic_inspiration = True
    apply(ctx, req("skill_check", skill="persuasion", category="medium", position="risky"))
    assert unpaid(ctx) == []


def test_offscreen_npc_fail_is_not_unpaid(registry, cfg):
    ctx = price_ctx(registry, cfg, mode="world")
    request = parse_request(
        {
            "type": "skill_check", "skill": "athletics", "category": "very_hard",
            "actor": "aldric",
        },
        "world",
    )
    d = apply(ctx, request)
    assert d.result["outcome"] == "fail"
    assert unpaid(ctx) == []


def test_two_fails_are_both_unpaid_in_order(registry, cfg):
    ctx = price_ctx(registry, cfg, d20=[1, 1])
    first = fail(ctx, "risky")
    second = fail(ctx, "desperate")
    assert unpaid(ctx) == [first, second]


def test_paying_one_of_two_fails_leaves_the_other(registry, cfg):
    ctx = price_ctx(registry, cfg, d20=[1, 1])
    first = fail(ctx, "risky")
    second = fail(ctx, "desperate")
    assert hit(ctx, first).status == "accepted"
    assert unpaid(ctx) == [second]


def test_dead_hero_holds_no_unpaid_fails(registry, cfg):
    ctx = price_ctx(registry, cfg, d20=[1, 1])
    fail(ctx, "risky")
    fail(ctx, "desperate")
    ctx.hero.status = "dead"
    assert unpaid(ctx) == []


# закрытие цены: damage, take_item, curse, delayed_condition, start_combat

@pytest.mark.parametrize("severity", ["nuisance", "dangerous"])
def test_damage_with_ref_pays_the_price(registry, cfg, severity):
    ctx = price_ctx(registry, cfg)
    ref = fail(ctx, "risky")
    assert hit(ctx, ref, severity).status == "accepted"
    assert ref in ctx.used_rolls
    assert unpaid(ctx) == []


def test_damage_without_ref_does_not_pay(registry, cfg):
    ctx = price_ctx(registry, cfg)
    ref = fail(ctx, "risky")
    apply(ctx, req("damage", severity="dangerous", damage_type="fire"))
    assert unpaid(ctx) == [ref]


def test_curse_pays_the_price(registry, cfg):
    ctx = price_ctx(registry, cfg)
    ref = fail(ctx, "desperate")
    apply(ctx, req("curse", failed_roll_ref=ref, cause="оберег"))
    assert unpaid(ctx) == []


def test_delayed_condition_for_hero_pays_the_price(registry, cfg):
    ctx = price_ctx(registry, cfg)
    ref = fail(ctx, "risky")
    d = apply(
        ctx,
        req(
            "delayed_condition", target=ctx.hero.id, condition="diseased", when="morning",
            text="Лихорадка", failed_roll_ref=ref,
        ),
    )
    assert d.status == "accepted"
    assert unpaid(ctx) == []


@pytest.mark.parametrize("why", ["lost", "stolen", "spent"])
def test_take_item_with_ref_pays_the_price(registry, cfg, why):
    ctx = price_ctx(registry, cfg)
    ref = fail(ctx, "risky")
    assert take(ctx, ref, why).status == "accepted"
    assert ref in ctx.used_rolls
    assert unpaid(ctx) == []


def test_take_item_given_does_not_spend_the_roll(registry, cfg):
    ctx = price_ctx(registry, cfg)
    ref = fail(ctx, "risky")
    assert take(ctx, ref, "given").status == "accepted"
    assert ref not in ctx.used_rolls
    assert unpaid(ctx) == [ref]


def test_take_item_without_ref_does_not_pay(registry, cfg):
    ctx = price_ctx(registry, cfg)
    ref = fail(ctx, "risky")
    assert take(ctx, "", "lost").status == "accepted"
    assert unpaid(ctx) == [ref]


def test_rejected_take_item_does_not_spend_the_roll(registry, cfg):
    ctx = price_ctx(registry, cfg)
    ref = fail(ctx, "risky")
    d = take(ctx, ref, "lost", item_id="dagger")
    assert isinstance(d, Invalid)
    assert d.code == "not_in_inventory"
    assert ref not in ctx.used_rolls
    assert unpaid(ctx) == [ref]


def test_take_item_with_ref_of_other_fail_leaves_this_one(registry, cfg):
    ctx = price_ctx(registry, cfg, d20=[1, 1])
    first = fail(ctx, "risky")
    second = fail(ctx, "risky")
    take(ctx, second, "lost")
    assert unpaid(ctx) == [first]


def test_accepted_start_combat_pays_all_fails_of_the_turn(registry, cfg):
    ctx = price_ctx(registry, cfg, d20=[1, 1])
    fail(ctx, "risky")
    fail(ctx, "desperate")
    assert apply(ctx, combat_request()).status == "accepted"
    assert unpaid(ctx) == []


def test_rejected_start_combat_does_not_pay(registry, cfg):
    ctx = price_ctx(registry, cfg)
    ref = fail(ctx, "risky")
    d = apply(ctx, combat_request(enemies=[], groups=[]))
    assert isinstance(d, Invalid) or d.status != "accepted"
    assert ctx.bundle.session.active_combat is None
    assert unpaid(ctx) == [ref]


# один бросок -- одна цена

def test_second_curse_with_same_ref_is_rejected(registry, cfg):
    ctx = price_ctx(registry, cfg)
    ref = fail(ctx, "desperate")
    assert hit(ctx, ref).status == "accepted"
    d = apply(ctx, req("curse", failed_roll_ref=ref, cause="оберег"))
    assert d.status == "rejected"
    assert d.report_tag == "curse_needs_fail"


# тяжесть вреда по позиции проваленного броска (решение 13)

@pytest.mark.parametrize(
    ("position", "asked", "applied", "status"),
    [
        ("risky", "nuisance", "nuisance", "accepted"),
        ("risky", "dangerous", "dangerous", "accepted"),
        ("risky", "deadly", "dangerous", "clamped"),
        ("desperate", "nuisance", "dangerous", "clamped"),
        ("desperate", "dangerous", "dangerous", "accepted"),
        ("desperate", "deadly", "deadly", "accepted"),
    ],
)
def test_damage_severity_follows_the_position_band(
    registry, cfg, position, asked, applied, status
):
    ctx = price_ctx(registry, cfg)
    ref = fail(ctx, position)
    d = hit(ctx, ref, asked)
    assert d.status == status
    assert d.result["severity"] == applied


def test_deadly_after_controlled_fail_is_cut_to_dangerous_and_spends_the_roll(registry, cfg):
    ctx = price_ctx(registry, cfg)
    ref = fail(ctx, "controlled")
    d = hit(ctx, ref, "deadly")
    assert d.status == "clamped"
    assert d.result["severity"] == "dangerous"
    assert ref in ctx.used_rolls


def test_clamped_by_band_still_spends_the_roll(registry, cfg):
    ctx = price_ctx(registry, cfg)
    ref = fail(ctx, "risky")
    assert hit(ctx, ref, "deadly").status == "clamped"
    assert ref in ctx.used_rolls
    assert unpaid(ctx) == []


def test_clamped_by_band_has_limit_exceeded_tag_and_signal(registry, cfg):
    ctx = price_ctx(registry, cfg)
    ref = fail(ctx, "desperate")
    d = hit(ctx, ref, "nuisance")
    assert d.report_tag == "limit-exceeded"
    assert d.signal_to_master


def test_deadly_without_ref_is_cut_to_dangerous(registry, cfg):
    ctx = price_ctx(registry, cfg)
    d = apply(ctx, req("damage", severity="deadly", damage_type="fire"))
    assert d.status == "clamped"
    assert d.result["severity"] == "dangerous"
