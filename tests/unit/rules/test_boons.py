# У1 П1 (docs/plan-u1.md): rules/boons.py -- бонусы платных услуг.
#   BOONS: id -> (название, фраза «уже действует»); groomed «ухожен», inspired «вдохновение»,
#       washed «чист».
#   grant_boon(ctx, boon_id, npc) -> (строка лога, выдан ли):
#     groomed -- ActiveEffect(id="groomed", kind="modifier", source="service:<npc>",
#       params {target ability_check, ability cha, dice 1d4, consume True}),
#       Expiry(seconds, now_s + 86400); при живом groomed -- не удваивается, лог «уже действует»;
#       истёкший groomed заменяется.
#     inspired -- hero.heroic_inspiration = True; уже True -- «уже воодушевлён», выдан False.
#     washed -- флаг washed:<hero> = now_s.
from protocol_kit import ScriptedRng, make_ctx, req

from ai_dm.core.boon_ids import BOON_IDS
from ai_dm.protocol.apply import apply
from ai_dm.rules.boons import BOONS, grant_boon
from ai_dm.rules.hygiene import washed_at
from ai_dm.state.creature import ActiveEffect, AppliedCondition, Expiry
from ai_dm.state.world import NPC

DAY = 86400


def make(registry, cfg, now_s=1000, **kwargs):
    ctx = make_ctx(registry, cfg, **kwargs)
    ctx.bundle.world.clock.advance(now_s - ctx.bundle.world.clock.now_s)
    npc = NPC(id="tobb", name="Тобб", means=["цирюльник"], location_id="vale")
    return ctx, npc


def grooms(ctx):
    return [e for e in ctx.hero.creature.active_effects if e.id == "groomed"]


def test_boon_ids_match_boons_table():
    assert set(BOON_IDS) == set(BOONS)


def test_boons_have_names_and_already_phrases():
    assert BOONS["groomed"][0] == "ухожен"
    assert BOONS["inspired"][0] == "вдохновение"
    assert BOONS["washed"][0] == "чист"
    assert BOONS["groomed"][1] == "уже действует"
    assert BOONS["inspired"][1] == "уже воодушевлён"


def test_groomed_adds_charisma_check_die_effect(registry, cfg):
    ctx, npc = make(registry, cfg)
    line, granted = grant_boon(ctx, "groomed", npc)
    [effect] = grooms(ctx)
    assert granted is True
    assert effect.kind == "modifier"
    assert effect.source == "service:tobb"
    assert effect.params == {
        "target": "ability_check", "ability": "cha", "dice": "1d4", "consume": True,
    }
    assert line == "Бонус: ухожен"


def test_groomed_expires_in_a_day(registry, cfg):
    ctx, npc = make(registry, cfg, now_s=5000)
    grant_boon(ctx, "groomed", npc)
    expires = grooms(ctx)[0].expires
    assert (expires.kind, expires.value) == ("seconds", 5000 + DAY)


def test_groomed_again_while_alive_is_not_doubled(registry, cfg):
    ctx, npc = make(registry, cfg)
    grant_boon(ctx, "groomed", npc)
    line, granted = grant_boon(ctx, "groomed", npc)
    assert granted is False
    assert len(grooms(ctx)) == 1
    assert "уже действует" in line
    assert "ухожен" in line


def test_groomed_again_keeps_original_expiry(registry, cfg):
    ctx, npc = make(registry, cfg, now_s=1000)
    grant_boon(ctx, "groomed", npc)
    ctx.bundle.world.clock.advance(3600)
    grant_boon(ctx, "groomed", npc)
    assert grooms(ctx)[0].expires.value == 1000 + DAY


def test_expired_groomed_is_replaced_not_kept(registry, cfg):
    ctx, npc = make(registry, cfg, now_s=1000)
    ctx.hero.creature.active_effects.append(
        ActiveEffect(
            id="groomed", source="service:old", kind="modifier",
            params={"target": "ability_check", "dice": "1d4", "consume": True},
            expires=Expiry(kind="seconds", value=900),
        )
    )
    _line, granted = grant_boon(ctx, "groomed", npc)
    [effect] = grooms(ctx)
    assert granted is True
    assert effect.source == "service:tobb"
    assert effect.expires.value == 1000 + DAY


def test_groomed_keeps_other_effects(registry, cfg):
    ctx, npc = make(registry, cfg)
    ctx.hero.creature.active_effects.append(
        ActiveEffect(id="bless", source="x", kind="spell", params={})
    )
    grant_boon(ctx, "groomed", npc)
    assert [e.id for e in ctx.hero.creature.active_effects] == ["bless", "groomed"]


