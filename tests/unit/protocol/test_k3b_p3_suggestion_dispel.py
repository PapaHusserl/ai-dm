# К3б П3 (docs/plan-k3b.md, «Тесты» П3, решения 6, 7; BACKLOG 257): Внушение и Развеивание магии
# вне боя в cast_spell. Внушение на NPC с состоянием здоровья: спасбросок Мдр, провал -- charmed и
# incapacitated на 8 часов; Развеивание (3 круг) снимает их с NPC.
import sys
from pathlib import Path

import game_kit  # noqa: F401  (добавляет в sys.path соседние kit-ы)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "combat"))

from combat_kit import ScriptedRng  # noqa: E402
from protocol_kit import make_ctx, req  # noqa: E402
from test_utility_spells import put_npc, wiz  # noqa: E402

from ai_dm.protocol.apply import apply  # noqa: E402
from ai_dm.protocol.decision import Invalid  # noqa: E402
from ai_dm.state.creature import AppliedCondition, Concentration, Expiry  # noqa: E402

HOUR = 3600


def cast_on(registry, cfg, bundle, spell_id, circle, rng=None, target="orc"):
    ctx = make_ctx(registry, cfg, rng=rng, bundle=bundle)
    extra = {} if target is None else {"target": target}
    return apply(ctx, req("cast_spell", spell_id=spell_id, circle=circle, **extra))


def suggested_orc(registry, cfg, d20=(1, 1)):
    bundle = wiz(registry, "suggestion", "dispel_magic")
    npc = put_npc(bundle)
    result = cast_on(registry, cfg, bundle, "suggestion", 2, ScriptedRng(d20=list(d20)))
    assert not isinstance(result, Invalid)
    assert "charmed" in ids_of(npc), "Внушение не легло на NPC: нечего развеивать"
    return bundle, npc


def ids_of(npc):
    return [c.id for c in npc.creature.conditions]


def test_suggestion_failed_save_charms_the_npc(registry, cfg):
    _, npc = suggested_orc(registry, cfg)
    assert "charmed" in ids_of(npc)


def test_suggestion_failed_save_makes_the_npc_incapacitated(registry, cfg):
    _, npc = suggested_orc(registry, cfg)
    assert "incapacitated" in ids_of(npc)


def test_suggestion_charm_is_bound_to_the_heros_concentration(registry, cfg):
    bundle, npc = suggested_orc(registry, cfg)
    charmed = [c for c in npc.creature.conditions if c.id == "charmed"][0]
    assert (charmed.expires.kind, charmed.expires.owner) == ("concentration", bundle.heroes[0].id)


def test_suggestion_concentration_lasts_eight_hours(registry, cfg):
    bundle = wiz(registry, "suggestion")
    put_npc(bundle)
    start = bundle.world.clock.now_s
    cast_on(registry, cfg, bundle, "suggestion", 2, ScriptedRng(d20=[1, 1]))
    assert bundle.heroes[0].creature.concentration.until_s == start + 8 * HOUR


def test_suggestion_charm_is_gone_after_eight_hours(registry, cfg):
    bundle, npc = suggested_orc(registry, cfg)
    bundle.world.clock.advance(8 * HOUR + 1)
    ctx = make_ctx(registry, cfg, bundle=bundle)
    apply(ctx, req("advance_time", category="hour"))
    assert "charmed" not in ids_of(npc)


def test_suggestion_conditions_outside_combat_name_the_spell_as_source(registry, cfg):
    _, npc = suggested_orc(registry, cfg)
    sources = {c.id: c.source for c in npc.creature.conditions}
    assert (sources["charmed"], sources["incapacitated"]) == ("suggestion", "suggestion")


def test_dispel_outside_combat_ends_the_heros_concentration(registry, cfg):
    bundle, _ = suggested_orc(registry, cfg)
    cast_on(registry, cfg, bundle, "dispel_magic", 3)
    assert bundle.heroes[0].creature.concentration is None


def test_suggestion_passed_save_leaves_the_npc_free(registry, cfg):
    bundle = wiz(registry, "suggestion")
    npc = put_npc(bundle)
    cast_on(registry, cfg, bundle, "suggestion", 2, ScriptedRng(d20=[20, 20]))
    assert ids_of(npc) == []


def test_dispel_outside_combat_removes_the_charm(registry, cfg):
    bundle, npc = suggested_orc(registry, cfg)
    result = cast_on(registry, cfg, bundle, "dispel_magic", 3)
    assert not isinstance(result, Invalid)
    assert "charmed" not in ids_of(npc)


def test_dispel_outside_combat_removes_the_incapacitation(registry, cfg):
    bundle, npc = suggested_orc(registry, cfg)
    cast_on(registry, cfg, bundle, "dispel_magic", 3)
    assert "incapacitated" not in ids_of(npc)


