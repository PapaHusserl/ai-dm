# Ожидаемый API (STAGE3-PLAN A8, П6а, ТЗ 4.2; решение G3б: молитва -- фраза игрока, нарратор
#   вызывает запрос):
#   Запрос pray{god_id: str} (видимый нарратору). favor героя к богу >= 6 -> accepted,
#     hero.divine.prayer_day = clock.now_s // 86400; иначе (или бог неизвестен/заморожен) --
#       rejected
#     (или Invalid для неизвестного бога) с signal_to_master, prayer_day не меняется.
#   +6 (hero.divine.prayer_day == сегодня): ближайший КРИТИЧЕСКИЙ бросок героя за день -- с
#     преимуществом
#     (два d20, берётся больший), prayer_day после этого сбрасывается (None); второй критический
#       -- без.
#     Критический момент: skill_check/saving_throw со stakes="critical". normal -- не тратит
#       молитву.
#     Новая молитва в новый день -- снова преимущество.
#   -6 (favor <= -6): первый критический бросок за день -- с помехой (два d20, меньший);
#     hero.divine.curse_day_used = сегодня; второй за тот же день -- без помехи; на следующий день
#       -- снова.
#     normal-бросок помеху не получает и день не тратит.
#   +9 вмешательство: герой на 0 HP получает убивающий удар (провал третьего спасброска от смерти):
#     d100 <= 50 при +9, <= 75 при +10 (rng.randbelow(100) + 1) -> герой жив, 1 HP, у бога
#       триггер-долг
#     (id начинается с "debt:"), бог в hero.divine.frozen, hero.divine.debts не пуст,
#     hero.divine.intervention_chapter заполнен; не чаще раза за главу. Кубик d100 бросается только
#     при favor >= 9 и доступном вмешательстве.
#     Выплата долга: set_flag debt_paid:<...> (имя берётся из условия триггера-долга) снимает
#       frozen.
import pytest
from protocol_kit import ScriptedRng, combat_request, make_bundle, make_ctx, req

from ai_dm.core.clock import DAY
from ai_dm.protocol.apply import apply
from ai_dm.protocol.decision import Decision, Invalid
from ai_dm.state.scene import SceneState
from ai_dm.state.session import ChapterState
from ai_dm.state.world import God


class DiceRng(ScriptedRng):
    # очереди граней; нехватка -- «максимум» для кубиков, которых тест не ждёт (кроме d20 и d100)
    def randbelow(self, n):
        if self.queues.get(f"d{n}") or n in (20, 100):
            return super().randbelow(n)
        self.calls.append(f"d{n}")
        return n - 1


def make_divine_ctx(registry, cfg, rng, favor=0, day=3, hp_max=None):
    bundle = make_bundle(registry)
    bundle.world.pantheon["selune"] = God(id="selune", name="Селунэ", rivals=["morrah"])
    bundle.world.pantheon["morrah"] = God(id="morrah", name="Моррах", rivals=["selune"])
    bundle.world.clock.now_s = day * DAY + 3600
    bundle.session.current_chapter = ChapterState(id="ch1", number=1)
    hero = bundle.heroes[0]
    hero.favor = {"selune": favor}
    if hp_max is not None:
        hero.creature.hp_max = hp_max
        hero.creature.hp_current = hp_max
    return make_ctx(registry, cfg, rng, bundle=bundle)


def check(stakes):
    return req("skill_check", skill="perception", category="medium", stakes=stakes)


def save(stakes):
    return req("saving_throw", ability="wis", category="medium", stakes=stakes)


# молитва

def test_pray_with_favor_six_sets_prayer_day(registry, cfg):
    ctx = make_divine_ctx(registry, cfg, DiceRng(), favor=6, day=3)
    d = apply(ctx, req("pray", god_id="selune"))
    assert isinstance(d, Decision)
    assert d.status == "accepted"
    assert ctx.hero.divine.prayer_day == 3


def test_pray_with_favor_five_is_rejected(registry, cfg):
    ctx = make_divine_ctx(registry, cfg, DiceRng(), favor=5)
    d = apply(ctx, req("pray", god_id="selune"))
    assert d.status == "rejected"
    assert d.signal_to_master
    assert ctx.hero.divine.prayer_day is None


def test_pray_to_frozen_god_is_rejected(registry, cfg):
    ctx = make_divine_ctx(registry, cfg, DiceRng(), favor=9)
    ctx.hero.divine.frozen = ["selune"]
    d = apply(ctx, req("pray", god_id="selune"))
    assert d.status == "rejected"


