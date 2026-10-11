# cast_spell (stage3-live-cast-explore, C1/C2/T): заклинание героя вне боя.
# Ожидаемый API: запрос cast_spell{spell_id, circle, target, free}; Invalid с кодами no_slot,
# not_prepared, unknown_spell; ячейка круга -- пул spell_slot:<круг>, бесплатное применение --
# пул favored_enemy; концентрация -- hero.creature.concentration. Грей из campaigns/drunk_dragon:
# 3 ячейки 1 круга, 2 Избранных врага, Мдр +2, Лечение ран / Туманное облако подготовлены.
from pathlib import Path

import game_kit  # noqa: F401  (добавляет в sys.path соседние kit-ы)
import pytest
from protocol_kit import ScriptedRng, combat_request, make_ctx, req

from ai_dm.campaign.loader import load_pack, pack_content_dir
from ai_dm.content.loader import load_registry
from ai_dm.game.combat_flow import make_engine
from ai_dm.game.controllers import PlayerController
from ai_dm.game.starter import new_world_from_pack
from ai_dm.protocol.apply import apply
from ai_dm.protocol.decision import Invalid

DRAGON = Path(__file__).resolve().parents[3] / "campaigns" / "drunk_dragon"


@pytest.fixture
def dragon(cfg):
    registry = load_registry([pack_content_dir(DRAGON)])
    bundle = new_world_from_pack(
        registry, cfg, load_pack(DRAGON, registry), hero="grey", seed=1, world_id="w1",
        saved_at="2026-01-01T00:00:00",
    )
    return registry, bundle


def cast(registry, cfg, bundle, rng=None, **fields):
    ctx = make_ctx(registry, cfg, rng=rng, bundle=bundle)
    fields = {"circle": 1, "target": "", "free": False} | fields
    return ctx, apply(ctx, req("cast_spell", **fields))


def pool(bundle, name):
    return bundle.heroes[0].creature.resources[name].current


def put_npc_here(bundle, npc_id="jorgen"):
    here = bundle.heroes[0].location_id
    bundle.world.npcs[npc_id].location_id = here
    return npc_id


def test_cure_wounds_is_accepted(dragon, cfg):
    registry, bundle = dragon
    bundle.heroes[0].creature.hp_current = 10
    rng = ScriptedRng(d8=[4, 5])
    ctx, d = cast(registry, cfg, bundle, rng, spell_id="cure_wounds", target="hero")
    assert d.status == "accepted"


def test_cure_wounds_heals_by_dice_and_wisdom(dragon, cfg):
    registry, bundle = dragon
    bundle.heroes[0].creature.hp_current = 10
    rng = ScriptedRng(d8=[4, 5])
    cast(registry, cfg, bundle, rng, spell_id="cure_wounds", target="hero")
    assert bundle.heroes[0].creature.hp_current == 21


def test_cure_wounds_does_not_heal_above_max(dragon, cfg):
    registry, bundle = dragon
    bundle.heroes[0].creature.hp_current = 20
    rng = ScriptedRng(d8=[8, 8])
    cast(registry, cfg, bundle, rng, spell_id="cure_wounds", target="hero")
    assert bundle.heroes[0].creature.hp_current == 25


def test_cure_wounds_spends_one_first_circle_slot(dragon, cfg):
    registry, bundle = dragon
    bundle.heroes[0].creature.hp_current = 10
    rng = ScriptedRng(d8=[4, 5])
    cast(registry, cfg, bundle, rng, spell_id="cure_wounds", target="hero")
    assert pool(bundle, "spell_slot:1") == 2


def test_cure_wounds_log_line(dragon, cfg):
    registry, bundle = dragon
    bundle.heroes[0].creature.hp_current = 10
    rng = ScriptedRng(d8=[4, 5])
    ctx, d = cast(registry, cfg, bundle, rng, spell_id="cure_wounds", target="hero")
    text = "\n".join(d.log)
    assert "Лечение ран" in text
    assert "2d8" in text
    assert "= 11" in text
    assert "21/25" in text


def test_cast_without_slots_is_invalid_no_slot(dragon, cfg):
    registry, bundle = dragon
    bundle.heroes[0].creature.resources["spell_slot:1"].current = 0
    ctx, d = cast(registry, cfg, bundle, spell_id="cure_wounds", target="hero")
    assert isinstance(d, Invalid)
    assert d.code == "no_slot"


def test_cast_without_slots_changes_nothing(dragon, cfg):
    registry, bundle = dragon
    bundle.heroes[0].creature.resources["spell_slot:1"].current = 0
    bundle.heroes[0].creature.hp_current = 10
    before = bundle.model_dump_json()
    ctx, d = cast(registry, cfg, bundle, spell_id="cure_wounds", target="hero")
    assert isinstance(d, Invalid)
    assert bundle.model_dump_json() == before


