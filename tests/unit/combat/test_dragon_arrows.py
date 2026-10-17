# Особые стрелы, клинок и «Каменная Кожа» Грея (docs/plan-stage3.md, A2-A5).
# Герой -- Грей из реального пака campaigns/drunk_dragon, стреляет из composite_longbow.
# Ожидаемый контракт (имена, которых в спеке нет, выбраны здесь -- это ТРЕБОВАНИЕ к реализации):
#   пункт действия особой стрелы: id вида attack:composite_longbow:<цель>:ammo:arrow_fire,
#       label -- "<оружие> -- <название стрелы> (осталось N)";
#       обычный выстрел остаётся "attack:composite_longbow:<цель>"; при 0 стрел пункта нет
#   доп. урон -- строка лога "<Название стрелы>: <кости> (<бросок>) <тип>"
#       ("Зажигательная стрела: 1d6 (4) огненный")
#   горение -- в начале хода цели (engine.start_turn) ещё 1d6 огня
#   мороз -- ActiveEffect(id="arrow_frost") на цели, expires end_of_turn (скорость -10 фт)
#   бронебойная -- строка атаки содержит "против КД 14 (бронебойная)"
#       (у воина-гоблина КД 15, Лов +2: 12 + 2)
#   тег "mor" -- поле tags у монстра; нежить -- creature_type == "undead"
#   КД монстра с ActiveEffect(kind="ac", params={"label", "amount", "magic"}) учитывается
#       engine.armor_class
#   эликсир: use_item:stoneskin_elixir, бонусное действие, ActiveEffect(id="stoneskin_elixir")
#       с Expiry(kind="seconds", value=<момент окончания в секундах мира>); +2 КД; сопротивление
#       рубящему/дробящему (урон вдвое); по истечении эффект снимается в start_turn героя
from pathlib import Path

import pytest
from combat_kit import ScriptedRng, creature, hp, make_engine, mon, option_ids, part, set_hp

from ai_dm.campaign.loader import load_pack, pack_content_dir
from ai_dm.content.loader import load_registry
from ai_dm.game.starter import new_world_from_pack
from ai_dm.rules.derived import attack_bonus
from ai_dm.rules.inventory import count_item, equip
from ai_dm.state.creature import ActiveEffect

ROOT = Path(__file__).resolve().parents[3]
DRAGON = ROOT / "campaigns" / "drunk_dragon"
SHIELD_PARAMS = {"label": "Щит", "amount": 5, "magic": True}
SHOOT = "attack:composite_longbow:goblin_1"

MONSTER = """id: {id}
name: {id}
source: test
license: CC0-1.0
size: medium
creature_type: {kind}
speed_ft: 30
ac: 15
hp: 10
cr: 1/4
abilities: {{str: 10, dex: 10, con: 10, int: 10, wis: 10, cha: 10}}
{tags}actions:
- name: Скимитар
  kind: melee
  attack_bonus: 4
  damage_dice: 1d6+2
  damage_type: slashing
  reach_ft: 5
"""


def build_dragon(cfg, tmp_path, specs):
    extra = tmp_path / "extra" / "monsters"
    extra.mkdir(parents=True)
    for name, (kind, tags) in specs.items():
        (extra / f"{name}.yaml").write_text(
            MONSTER.format(id=name, kind=kind, tags=tags), encoding="utf-8"
        )
    registry = load_registry([pack_content_dir(DRAGON), tmp_path / "extra"])
    pack = load_pack(DRAGON, load_registry([pack_content_dir(DRAGON)]))
    bundle = new_world_from_pack(
        registry, cfg, pack, hero="grey", seed=1, world_id="dd", saved_at="2026-01-01T00:00:00",
    )
    return registry, bundle.heroes[0]


@pytest.fixture
def dragon(cfg, tmp_path):
    return build_dragon(cfg, tmp_path, {"skeleton_x": ("undead", "")})


@pytest.fixture
def dragon_mor(cfg, tmp_path):
    specs = {"skeleton_x": ("undead", ""), "mor_x": ("fiend", "tags: [mor]\n")}
    return build_dragon(cfg, tmp_path, specs)


def fresh_hero(hero, registry):
    copy = hero.model_copy(deep=True)
    equip(copy, "composite_longbow", registry)
    return copy


def make(dragon, cfg, rng, monster="goblin_warrior", zone="hall"):
    registry, hero = dragon
    engine = make_engine(
        registry, cfg, heroes=[fresh_hero(hero, registry)], rng=rng,
        monsters=[mon("goblin_1", monster, zone)], hero_zone="door",
    )
    creature(engine, "goblin_1").hp_max = 100
    set_hp(engine, "goblin_1", 100)
    return engine