# +6: преимущество

def test_prayer_gives_advantage_on_first_critical_check(registry, cfg):
    ctx = make_divine_ctx(registry, cfg, DiceRng(d20=[3, 15]), favor=6)
    ctx.hero.divine.prayer_day = 3
    ctx.hero.divine.prayer_god = "selune"
    apply(ctx, check("critical"))
    assert ctx.rolls["r1"].natural == 15
    assert ctx.rng.left("d20") == 0


def test_prayer_gives_advantage_on_critical_save(registry, cfg):
    ctx = make_divine_ctx(registry, cfg, DiceRng(d20=[3, 15]), favor=6)
    ctx.hero.divine.prayer_day = 3
    ctx.hero.divine.prayer_god = "selune"
    apply(ctx, save("critical"))
    assert ctx.rolls["r1"].natural == 15


def test_prayer_is_spent_by_first_critical_roll(registry, cfg):
    ctx = make_divine_ctx(registry, cfg, DiceRng(d20=[3, 15, 4]), favor=6)
    ctx.hero.divine.prayer_day = 3
    ctx.hero.divine.prayer_god = "selune"
    apply(ctx, check("critical"))
    apply(ctx, check("critical"))
    assert ctx.rolls["r2"].natural == 4
    assert ctx.rng.left("d20") == 0


def test_normal_roll_does_not_spend_prayer(registry, cfg):
    ctx = make_divine_ctx(registry, cfg, DiceRng(d20=[7, 3, 15]), favor=6)
    ctx.hero.divine.prayer_day = 3
    ctx.hero.divine.prayer_god = "selune"
    apply(ctx, check("normal"))
    assert ctx.rng.left("d20") == 2
    apply(ctx, check("critical"))
    assert ctx.rolls["r2"].natural == 15


def test_prayer_from_yesterday_does_not_work(registry, cfg):
    ctx = make_divine_ctx(registry, cfg, DiceRng(d20=[3, 15]), favor=6, day=4)
    ctx.hero.divine.prayer_day = 3
    ctx.hero.divine.prayer_god = "selune"
    apply(ctx, check("critical"))
    assert ctx.rolls["r1"].natural == 3
    assert ctx.rng.left("d20") == 1


def test_prayer_next_day_gives_advantage_again(registry, cfg):
    ctx = make_divine_ctx(registry, cfg, DiceRng(d20=[3, 15, 5, 14]), favor=6, day=3)
    ctx.hero.divine.prayer_day = 3
    ctx.hero.divine.prayer_god = "selune"
    apply(ctx, check("critical"))
    ctx.bundle.world.clock.now_s = 4 * DAY + 3600
    apply(ctx, req("pray", god_id="selune"))
    apply(ctx, check("critical"))
    assert ctx.rolls["r2"].natural == 14
    assert ctx.rng.left("d20") == 0


def test_prayer_without_favor_six_gives_no_advantage(registry, cfg):
    ctx = make_divine_ctx(registry, cfg, DiceRng(d20=[3, 15]), favor=5)
    ctx.hero.divine.prayer_day = 3
    ctx.hero.divine.prayer_god = "selune"
    apply(ctx, check("critical"))
    assert ctx.rolls["r1"].natural == 3


def test_critical_roll_without_prayer_has_no_advantage(registry, cfg):
    ctx = make_divine_ctx(registry, cfg, DiceRng(d20=[3, 15]), favor=8)
    apply(ctx, check("critical"))
    assert ctx.rolls["r1"].natural == 3
    assert ctx.rng.left("d20") == 1


# -6: помеха

def test_curse_gives_disadvantage_on_first_critical_roll(registry, cfg):
    ctx = make_divine_ctx(registry, cfg, DiceRng(d20=[15, 3]), favor=-6)
    apply(ctx, check("critical"))
    assert ctx.rolls["r1"].natural == 3
    assert ctx.rng.left("d20") == 0
    assert ctx.hero.divine.curse_day_used == 3


def test_curse_second_critical_roll_same_day_is_plain(registry, cfg):
    ctx = make_divine_ctx(registry, cfg, DiceRng(d20=[15, 3, 12]), favor=-6)
    apply(ctx, check("critical"))
    apply(ctx, check("critical"))
    assert ctx.rolls["r2"].natural == 12
    assert ctx.rng.left("d20") == 0