def test_dispel_outside_combat_spends_a_third_circle_slot(registry, cfg):
    bundle, _ = suggested_orc(registry, cfg)
    before = bundle.heroes[0].creature.resources["spell_slot:3"].current
    cast_on(registry, cfg, bundle, "dispel_magic", 3)
    assert bundle.heroes[0].creature.resources["spell_slot:3"].current == before - 1


def test_dispel_outside_combat_logs_what_it_removed(registry, cfg):
    bundle, _ = suggested_orc(registry, cfg)
    result = cast_on(registry, cfg, bundle, "dispel_magic", 3)
    assert any("Внушение" in line for line in result.log)


def charmed_by(registry, cfg, owner):
    # герой держит Внушение; на NPC такое же состояние Внушения с владельцем owner; Рассеивание
    bundle = wiz(registry, "dispel_magic")
    hero = bundle.heroes[0]
    hero.creature.concentration = Concentration(spell_id="suggestion", circle=2)
    npc = put_npc(bundle)
    npc.creature.conditions.append(
        AppliedCondition(
            id="charmed", source="suggestion", expires=Expiry(kind="concentration", owner=owner),
        )
    )
    result = cast_on(registry, cfg, bundle, "dispel_magic", 3)
    assert not isinstance(result, Invalid)
    return hero, npc


def test_dispel_of_a_foreign_copy_of_the_spell_keeps_the_heros_concentration(registry, cfg):
    hero, npc = charmed_by(registry, cfg, "stranger")
    assert "charmed" not in ids_of(npc)
    assert hero.creature.concentration.spell_id == "suggestion"


def test_dispel_of_the_heros_own_spell_ends_his_concentration(registry, cfg):
    hero, npc = charmed_by(registry, cfg, "hero")
    assert "charmed" not in ids_of(npc)
    assert hero.creature.concentration is None


def test_dispel_outside_combat_on_a_clean_npc_says_so(registry, cfg):
    # решение 32: «Рассеивание магии: на <цель> нет заклинаний», ячейка тратится
    bundle = wiz(registry, "dispel_magic")
    npc = put_npc(bundle)
    before = bundle.heroes[0].creature.resources["spell_slot:3"].current
    result = cast_on(registry, cfg, bundle, "dispel_magic", 3)
    assert any(f"Рассеивание магии: на {npc.name} нет заклинаний" in x for x in result.log)
    assert bundle.heroes[0].creature.resources["spell_slot:3"].current == before - 1


def test_dispel_outside_combat_on_a_clean_npc_changes_nothing(registry, cfg):
    bundle = wiz(registry, "dispel_magic")
    npc = put_npc(bundle)
    cast_on(registry, cfg, bundle, "dispel_magic", 3)
    assert ids_of(npc) == []


# добор по выжившим мутантам: круг заклинания владельца-героя

def held_by(registry, cfg, owner, held):
    # на NPC Внушение владельца owner; у героя концентрация held (или None); Рассеивание, d20 = 1
    bundle = wiz(registry, "dispel_magic")
    hero = bundle.heroes[0]
    hero.creature.concentration = held
    npc = put_npc(bundle)
    npc.creature.conditions.append(
        AppliedCondition(
            id="charmed", source="suggestion", expires=Expiry(kind="concentration", owner=owner),
        )
    )
    cast_on(registry, cfg, bundle, "dispel_magic", 3, ScriptedRng(d20=[1]))
    return npc


def test_dispel_of_the_heros_spell_held_at_a_higher_circle_needs_a_check(registry, cfg):
    # Внушение на концентрации 4 круга: СЛ 14, d20 1 + Инт не хватает
    npc = held_by(registry, cfg, "hero", Concentration(spell_id="suggestion", circle=4))
    assert "charmed" in ids_of(npc)


def test_dispel_of_a_foreign_copy_ignores_the_heros_higher_circle(registry, cfg):
    npc = held_by(registry, cfg, "stranger", Concentration(spell_id="suggestion", circle=4))
    assert "charmed" not in ids_of(npc)


def test_dispel_of_the_heros_spell_ignores_his_other_concentration(registry, cfg):
    npc = held_by(registry, cfg, "hero", Concentration(spell_id="web", circle=4))
    assert "charmed" not in ids_of(npc)


def test_dispel_of_the_heros_spell_without_any_concentration_removes_it(registry, cfg):
    npc = held_by(registry, cfg, "hero", None)
    assert "charmed" not in ids_of(npc)


# добор по выжившим мутантам: цель Рассеивания и областные состояния вне боя

def test_dispel_outside_combat_needs_a_target(registry, cfg):
    bundle = wiz(registry, "dispel_magic")
    result = cast_on(registry, cfg, bundle, "dispel_magic", 3, target=None)
    assert isinstance(result, Invalid) and result.code == "bad_target"


def test_area_condition_spell_outside_combat_needs_no_npc_target(registry, cfg):
    bundle = wiz(registry, "web")
    result = cast_on(registry, cfg, bundle, "web", 2, ScriptedRng(d20=[1]), target=None)
    assert not isinstance(result, Invalid)