def arrow_option(engine, arrow_id, target="goblin_1"):
    found = [
        o for o in engine.available_actions("hero")
        if arrow_id in o.id and target in o.id
    ]
    assert found, f"нет пункта для {arrow_id}"
    return found[0]


def hit_roll(dragon, need=0):
    # d20, который попадает по КД 15 (need -- запас сверх)
    registry, hero = dragon
    return max(2, 15 - attack_bonus(hero, registry, "composite_longbow") + need)


def shoot(dragon, cfg, option_of, d6=(), d8=(), monster="goblin_warrior"):
    rng = ScriptedRng(d20=[hit_roll(dragon, 3)], d8=[5, 5, *d8], d6=list(d6), d4=[1])
    engine = make(dragon, cfg, rng, monster)
    option = option_of(engine)
    engine.perform("hero", option)
    return engine, 100 - hp(engine, "goblin_1")


def plain(engine):
    return SHOOT


def fire(engine):
    return arrow_option(engine, "arrow_fire").id


def frost(engine):
    return arrow_option(engine, "arrow_frost").id


def silver(engine):
    return arrow_option(engine, "arrow_silver").id


# выбор и расход

def test_each_special_arrow_has_its_own_option(dragon, cfg):
    engine = make(dragon, cfg, ScriptedRng())
    for arrow in ("arrow_fire", "arrow_frost", "arrow_silver", "arrow_armor_piercing"):
        arrow_option(engine, arrow)


def test_option_label_names_bow_arrow_and_count(dragon, cfg):
    engine = make(dragon, cfg, ScriptedRng())
    label = arrow_option(engine, "arrow_fire").label
    assert "зажигательная стрела" in label.lower()
    assert "(осталось 10)" in label


def test_ordinary_arrows_are_not_an_option(dragon, cfg):
    engine = make(dragon, cfg, ScriptedRng())
    assert "arrows" not in "".join(option_ids(engine, "hero"))


def test_shot_spends_one_arrow(dragon, cfg):
    engine, _ = shoot(dragon, cfg, fire, d6=[4])
    assert count_item(engine.heroes["hero"], "arrow_fire") == 9
    assert count_item(engine.heroes["hero"], "arrow_frost") == 10


def test_miss_also_spends_the_arrow(dragon, cfg):
    rng = ScriptedRng(d20=[1])
    engine = make(dragon, cfg, rng)
    engine.perform("hero", arrow_option(engine, "arrow_fire").id)
    assert count_item(engine.heroes["hero"], "arrow_fire") == 9


def test_option_disappears_at_zero(dragon, cfg):
    registry, hero = dragon
    hero = fresh_hero(hero, registry)
    for entry in hero.inventory:
        if entry.item_id == "arrow_silver":
            entry.qty = 1
    engine = make_engine(
        registry, cfg, heroes=[hero], rng=ScriptedRng(d20=[1]),
        monsters=[mon("goblin_1", "goblin_warrior", "hall")], hero_zone="door",
    )
    engine.perform("hero", arrow_option(engine, "arrow_silver").id)
    assert not [o for o in engine.available_actions("hero") if "arrow_silver" in o.id]
    assert count_item(engine.heroes["hero"], "arrow_silver") == 0


# зажигательная

def test_fire_arrow_adds_1d6_fire(dragon, cfg):
    _, base = shoot(dragon, cfg, plain)
    _, with_fire = shoot(dragon, cfg, fire, d6=[4])
    assert with_fire - base == 4


def test_fire_arrow_extra_damage_has_its_own_log_line(dragon, cfg):
    engine, _ = shoot(dragon, cfg, fire, d6=[4])
    assert any("Зажигательная стрела: 1d6 (4) огненный" in line for line in engine.state.log)


def test_fire_arrow_target_burns_at_start_of_its_turn(dragon, cfg):
    engine, _ = shoot(dragon, cfg, fire, d6=[4, 3])
    before = hp(engine, "goblin_1")
    engine.start_turn("goblin_1")
    assert before - hp(engine, "goblin_1") == 3


def test_ordinary_shot_does_not_burn(dragon, cfg):
    engine, _ = shoot(dragon, cfg, plain)
    before = hp(engine, "goblin_1")
    engine.start_turn("goblin_1")
    assert hp(engine, "goblin_1") == before


# морозная

def test_frost_arrow_adds_1d8_cold(dragon, cfg):
    _, base = shoot(dragon, cfg, plain)
    _, with_frost = shoot(dragon, cfg, frost, d8=[6])
    assert with_frost - base == 6