def test_cast_unknown_spell_is_invalid(dragon, cfg):
    registry, bundle = dragon
    ctx, d = cast(registry, cfg, bundle, spell_id="no_such_spell")
    assert isinstance(d, Invalid)


def test_cast_unknown_spell_changes_nothing(dragon, cfg):
    registry, bundle = dragon
    before = bundle.model_dump_json()
    cast(registry, cfg, bundle, spell_id="no_such_spell")
    assert bundle.model_dump_json() == before


def test_cast_not_prepared_spell_is_invalid(dragon, cfg):
    registry, bundle = dragon
    ctx, d = cast(registry, cfg, bundle, spell_id="longstrider")
    assert isinstance(d, Invalid)
    assert d.code == "not_prepared"


def test_fog_cloud_spends_slot_and_takes_concentration(dragon, cfg):
    registry, bundle = dragon
    ctx, d = cast(registry, cfg, bundle, spell_id="fog_cloud")
    assert d.status == "accepted"
    assert pool(bundle, "spell_slot:1") == 2
    assert bundle.heroes[0].creature.concentration.spell_id == "fog_cloud"


def test_fog_cloud_log_line(dragon, cfg):
    registry, bundle = dragon
    ctx, d = cast(registry, cfg, bundle, spell_id="fog_cloud")
    text = "\n".join(d.log)
    assert "Грей читает Туманное облако" in text
    assert "1 круг" in text
    assert "ячейки 2/3" in text


def test_new_concentration_spell_drops_the_previous_one(dragon, cfg):
    registry, bundle = dragon
    cast(registry, cfg, bundle, spell_id="fog_cloud")
    npc = put_npc_here(bundle)
    ctx, d = cast(registry, cfg, bundle, spell_id="hunters_mark", target=npc, free=True)
    assert d.status == "accepted"
    assert bundle.heroes[0].creature.concentration.spell_id == "hunters_mark"


def test_hunters_mark_free_spends_favored_enemy_not_slot(dragon, cfg):
    registry, bundle = dragon
    npc = put_npc_here(bundle)
    ctx, d = cast(registry, cfg, bundle, spell_id="hunters_mark", target=npc, free=True)
    assert d.status == "accepted"
    assert pool(bundle, "favored_enemy") == 1
    assert pool(bundle, "spell_slot:1") == 3


def test_hunters_mark_free_takes_concentration(dragon, cfg):
    registry, bundle = dragon
    npc = put_npc_here(bundle)
    cast(registry, cfg, bundle, spell_id="hunters_mark", target=npc, free=True)
    assert bundle.heroes[0].creature.concentration.spell_id == "hunters_mark"


def test_hunters_mark_with_slot_does_not_spend_favored_enemy(dragon, cfg):
    registry, bundle = dragon
    npc = put_npc_here(bundle)
    cast(registry, cfg, bundle, spell_id="hunters_mark", target=npc)
    assert pool(bundle, "favored_enemy") == 2
    assert pool(bundle, "spell_slot:1") == 2


def test_hunters_mark_free_without_favored_enemy_is_invalid(dragon, cfg):
    registry, bundle = dragon
    bundle.heroes[0].creature.resources["favored_enemy"].current = 0
    npc = put_npc_here(bundle)
    ctx, d = cast(registry, cfg, bundle, spell_id="hunters_mark", target=npc, free=True)
    assert isinstance(d, Invalid)
    assert pool(bundle, "spell_slot:1") == 3


def test_cast_at_unknown_npc_target_is_invalid(dragon, cfg):
    registry, bundle = dragon
    ctx, d = cast(registry, cfg, bundle, spell_id="hunters_mark", target="nobody", free=True)
    assert isinstance(d, Invalid)
    assert pool(bundle, "favored_enemy") == 2


def test_mark_outside_combat_goes_onto_target_when_combat_starts(dragon, cfg):
    registry, bundle = dragon
    npc = put_npc_here(bundle)
    ctx, d = cast(registry, cfg, bundle, spell_id="hunters_mark", target=npc, free=True)
    assert d.status == "accepted"
    enemy = {"ref": npc, "monster_id": "goblin_warrior", "zone": "hall", "group": "g"}
    group = {"id": "g", "leader": npc, "intent": "kill"}
    d = apply(ctx, combat_request(enemies=[enemy], groups=[group]))
    assert d.status == "accepted"
    assert bundle.session.active_combat is not None
    engine = make_engine(ctx, None, "r1", "", PlayerController())
    engine.start()
    hero = bundle.heroes[0]
    assert hero.creature.concentration.spell_id == "hunters_mark"
    assert "mark_pending" not in [e.kind for e in hero.creature.active_effects]
    assert "mark" in [e.kind for e in engine.creature(npc).active_effects]


