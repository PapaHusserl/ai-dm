# Партия К7д, Q5 (ответ проектировщика): Предсмертный взрыв мефитов и магмина (docs/K7D-PLAN.md).
#   Monster.death_burst: DeathBurst | None; DeathBurst(save: Ability = "dex", dc: int, dice: str,
#     damage_type: str) -- обязательны dc, dice, damage_type.
#   combat/death_burst.explode(engine, ref) -> события: вызывается из downed.kill_monster (после
#   monster_died / смерти NPC). Монстр без death_burst -- []. Один бросок урона на всех; каждый
#   участник в зоне умершего (status active или down, кроме самого умершего) бросает спасбросок
#   save СЛ dc: успех -- половина (округление вниз), провал -- полный урон. Урон идёт через
#   engine.damage (иммунитеты) и downed.after_damage (смерть, падение героя, цепной взрыв).
#   Участники других зон и мёртвые не страдают. Нелетальный удар (без сознания, не смерть)
#   не взрывает; успешная Стойкость нежити -- не смерть, взрыва нет.
# Мефит-копия: hp 5, КД 8, взрыв 2d4 огнём СЛ 10 Лов. Герой-воин: Лов +1 (без мастерства спаса).
import pytest
from combat_kit import (
    ScriptedRng,
    custom_registry,
    down_hero,
    hp,
    make_engine,
    make_fighter,
    make_zones,
    mon,
    part,
    set_hp,
)
from pydantic import ValidationError

from ai_dm.combat import downed
from ai_dm.content.models.monsters import DeathBurst

BURST = {"dc": 10, "dice": "2d4", "damage_type": "fire"}


def room(registry, cfg, rng, burst=BURST, named=False, pals=(), kinds=None, hero_hp=12):
    # pals: (ref, вид, зона) -- соседи-враги; kinds: {вид: поля монстра-копии}
    data = {"hp": 5, "ac": 8, "death_burst": burst}
    reg = custom_registry(registry, mephit=data, **(kinds or {"pal": {"hp": 20}}))
    engine = make_engine(
        reg, cfg, heroes=[make_fighter(registry)], rng=rng, zones=make_zones(),
        monsters=[mon("mephit", "mephit", "hall", named=named)]
        + [mon(ref, kind, zone) for ref, kind, zone in pals],
    )
    set_hp(engine, "hero", hero_hp)
    return engine


def kill(engine):
    # герой бьёт мечом 1d8+3 по мефиту с hp 5: d20 15 -- попадание
    return engine.perform("hero", "attack:longsword:mephit")


def test_failed_save_takes_full_damage(registry, cfg):
    # урон 2d4 = 3 + 4 = 7; Лов героя +1: d20 5 -> 6 < СЛ 10
    engine = room(registry, cfg, ScriptedRng(d20=[15, 5], d8=[5], d4=[3, 4]))
    kill(engine)
    assert hp(engine, "hero") == 12 - 7


def test_passed_save_takes_half(registry, cfg):
    engine = room(registry, cfg, ScriptedRng(d20=[15, 9], d8=[5], d4=[3, 4]))
    kill(engine)
    assert hp(engine, "hero") == 12 - 3


def test_save_at_the_dc_passes_one_below_fails(registry, cfg):
    # d20 9 -> 10 = СЛ -- успех (см. выше); d20 8 -> 9 -- провал
    engine = room(registry, cfg, ScriptedRng(d20=[15, 8], d8=[5], d4=[3, 4]))
    kill(engine)
    assert hp(engine, "hero") == 12 - 7


def test_the_mephit_dies_and_the_event_is_reported(registry, cfg):
    engine = room(registry, cfg, ScriptedRng(d20=[15, 9], d8=[5], d4=[1, 1]))
    events = kill(engine)
    assert part(engine, "mephit").status == "dead"
    assert [e.data["id"] for e in events if e.type == "monster_died"] == ["mephit"]


def test_explosion_is_logged(registry, cfg):
    engine = room(registry, cfg, ScriptedRng(d20=[15, 9], d8=[5], d4=[1, 1]))
    kill(engine)
    text = "\n".join(engine.state.log)
    assert "взрывается" in text and "Предсмертный взрыв" in text


def test_one_damage_roll_for_everybody(registry, cfg):
    # 7 урона обоим (провал у обоих), кости бросаются один раз
    rng = ScriptedRng(d20=[15, 5, 1], d8=[5], d4=[3, 4])
    engine = room(registry, cfg, rng, pals=[("pal", "pal", "hall")])
    kill(engine)
    assert (hp(engine, "hero"), hp(engine, "pal"), rng.left("d4")) == (5, 13, 0)


def test_other_zone_is_safe(registry, cfg):
    rng = ScriptedRng(d20=[15, 5], d8=[5], d4=[3, 4])
    engine = room(registry, cfg, rng, pals=[("pal", "pal", "balcony")])
    kill(engine)
    assert hp(engine, "pal") == 20


def test_dead_bystander_is_not_hit(registry, cfg):
    rng = ScriptedRng(d20=[15, 5], d8=[5], d4=[3, 4])
    engine = room(registry, cfg, rng, pals=[("pal", "pal", "hall")])
    part(engine, "pal").status = "dead"
    kill(engine)
    assert hp(engine, "pal") == 20


def test_fire_immune_victim_takes_nothing(registry, cfg):
    kinds = {"pal": {"hp": 20, "damage_immunities": ["fire"]}}
    rng = ScriptedRng(d20=[15, 5, 1], d8=[5], d4=[3, 4])
    engine = room(registry, cfg, rng, pals=[("pal", "pal", "hall")], kinds=kinds)
    kill(engine)
    assert hp(engine, "pal") == 20


