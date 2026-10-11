# Строка о сопротивлении под строкой урона (stage3-live-resist-line, R1/T).
# Если итоговый урон отличается от брошенного, в state.log под «Урон (...)» идёт строка:
#   «Сопротивление (<источник>): 3 → 1 рубящий», «Временные HP поглотили 2».
# Эликсир «Каменная Кожа» Грея из campaigns/drunk_dragon; монстр с сопротивлением -- тестовый
# контент во временном каталоге (черта монстра с modifier damage resistance).
from pathlib import Path

import game_kit  # noqa: F401  (добавляет kit-ы соседних слоёв в sys.path)
import pytest
from combat_kit import ScriptedRng, make_engine, make_fighter, mon
from protocol_kit import make_ctx, req

from ai_dm.campaign.loader import load_pack, pack_content_dir
from ai_dm.content.loader import load_registry
from ai_dm.game.starter import new_world_from_pack
from ai_dm.protocol.apply import apply

DRAGON = Path(__file__).resolve().parents[3] / "campaigns" / "drunk_dragon"
GOBLIN_HIT = "attack:скимитар:"


@pytest.fixture
def dragon(cfg):
    registry = load_registry([pack_content_dir(DRAGON)])
    bundle = new_world_from_pack(
        registry, cfg, load_pack(DRAGON, registry), hero="grey", seed=1, world_id="w1",
        saved_at="2026-01-01T00:00:00",
    )
    return registry, bundle


def drink(registry, cfg, bundle):
    ctx = make_ctx(registry, cfg, bundle=bundle)
    apply(ctx, req("use_item", item_id="stoneskin_elixir", qty=1))


def grey_vs_goblin(registry, cfg, bundle, rng):
    grey = bundle.heroes[0]
    return make_engine(
        registry, cfg, heroes=[(grey, "hall")], rng=rng,
        monsters=[mon("g1", "goblin_warrior", "hall")],
    ), grey


def goblin_hits(engine, hero):
    engine.perform("g1", f"{GOBLIN_HIT}{hero.id}")
    return engine.state.log


def test_elixir_resist_line_has_source_and_result(dragon, cfg):
    registry, bundle = dragon
    drink(registry, cfg, bundle)
    engine, grey = grey_vs_goblin(registry, cfg, bundle, ScriptedRng(d20=[18], d6=[1]))
    log = goblin_hits(engine, grey)
    assert any("Сопротивление (Каменная Кожа): 3 → 1 рубящий" in line for line in log)


def test_elixir_resist_line_follows_damage_line(dragon, cfg):
    registry, bundle = dragon
    drink(registry, cfg, bundle)
    engine, grey = grey_vs_goblin(registry, cfg, bundle, ScriptedRng(d20=[18], d6=[1]))
    log = goblin_hits(engine, grey)
    damage_at = [i for i, line in enumerate(log) if "Урон (скимитар)" in line][0]
    assert "Сопротивление" in log[damage_at + 1]


def test_no_resist_line_without_elixir(dragon, cfg):
    registry, bundle = dragon
    engine, grey = grey_vs_goblin(registry, cfg, bundle, ScriptedRng(d20=[19], d6=[1]))
    log = goblin_hits(engine, grey)
    assert any("Урон (скимитар)" in line for line in log)
    assert not any("Сопротивление" in line for line in log)


def test_temp_hp_line(registry, cfg):
    hero = make_fighter(registry)
    hero.creature.hp_temp = 5
    engine = make_engine(
        registry, cfg, heroes=[(hero, "hall")], rng=ScriptedRng(d20=[19], d6=[1]),
        monsters=[mon("g1", "goblin_warrior", "hall")],
    )
    log = goblin_hits(engine, hero)
    assert any("Временные HP поглотили 3" in line for line in log)


def test_no_temp_hp_line_without_temp_hp(registry, cfg):
    hero = make_fighter(registry)
    engine = make_engine(
        registry, cfg, heroes=[(hero, "hall")], rng=ScriptedRng(d20=[19], d6=[1]),
        monsters=[mon("g1", "goblin_warrior", "hall")],
    )
    log = goblin_hits(engine, hero)
    assert not any("Временные HP" in line for line in log)


@pytest.mark.xfail(strict=True, reason="сопротивлений монстров в данных нет — BACKLOG")
def test_monster_resistance_line_names_the_trait(registry, cfg, tmp_path):
    (tmp_path / "features").mkdir()
    (tmp_path / "monsters").mkdir()
    (tmp_path / "features" / "stone_hide.yaml").write_text(
        "id: stone_hide\nname: Каменная шкура\n"
        "description: Сопротивление рубящему урону.\n"
        "effects:\n- type: modifier\n  target: damage\n  mode: resistance\n"
        "  damage_type: slashing\n"
    )
    (tmp_path / "monsters" / "stone_dummy.yaml").write_text(
        "id: stone_dummy\nname: Каменный истукан\nsize: medium\ncreature_type: construct\n"
        "ac: 10\nhp: 30\ncr: '1'\n"
        "abilities: {str: 10, dex: 10, con: 10, int: 10, wis: 10, cha: 10}\n"
        "traits:\n- stone_hide\n"
    )
    registry = load_registry([tmp_path])
    hero = make_fighter(registry)
    engine = make_engine(
        registry, cfg, heroes=[(hero, "hall")], rng=ScriptedRng(d20=[10], d8=[5]),
        monsters=[mon("dummy", "stone_dummy", "hall")],
    )
    engine.perform("hero", "attack:longsword:dummy")
    log = engine.state.log
    assert any("Сопротивление (Каменная шкура): 8 → 4 рубящий" in line for line in log)