def test_curse_returns_on_next_day(registry, cfg):
    ctx = make_divine_ctx(registry, cfg, DiceRng(d20=[15, 3, 15, 4]), favor=-6, day=3)
    apply(ctx, check("critical"))
    ctx.bundle.world.clock.now_s = 4 * DAY + 3600
    apply(ctx, check("critical"))
    assert ctx.rolls["r2"].natural == 4


def test_curse_does_not_touch_normal_roll(registry, cfg):
    ctx = make_divine_ctx(registry, cfg, DiceRng(d20=[15, 9, 2]), favor=-6)
    apply(ctx, check("normal"))
    assert ctx.rng.left("d20") == 2
    assert ctx.hero.divine.curse_day_used is None
    apply(ctx, check("critical"))
    assert ctx.rolls["r2"].natural == 2


def test_curse_applies_to_critical_save(registry, cfg):
    ctx = make_divine_ctx(registry, cfg, DiceRng(d20=[15, 3]), favor=-6)
    apply(ctx, save("critical"))
    assert ctx.rolls["r1"].natural == 3


def test_favor_minus_five_has_no_curse(registry, cfg):
    ctx = make_divine_ctx(registry, cfg, DiceRng(d20=[15, 3]), favor=-5)
    apply(ctx, check("critical"))
    assert ctx.rolls["r1"].natural == 15
    assert ctx.rng.left("d20") == 1


# +9: вмешательство

def dying_hero(ctx):
    hero = ctx.hero
    hero.creature.hp_max = 10
    hero.creature.hp_current = 0
    hero.creature.death_saves.failures = 2
    return hero


def deadly_blow(ctx):
    return apply(ctx, req("damage", severity="dangerous", damage_type="fire", failed_roll_ref=""))


def test_no_favor_means_hero_dies_without_intervention_roll(registry, cfg):
    ctx = make_divine_ctx(registry, cfg, DiceRng(), favor=8)
    dying_hero(ctx)
    deadly_blow(ctx)
    assert ctx.hero.status == "dead"
    assert ctx.rng.left("d100") == 0
    assert "d100" not in ctx.rng.calls


@pytest.mark.parametrize("favor, roll", [(9, 50), (9, 1), (10, 75), (10, 50)])
def test_intervention_saves_hero(registry, cfg, favor, roll):
    ctx = make_divine_ctx(registry, cfg, DiceRng(d100=[roll]), favor=favor)
    dying_hero(ctx)
    deadly_blow(ctx)
    assert ctx.hero.status != "dead"
    assert ctx.hero.creature.hp_current == 1


@pytest.mark.parametrize("favor, roll", [(9, 51), (9, 100), (10, 76), (10, 100)])
def test_intervention_roll_too_high_hero_dies(registry, cfg, favor, roll):
    ctx = make_divine_ctx(registry, cfg, DiceRng(d100=[roll]), favor=favor)
    dying_hero(ctx)
    deadly_blow(ctx)
    assert ctx.hero.status == "dead"
    assert ctx.rng.left("d100") == 0


def test_intervention_sets_debt_trigger_on_god(registry, cfg):
    ctx = make_divine_ctx(registry, cfg, DiceRng(d100=[10]), favor=9)
    dying_hero(ctx)
    deadly_blow(ctx)
    god = ctx.bundle.world.pantheon["selune"]
    assert [t.id for t in god.opportunity if t.id.startswith("debt:")]
    assert ctx.hero.divine.debts


def test_intervention_freezes_god_favor(registry, cfg):
    ctx = make_divine_ctx(registry, cfg, DiceRng(d100=[10]), favor=9)
    dying_hero(ctx)
    deadly_blow(ctx)
    assert ctx.hero.divine.frozen == ["selune"]
    d = apply(ctx, req("favor_change", target="hero", god_id="selune", delta=-1, reason="x"))
    assert d.status == "rejected"


def test_intervention_remembers_chapter(registry, cfg):
    ctx = make_divine_ctx(registry, cfg, DiceRng(d100=[10]), favor=9)
    dying_hero(ctx)
    deadly_blow(ctx)
    assert ctx.hero.divine.intervention_chapter


def test_intervention_not_twice_in_one_chapter(registry, cfg):
    ctx = make_divine_ctx(registry, cfg, DiceRng(d100=[10, 1]), favor=9)
    dying_hero(ctx)
    deadly_blow(ctx)
    ctx.hero.divine.frozen = []
    ctx.hero.favor["selune"] = 9
    dying_hero(ctx)
    deadly_blow(ctx)
    assert ctx.hero.status == "dead"
    assert ctx.rng.left("d100") == 1