def test_downed_hero_in_the_zone_takes_a_failure(registry, cfg):
    engine = room(registry, cfg, ScriptedRng(d20=[5], d4=[3, 4]))
    down_hero(engine, "hero")
    dealt = engine.damage("mephit", 9, "slashing")
    downed.after_damage(engine, "mephit", dealt, "pal")
    assert engine.heroes["hero"].creature.death_saves.failures == 1


def test_burst_can_drop_the_hero(registry, cfg):
    engine = room(registry, cfg, ScriptedRng(d20=[15, 5], d8=[5], d4=[4, 4]), hero_hp=5)
    kill(engine)
    assert (hp(engine, "hero"), part(engine, "hero").status) == (0, "down")


def test_burst_kills_a_weak_neighbour(registry, cfg):
    rng = ScriptedRng(d20=[15, 5, 1], d8=[5], d4=[4, 4])
    engine = room(registry, cfg, rng, pals=[("pal", "pal", "hall")], kinds={"pal": {"hp": 3}})
    events = kill(engine)
    assert "pal" in [e.data["id"] for e in events if e.type == "monster_died"]


def test_nonlethal_knockout_does_not_explode(registry, cfg):
    engine = room(registry, cfg, ScriptedRng(d20=[15], d8=[5]))
    engine.perform("hero", "attack:longsword:mephit:nonlethal")
    assert (part(engine, "mephit").status, hp(engine, "hero")) == ("down", 12)


def test_named_npc_mephit_explodes_too(registry, cfg):
    engine = room(registry, cfg, ScriptedRng(d20=[15, 5], d8=[5], d4=[3, 4]), named=True)
    kill(engine)
    assert hp(engine, "hero") == 12 - 7


def test_monster_without_a_burst_does_not_explode(registry, cfg):
    engine = room(registry, cfg, ScriptedRng(d20=[15], d8=[5]), burst=None)
    kill(engine)
    assert hp(engine, "hero") == 12


def test_chain_reaction(registry, cfg):
    # сосед гибнет от взрыва и взрывается сам: герой бросает два спасброска и получает 8 + 2
    kinds = {"pal": {"hp": 3, "death_burst": BURST}}
    rng = ScriptedRng(d20=[15, 5, 1, 5], d8=[5], d4=[4, 4, 1, 1])
    engine = room(registry, cfg, rng, pals=[("pal", "pal", "hall")], kinds=kinds, hero_hp=40)
    kill(engine)
    assert (part(engine, "pal").status, hp(engine, "hero"), rng.left("d4")) == ("dead", 30, 0)


def test_burst_save_ability_is_used(registry, cfg):
    # Сил героя +3 и мастерство спасброска +2: d20 5 -> 10 >= СЛ 10 -- успех
    burst = {**BURST, "save": "str"}
    engine = room(registry, cfg, ScriptedRng(d20=[15, 5], d8=[5], d4=[3, 4]), burst=burst)
    kill(engine)
    assert hp(engine, "hero") == 12 - 3


def test_model_defaults_to_a_dexterity_save():
    assert DeathBurst(dc=10, dice="1d4", damage_type="fire").save == "dex"


@pytest.mark.parametrize("missing", ["dc", "dice", "damage_type"])
def test_model_requires_all_three(missing):
    data = {"dc": 10, "dice": "1d4", "damage_type": "fire"}
    del data[missing]
    with pytest.raises(ValidationError):
        DeathBurst(**data)


def test_burst_roll_is_logged_with_its_type(registry, cfg):
    engine = room(registry, cfg, ScriptedRng(d20=[15, 5], d8=[5], d4=[3, 4]))
    kill(engine)
    assert any("Предсмертный взрыв: 2d4 (3, 4) = 7 огненный" in line for line in engine.state.log)


def test_every_victim_events_are_kept(registry, cfg):
    kinds = {"pal": {"hp": 3}}
    pals = [("pal_1", "pal", "hall"), ("pal_2", "pal", "hall")]
    rng = ScriptedRng(d20=[15, 5, 1, 1], d8=[5], d4=[4, 4])
    engine = room(registry, cfg, rng, pals=pals, kinds=kinds)
    died = [e.data["id"] for e in kill(engine) if e.type == "monster_died"]
    assert sorted(died) == ["mephit", "pal_1", "pal_2"]


def test_the_burst_is_the_cause_of_a_hit_on_the_hero(registry, cfg):
    engine = room(registry, cfg, ScriptedRng(d20=[15, 5], d8=[5], d4=[4, 4]), hero_hp=5)
    kill(engine)
    assert part(engine, "hero").last_hit_by == "mephit"


def test_named_npc_death_event_names_the_killer(registry, cfg):
    engine = room(registry, cfg, ScriptedRng(d20=[15, 9], d8=[5], d4=[1, 1]), named=True)
    died = [e.data for e in kill(engine) if e.type == "npc_died"]
    assert [(d["id"], d["by"], d["cause"]) for d in died] == [("mephit", "hero", "goal")]


def test_named_npc_hazard_death_has_no_killer(registry, cfg):
    engine = room(registry, cfg, ScriptedRng(d20=[9], d4=[1, 1]), named=True)
    dealt = engine.damage("mephit", 9, "fire")
    died = [e.data for e in downed.after_damage(engine, "mephit", dealt, None)
            if e.type == "npc_died"]
    assert [(d["by"], d["cause"]) for d in died] == [(None, "hazard")]