def test_frost_arrow_log_line(dragon, cfg):
    engine, _ = shoot(dragon, cfg, frost, d8=[6])
    assert any("Морозная стрела: 1d8 (6)" in line for line in engine.state.log)


def test_frost_arrow_slows_target(dragon, cfg):
    engine, _ = shoot(dragon, cfg, frost, d8=[6])
    effects = creature(engine, "goblin_1").active_effects
    assert [e for e in effects if e.id == "arrow_frost"]


def test_frost_slow_ends_with_its_next_turn(dragon, cfg):
    engine, _ = shoot(dragon, cfg, frost, d8=[6])
    engine.start_turn("goblin_1")
    engine.expire("end_of_turn", "goblin_1")
    assert not [e for e in creature(engine, "goblin_1").active_effects if e.id == "arrow_frost"]


def test_ordinary_shot_does_not_slow(dragon, cfg):
    engine, _ = shoot(dragon, cfg, plain)
    assert not creature(engine, "goblin_1").active_effects


# бронебойная

def test_armor_piercing_hits_what_plain_arrow_misses(dragon, cfg):
    registry, hero = dragon
    # воин-гоблин: КД 15, Лов +2 -> бронебойная считает 12 + 2 = 14
    roll = 14 - attack_bonus(hero, registry, "composite_longbow")
    plain_engine = make(dragon, cfg, ScriptedRng(d20=[roll]))
    plain_engine.perform("hero", SHOOT)
    assert hp(plain_engine, "goblin_1") == 100
    rng = ScriptedRng(d20=[roll], d8=[5, 5])
    engine = make(dragon, cfg, rng)
    engine.perform("hero", arrow_option(engine, "arrow_armor_piercing").id)
    assert hp(engine, "goblin_1") < 100


def test_armor_piercing_attack_line_shows_ac_12(dragon, cfg):
    rng = ScriptedRng(d20=[8], d8=[5, 5])
    engine = make(dragon, cfg, rng)
    engine.perform("hero", arrow_option(engine, "arrow_armor_piercing").id)
    assert any("против КД 14 (бронебойная)" in line for line in engine.state.log)


# серебряная

def test_silver_arrow_extra_2d6_against_undead(dragon, cfg):
    _, base = shoot(dragon, cfg, plain, monster="skeleton_x")
    _, with_silver = shoot(dragon, cfg, silver, d6=[3, 4], monster="skeleton_x")
    assert with_silver - base == 7


def test_silver_arrow_extra_2d6_against_mor_tag(dragon_mor, cfg):
    _, base = shoot(dragon_mor, cfg, plain, monster="mor_x")
    _, with_silver = shoot(dragon_mor, cfg, silver, d6=[3, 4], monster="mor_x")
    assert with_silver - base == 7


def test_silver_arrow_log_line_against_undead(dragon, cfg):
    engine, _ = shoot(dragon, cfg, silver, d6=[3, 4], monster="skeleton_x")
    assert any("Серебряная стрела: 2d6" in line for line in engine.state.log)


def test_silver_arrow_no_bonus_against_ordinary_target(dragon, cfg):
    _, base = shoot(dragon, cfg, plain)
    engine, with_silver = shoot(dragon, cfg, silver)
    assert with_silver == base
    assert not any("Серебряная стрела" in line for line in engine.state.log)


# клинок Северного Ветра

def blade_engine(dragon, cfg, rng, monster="goblin_warrior"):
    registry, hero = dragon
    blade = hero.model_copy(deep=True)
    equip(blade, "north_wind_blade", registry)
    engine = make_engine(
        registry, cfg, heroes=[blade], rng=rng,
        monsters=[mon("goblin_1", monster, "door")], hero_zone="door",
    )
    creature(engine, "goblin_1").hp_max = 100
    set_hp(engine, "goblin_1", 100)
    return engine


BLADE = "attack:north_wind_blade:goblin_1"


def blade_loss(dragon, cfg, monster, d6=()):
    engine = blade_engine(
        dragon, cfg, ScriptedRng(d20=[12], d8=[5, 5], d6=list(d6), d4=[1, 1]), monster
    )
    engine.perform("hero", BLADE)
    return engine, 100 - hp(engine, "goblin_1")


def test_blade_extra_2d6_against_undead(dragon, cfg):
    _, base = blade_loss(dragon, cfg, "goblin_warrior")
    _, with_bonus = blade_loss(dragon, cfg, "skeleton_x", d6=[2, 5])
    assert with_bonus - base == 7


def test_blade_extra_line_against_mor(dragon_mor, cfg):
    engine, _ = blade_loss(dragon_mor, cfg, "mor_x", d6=[2, 5])
    assert any("Клинок Северного Ветра: 2d6" in line and "рубящий" in line
               for line in engine.state.log)