def test_intervention_available_again_in_next_chapter(registry, cfg):
    ctx = make_divine_ctx(registry, cfg, DiceRng(d100=[10, 10]), favor=9)
    dying_hero(ctx)
    deadly_blow(ctx)
    ctx.hero.divine.frozen = []
    ctx.hero.favor["selune"] = 9
    ctx.bundle.session.current_chapter = ChapterState(id="ch2", number=2)
    dying_hero(ctx)
    deadly_blow(ctx)
    assert ctx.hero.status != "dead"


def intervened_ctx(registry, cfg):
    ctx = make_divine_ctx(registry, cfg, DiceRng(d100=[10]), favor=9)
    dying_hero(ctx)
    deadly_blow(ctx)
    god = ctx.bundle.world.pantheon["selune"]
    debt = [t for t in god.opportunity if t.id.startswith("debt:")][0]
    return ctx, debt.if_.name


def test_debt_paid_in_intervention_scene_is_rejected(registry, cfg):
    ctx, flag = intervened_ctx(registry, cfg)
    d = apply(ctx, req("set_flag", name=flag, value="true"))
    assert isinstance(d, Decision)
    assert d.status == "rejected"
    assert ctx.hero.divine.frozen == ["selune"]


def test_debt_paid_in_next_scene_unfreezes_god(registry, cfg):
    ctx, flag = intervened_ctx(registry, cfg)
    ctx.bundle.session.current_scene = SceneState(id="scene_2", started_at_s=0, location_id="vale")
    apply(ctx, req("set_flag", name=flag, value="true"))
    assert ctx.hero.divine.frozen == []
    d = apply(ctx, req("favor_change", target="hero", god_id="selune", delta=-1, reason="x"))
    assert d.status == "accepted"


# D3: молитва действует только от бога, которому молились

def pray_ctx(registry, cfg):
    ctx = make_divine_ctx(registry, cfg, DiceRng(d20=[3, 15]), favor=6)
    ctx.hero.favor["morrah"] = 7
    apply(ctx, req("pray", god_id="selune"))
    return ctx


def test_prayer_works_while_prayed_god_keeps_favor(registry, cfg):
    ctx = pray_ctx(registry, cfg)
    apply(ctx, check("critical"))
    assert ctx.rolls["r1"].natural == 15


def test_prayer_dies_when_prayed_god_favor_drops_below_six(registry, cfg):
    ctx = pray_ctx(registry, cfg)
    ctx.hero.favor["selune"] = 5
    apply(ctx, check("critical"))
    assert ctx.rolls["r1"].natural == 3


def test_prayer_dies_when_prayed_god_is_frozen(registry, cfg):
    ctx = pray_ctx(registry, cfg)
    ctx.hero.divine.frozen = ["selune"]
    apply(ctx, check("critical"))
    assert ctx.rolls["r1"].natural == 3


# D2: истощение 6 -- тоже путь вмешательства
# Ожидание: add_exhaustion(hero, levels, now_s=, cause=, intervene=) -- как check_three;
# при спасении степень истощения 5.

def exhaustion_case(registry, cfg, favor, roll):
    from ai_dm.rules import divine

    ctx = make_divine_ctx(registry, cfg, DiceRng(d100=[roll]), favor=favor)
    hero = ctx.hero
    hero.creature.exhaustion = 5

    def intervene(target):
        return divine.try_intervention(
            target, ctx.bundle.world, ctx.rng, ctx.cfg, ctx.bundle.session.current_chapter.id
        )

    from ai_dm.rules.exhaustion import add_exhaustion

    add_exhaustion(hero, 1, now_s=0, cause="goal", intervene=intervene)
    return ctx


def test_exhaustion_six_with_intervention_keeps_hero_alive(registry, cfg):
    ctx = exhaustion_case(registry, cfg, 9, 10)
    assert ctx.hero.status != "dead"
    assert ctx.hero.creature.exhaustion == 5


def test_exhaustion_six_with_intervention_sets_debt_and_freeze(registry, cfg):
    ctx = exhaustion_case(registry, cfg, 9, 10)
    assert ctx.hero.divine.frozen == ["selune"]
    assert ctx.hero.divine.debts


def test_exhaustion_six_without_favor_kills_hero(registry, cfg):
    ctx = make_divine_ctx(registry, cfg, DiceRng(), favor=3)
    from ai_dm.rules.exhaustion import add_exhaustion

    ctx.hero.creature.exhaustion = 5
    add_exhaustion(ctx.hero, 1, now_s=0, cause="goal")
    assert ctx.hero.status == "dead"