def test_ensnaring_strike_outside_combat_is_invalid_combat_only(dragon, cfg):
    registry, bundle = dragon
    bundle.heroes[0].sheet.prepared_of().append("ensnaring_strike")
    ctx, d = cast(registry, cfg, bundle, spell_id="ensnaring_strike", target="hero")
    assert isinstance(d, Invalid)
    assert d.code == "combat_only"


def test_ensnaring_strike_outside_combat_changes_nothing(dragon, cfg):
    registry, bundle = dragon
    bundle.heroes[0].sheet.prepared_of().append("ensnaring_strike")
    before = pool(bundle, "spell_slot:1")
    cast(registry, cfg, bundle, spell_id="ensnaring_strike", target="hero")
    assert pool(bundle, "spell_slot:1") == before
    assert bundle.heroes[0].creature.concentration is None


# К0а: концентрация -- объект с кругом (вне боя круг берётся из запроса)

def test_fog_cloud_concentration_has_the_circle_of_the_request(dragon, cfg):
    registry, bundle = dragon
    cast(registry, cfg, bundle, spell_id="fog_cloud", circle=1)
    held = bundle.heroes[0].creature.concentration
    assert (held.spell_id, held.circle, held.until_s) == ("fog_cloud", 1, None)


def test_hunters_mark_free_concentration_has_the_circle_of_the_request(dragon, cfg):
    registry, bundle = dragon
    npc = put_npc_here(bundle)
    cast(registry, cfg, bundle, spell_id="hunters_mark", target=npc, free=True, circle=1)
    assert bundle.heroes[0].creature.concentration.circle == 1


def test_second_concentration_replaces_the_first_object(dragon, cfg):
    registry, bundle = dragon
    cast(registry, cfg, bundle, spell_id="fog_cloud")
    npc = put_npc_here(bundle)
    cast(registry, cfg, bundle, spell_id="hunters_mark", target=npc, free=True)
    held = bundle.heroes[0].creature.concentration
    assert (held.spell_id, held.circle) == ("hunters_mark", 1)


def test_concentration_survives_save_json(dragon, cfg):
    from ai_dm.state.hero import HeroState

    registry, bundle = dragon
    cast(registry, cfg, bundle, spell_id="fog_cloud")
    hero = bundle.heroes[0]
    assert HeroState.model_validate_json(hero.model_dump_json()).creature.concentration == (
        hero.creature.concentration
    )


# К0а (мутанты cast_spell): результат заклинания и снятие прежней концентрации с NPC

def test_cast_result_has_spell_id_circle_and_concentration(dragon, cfg):
    registry, bundle = dragon
    ctx, d = cast(registry, cfg, bundle, spell_id="fog_cloud")
    assert d.result["spell_id"] == "fog_cloud"
    assert d.result["circle"] == 1
    assert d.result["concentration"] == "fog_cloud"


def test_mark_cast_result_has_target_name_and_concentration(dragon, cfg):
    registry, bundle = dragon
    npc = put_npc_here(bundle)
    ctx, d = cast(registry, cfg, bundle, spell_id="hunters_mark", target=npc, free=True)
    assert d.result["target"] == bundle.world.npcs[npc].name
    assert d.result["concentration"] == "hunters_mark"


def test_heal_result_has_no_concentration(dragon, cfg):
    registry, bundle = dragon
    bundle.heroes[0].creature.hp_current = 10
    ctx, d = cast(registry, cfg, bundle, ScriptedRng(d8=[4, 5]), spell_id="cure_wounds",
        target="hero")
    assert "concentration" not in d.result


def held_effect_on_npc(bundle, hero):
    from ai_dm.state.creature import ActiveEffect, Concentration, CreatureState, Expiry

    npc = bundle.world.npcs["jorgen"]
    npc.creature = CreatureState(hp_current=5, hp_max=5)
    npc.creature.active_effects.append(
        ActiveEffect(id="old", source=hero.id, kind="spell",
                     expires=Expiry(kind="concentration", owner=hero.id))
    )
    hero.creature.concentration = Concentration(spell_id="bless", circle=1)
    return npc


def test_new_buff_concentration_removes_effects_the_old_one_put_on_npcs(dragon, cfg):
    registry, bundle = dragon
    hero = bundle.heroes[0]
    npc = held_effect_on_npc(bundle, hero)
    cast(registry, cfg, bundle, spell_id="fog_cloud")
    assert npc.creature.active_effects == []


def test_new_mark_concentration_removes_effects_the_old_one_put_on_npcs(dragon, cfg):
    registry, bundle = dragon
    hero = bundle.heroes[0]
    npc = held_effect_on_npc(bundle, hero)
    put_npc_here(bundle)
    cast(registry, cfg, bundle, spell_id="hunters_mark", target="jorgen", free=True)
    assert npc.creature.active_effects == []