def test_blade_no_bonus_against_ordinary_target(dragon, cfg):
    engine, _ = blade_loss(dragon, cfg, "goblin_warrior")
    assert not any("Клинок Северного Ветра: 2d6" in line for line in engine.state.log)


def test_blade_ignores_magic_ac_bonus(dragon, cfg):
    registry, hero = dragon
    roll = 17 - attack_bonus(hero, registry, "north_wind_blade")
    engine = blade_engine(dragon, cfg, ScriptedRng(d20=[roll], d8=[5, 5], d4=[1]))
    creature(engine, "goblin_1").active_effects.append(
        ActiveEffect(id="shield", source="goblin_1", kind="ac", params=SHIELD_PARAMS)
    )
    assert engine.armor_class("goblin_1") == 20
    engine.perform("hero", BLADE)
    assert hp(engine, "goblin_1") < 100


def test_other_weapon_does_not_ignore_magic_ac(dragon, cfg):
    registry, hero = dragon
    roll = 17 - attack_bonus(hero, registry, "composite_longbow")
    engine = make(dragon, cfg, ScriptedRng(d20=[roll]))
    creature(engine, "goblin_1").active_effects.append(
        ActiveEffect(id="shield", source="goblin_1", kind="ac", params=SHIELD_PARAMS)
    )
    engine.perform("hero", SHOOT)
    assert hp(engine, "goblin_1") == 100


# Каменная Кожа

ELIXIR = "use_item:stoneskin_elixir"


def test_elixir_is_a_bonus_action_option_with_count(dragon, cfg):
    engine = make(dragon, cfg, ScriptedRng())
    option = [o for o in engine.available_actions("hero") if o.id == ELIXIR]
    assert option
    assert "Каменная Кожа" in option[0].label
    assert "(осталось 2)" in option[0].label


def test_elixir_spends_bonus_action_not_action(dragon, cfg):
    engine = make(dragon, cfg, ScriptedRng())
    engine.perform("hero", ELIXIR)
    assert part(engine, "hero").turn.bonus is False
    assert part(engine, "hero").turn.action is True


def test_elixir_spends_one_item(dragon, cfg):
    engine = make(dragon, cfg, ScriptedRng())
    engine.perform("hero", ELIXIR)
    assert count_item(engine.heroes["hero"], "stoneskin_elixir") == 1


def test_elixir_gives_plus_2_ac(dragon, cfg):
    engine = make(dragon, cfg, ScriptedRng())
    before = engine.armor_class("hero")
    engine.perform("hero", ELIXIR)
    assert engine.armor_class("hero") == before + 2


def test_elixir_halves_slashing_damage(dragon, cfg):
    # скимитар гоблина 1d6+2 при d6=6 -- 8 рубящего, с эликсиром 4
    engine = make(dragon, cfg, ScriptedRng(d20=[19], d6=[6, 6]), zone="door")
    engine.perform("hero", ELIXIR)
    full = engine.heroes["hero"].creature.hp_current
    engine.perform("goblin_1", "attack:скимитар:hero")
    assert full - engine.heroes["hero"].creature.hp_current == 4


def test_elixir_effect_expires_after_one_hour(dragon, cfg):
    engine = make(dragon, cfg, ScriptedRng())
    before = engine.armor_class("hero")
    engine.perform("hero", ELIXIR)
    engine.world.clock.now_s += 3601
    engine.start_turn("hero")
    assert engine.armor_class("hero") == before


def test_elixir_still_active_before_hour(dragon, cfg):
    engine = make(dragon, cfg, ScriptedRng())
    before = engine.armor_class("hero")
    engine.perform("hero", ELIXIR)
    engine.world.clock.now_s += 3500
    engine.start_turn("hero")
    assert engine.armor_class("hero") == before + 2


def test_elixir_option_gone_when_none_left(dragon, cfg):
    registry, hero = dragon
    hero = fresh_hero(hero, registry)
    for entry in hero.inventory:
        if entry.item_id == "stoneskin_elixir":
            hero.inventory.remove(entry)
            break
    engine = make_engine(
        registry, cfg, heroes=[hero], rng=ScriptedRng(),
        monsters=[mon("goblin_1", "goblin_warrior", "hall")], hero_zone="door",
    )
    assert ELIXIR not in option_ids(engine, "hero")


# детерминизм

def test_same_seed_same_arrow_log(dragon, cfg):
    first, _ = shoot(dragon, cfg, fire, d6=[4])
    second, _ = shoot(dragon, cfg, fire, d6=[4])
    assert first.state.log == second.state.log