# M: модели не отдаётся число шкалы

def test_favor_change_result_has_no_scale_number(registry, cfg):
    ctx = make_divine_ctx(registry, cfg, DiceRng(), favor=4)
    d = apply(ctx, req("favor_change", target="hero", god_id="selune", delta=2, reason="x"))
    assert ctx.hero.favor["selune"] == 6
    assert "favor" not in d.result
    assert 6 not in d.result.values()
    assert not [line for line in d.log if "теперь 6" in line or "(6)" in line]


# D2 через defeat_outcome: последствие «истощение» при степени 5

def exhaustion_defeat(registry, cfg, favor, rng):
    ctx = make_divine_ctx(registry, cfg, rng, favor=favor)
    apply(ctx, combat_request())
    ctx.bundle.session.active_combat.outcome = "defeat_pending"
    ctx.hero.creature.exhaustion = 5
    d = apply(ctx, req("defeat_outcome", consequences=["exhaustion"]))
    return ctx, d


def test_defeat_exhaustion_six_with_intervention_keeps_hero_alive(registry, cfg):
    ctx, d = exhaustion_defeat(registry, cfg, 9, DiceRng(d100=[10]))
    assert d.status == "accepted"
    assert ctx.hero.status != "dead"
    assert ctx.hero.creature.exhaustion == 5
    assert ctx.hero.divine.frozen == ["selune"]
    assert ctx.hero.divine.debts


def test_defeat_exhaustion_six_without_favor_kills_hero(registry, cfg):
    ctx, d = exhaustion_defeat(registry, cfg, 3, DiceRng())
    assert ctx.hero.status == "dead"


# S1 (stage3-p7-review): God.season_power -- поправка шанса вмешательства по сезону, клэмп 0..100
SPRING_DAY = 35
SUMMER_DAY = 150
WINTER_DAY = 3


def season_intervention(registry, cfg, day, roll, power, favor=9):
    ctx = make_divine_ctx(registry, cfg, DiceRng(d100=[roll]), favor=favor, day=day)
    ctx.bundle.world.pantheon["selune"].season_power = power
    dying_hero(ctx)
    deadly_blow(ctx)
    return ctx


@pytest.mark.parametrize("roll, alive", [(65, True), (66, False)])
def test_spring_bonus_raises_threshold_to_65(registry, cfg, roll, alive):
    ctx = season_intervention(registry, cfg, SPRING_DAY, roll, {"весна": 15})
    assert (ctx.hero.status != "dead") is alive


@pytest.mark.parametrize("roll, alive", [(25, True), (26, False)])
def test_winter_penalty_lowers_threshold_to_25(registry, cfg, roll, alive):
    ctx = season_intervention(registry, cfg, WINTER_DAY, roll, {"зима": -25})
    assert (ctx.hero.status != "dead") is alive


def test_other_season_power_does_not_apply(registry, cfg):
    ctx = season_intervention(registry, cfg, SUMMER_DAY, 50, {"весна": 15, "зима": -25})
    assert ctx.hero.status != "dead"
    ctx = season_intervention(registry, cfg, SUMMER_DAY, 51, {"весна": 15, "зима": -25})
    assert ctx.hero.status == "dead"


def test_season_power_clamps_to_hundred(registry, cfg):
    ctx = season_intervention(registry, cfg, SPRING_DAY, 100, {"весна": 90}, favor=10)
    assert ctx.hero.status != "dead"


def test_season_power_clamps_to_zero(registry, cfg):
    ctx = season_intervention(registry, cfg, WINTER_DAY, 1, {"зима": -90})
    assert ctx.hero.status == "dead"


# Ж2 коммит 3: change_deity -- смена бога; отказы unknown_god / same_deity, +1 новому,
# хроника, журнал

def deity_ctx(registry, cfg, deity="selune"):
    ctx = make_divine_ctx(registry, cfg, DiceRng(), favor=4)
    ctx.hero.deity_id = deity
    return ctx


def change(ctx, god_id="morrah", reason="сделка с жрецом"):
    return apply(ctx, req("change_deity", god_id=god_id, reason=reason))


def test_change_deity_unknown_god_is_invalid(registry, cfg):
    ctx = deity_ctx(registry, cfg)
    d = change(ctx, "nobody")
    assert isinstance(d, Invalid)
    assert d.code == "unknown_god"
    assert ctx.hero.deity_id == "selune"