def test_inspired_sets_heroic_inspiration(registry, cfg):
    ctx, npc = make(registry, cfg)
    ctx.hero.heroic_inspiration = False
    line, granted = grant_boon(ctx, "inspired", npc)
    assert granted is True
    assert ctx.hero.heroic_inspiration is True
    assert line == "Бонус: вдохновение"


def test_inspired_when_already_inspired_is_not_granted(registry, cfg):
    ctx, npc = make(registry, cfg)
    ctx.hero.heroic_inspiration = True
    line, granted = grant_boon(ctx, "inspired", npc)
    assert granted is False
    assert ctx.hero.heroic_inspiration is True
    assert "уже воодушевлён" in line


def test_inspired_adds_no_active_effect(registry, cfg):
    ctx, npc = make(registry, cfg)
    grant_boon(ctx, "inspired", npc)
    assert ctx.hero.creature.active_effects == []


def test_washed_marks_hero_washed_now(registry, cfg):
    ctx, npc = make(registry, cfg, now_s=4321)
    line, granted = grant_boon(ctx, "washed", npc)
    assert granted is True
    assert washed_at(ctx.bundle.world, ctx.hero.id) == 4321
    assert line == "Бонус: чист"


def test_washed_again_moves_the_mark(registry, cfg):
    ctx, npc = make(registry, cfg, now_s=100)
    grant_boon(ctx, "washed", npc)
    ctx.bundle.world.clock.advance(500)
    grant_boon(ctx, "washed", npc)
    assert washed_at(ctx.bundle.world, ctx.hero.id) == 600


def test_washed_adds_no_active_effect(registry, cfg):
    ctx, npc = make(registry, cfg)
    grant_boon(ctx, "washed", npc)
    assert ctx.hero.creature.active_effects == []


# У1 П3: washed снимает «вонь»

def smelly_ctx(registry, cfg, *others):
    ctx, npc = make(registry, cfg, now_s=4321)
    conditions = ctx.hero.creature.conditions
    conditions.extend(AppliedCondition(id=c) for c in others)
    conditions.append(AppliedCondition(id="smelly", source="hygiene"))
    return ctx, npc


def test_washed_removes_smelly(registry, cfg):
    ctx, npc = smelly_ctx(registry, cfg)
    grant_boon(ctx, "washed", npc)
    assert ctx.hero.creature.conditions == []


def test_washed_with_smelly_says_stench_is_washed_off(registry, cfg):
    ctx, npc = smelly_ctx(registry, cfg)
    line, granted = grant_boon(ctx, "washed", npc)
    assert granted is True
    assert line == "Бонус: чист — вонь смыта"


def test_washed_with_smelly_still_marks_the_time(registry, cfg):
    ctx, npc = smelly_ctx(registry, cfg)
    grant_boon(ctx, "washed", npc)
    assert washed_at(ctx.bundle.world, ctx.hero.id) == 4321


def test_washed_keeps_other_conditions(registry, cfg):
    ctx, npc = smelly_ctx(registry, cfg, "poisoned", "cursed")
    grant_boon(ctx, "washed", npc)
    assert [c.id for c in ctx.hero.creature.conditions] == ["poisoned", "cursed"]


def test_washed_without_smelly_line_has_no_stench_note(registry, cfg):
    ctx, npc = make(registry, cfg)
    ctx.hero.creature.conditions.append(AppliedCondition(id="poisoned"))
    line, _granted = grant_boon(ctx, "washed", npc)
    assert line == "Бонус: чист"
    assert [c.id for c in ctx.hero.creature.conditions] == ["poisoned"]


def test_groomed_does_not_remove_smelly(registry, cfg):
    ctx, npc = smelly_ctx(registry, cfg)
    grant_boon(ctx, "groomed", npc)
    assert [c.id for c in ctx.hero.creature.conditions] == ["smelly"]


def test_inspired_does_not_remove_smelly(registry, cfg):
    ctx, npc = smelly_ctx(registry, cfg)
    grant_boon(ctx, "inspired", npc)
    assert [c.id for c in ctx.hero.creature.conditions] == ["smelly"]


# Бонус в связке с проверкой Харизмы (конвейер бросков)

def test_groomed_adds_d4_to_charisma_check_and_is_consumed(registry, cfg):
    ctx, npc = make(registry, cfg)
    grant_boon(ctx, "groomed", npc)
    ctx.rng = ScriptedRng(d20=[10], d4=[3])
    d = apply(ctx, req("skill_check", skill="persuasion", category="medium"))
    assert "ухожен" in d.log[0]
    assert grooms(ctx) == []


def test_groomed_is_not_used_by_strength_check(registry, cfg):
    ctx, npc = make(registry, cfg)
    grant_boon(ctx, "groomed", npc)
    ctx.rng = ScriptedRng(d20=[10])
    apply(ctx, req("skill_check", skill="athletics", category="medium"))
    assert len(grooms(ctx)) == 1