def test_change_deity_same_god_is_invalid(registry, cfg):
    ctx = deity_ctx(registry, cfg)
    d = change(ctx, "selune")
    assert isinstance(d, Invalid)
    assert d.code == "same_deity"
    assert ctx.hero.favor["selune"] == 4


def test_change_deity_sets_new_god(registry, cfg):
    ctx = deity_ctx(registry, cfg)
    d = change(ctx)
    assert isinstance(d, Decision)
    assert d.status == "accepted"
    assert ctx.hero.deity_id == "morrah"


def test_change_deity_gives_plus_one_to_new_god_without_key(registry, cfg):
    ctx = deity_ctx(registry, cfg)
    change(ctx)
    assert ctx.hero.favor["morrah"] == 1


def test_change_deity_to_god_with_favor_key_gives_no_bonus(registry, cfg):
    ctx = deity_ctx(registry, cfg)
    ctx.hero.favor["morrah"] = 2
    d = change(ctx)
    assert d.status == "accepted"
    assert ctx.hero.favor["morrah"] == 2
    assert "благосклонность" not in d.log[0]


def test_change_deity_back_to_previous_god_has_no_bonus_text(registry, cfg):
    ctx = deity_ctx(registry, cfg)
    change(ctx)
    d = change(ctx, "selune")
    assert d.status == "accepted"
    assert ctx.hero.deity_id == "selune"
    assert ctx.hero.favor["selune"] == 4
    assert d.log[0] == "Герой сменил бога: теперь Селунэ (сделка с жрецом)"
    assert ctx.bundle.chronicle.entries[-1].text == d.log[0]


def test_change_deity_old_god_without_key_gets_zero(registry, cfg):
    ctx = deity_ctx(registry, cfg)
    ctx.hero.favor.pop("selune")
    change(ctx)
    assert ctx.hero.favor["selune"] == 0


def test_change_deity_text_mentions_bonus_when_given(registry, cfg):
    ctx = deity_ctx(registry, cfg)
    d = change(ctx)
    assert "благосклонность +1" in d.log[0]
    assert "благосклонность +1" in ctx.bundle.chronicle.entries[0].text


def test_change_deity_leaves_old_god_favor(registry, cfg):
    ctx = deity_ctx(registry, cfg)
    change(ctx)
    assert ctx.hero.favor["selune"] == 4


def test_change_deity_result_has_god_id(registry, cfg):
    d = change(deity_ctx(registry, cfg))
    assert d.result == {"god_id": "morrah"}


def test_change_deity_log_names_new_god_and_reason(registry, cfg):
    d = change(deity_ctx(registry, cfg))
    assert len(d.log) == 1
    assert "Моррах" in d.log[0]
    assert "сделка с жрецом" in d.log[0]


def test_change_deity_writes_favor_chronicle_entry(registry, cfg):
    ctx = deity_ctx(registry, cfg)
    change(ctx)
    entries = [e for e in ctx.bundle.chronicle.entries if e.kind == "favor"]
    assert len(entries) == 1
    assert entries[0].refs == [ctx.hero.id, "morrah"]
    assert "Моррах" in entries[0].text
    assert "сделка с жрецом" in entries[0].text
    assert entries[0].at_s == ctx.bundle.world.clock.now_s


def test_change_deity_notes_god_in_hero_journal(registry, cfg):
    ctx = deity_ctx(registry, cfg)
    change(ctx)
    facts = [e for e in ctx.hero.knowledge if e.kind == "god" and e.ref == "morrah"]
    assert len(facts) == 1
    assert "Моррах" in facts[0].text
    assert "сделка с жрецом" in facts[0].text


@pytest.mark.parametrize("god_id", ["nobody", "selune"])
def test_rejected_change_deity_leaves_no_chronicle_or_journal(registry, cfg, god_id):
    ctx = deity_ctx(registry, cfg)
    change(ctx, god_id)
    assert ctx.bundle.chronicle.entries == []
    assert [e for e in ctx.hero.knowledge if e.kind == "god"] == []


def test_change_deity_works_for_hero_without_deity(registry, cfg):
    ctx = deity_ctx(registry, cfg, deity=None)
    d = change(ctx)
    assert d.status == "accepted"
    assert ctx.hero.deity_id == "morrah"
    assert ctx.hero.favor["morrah"] == 1


def test_without_season_power_chance_is_as_before(registry, cfg):
    ctx = season_intervention(registry, cfg, SPRING_DAY, 50, {})
    assert ctx.hero.status != "dead"
    ctx = season_intervention(registry, cfg, SPRING_DAY, 51, {})
    assert ctx.hero.status == "dead"
