# Приёмка этапа 1: сквозная проверка критериев «готово» (ARCHITECTURE 13/B, ТЗ 13 строка 1).
# Реальный SRD-контент, диск (tmp_path), без моков. Детали -- в unit/scenario-тестах из таблицы.
# Критерий -> тест здесь -> где детали:
#   1 бой гоблины-3 по сиду до конца, в т.ч. исход при 0 HP:
#       test_full_cycle (победа / defeat_pending / hero_dead), test_mixed_fight_*
#       tests/scenarios/test_criterion1.py, tests/unit/combat/*,
#       tests/unit/devtools/test_sim_combat.py, tests/golden/goblins3_win.txt
#   2 сейв -> загрузка -> то же состояние, пустые секции, RNG продолжается, сейв посреди боя:
#       test_full_cycle, test_save_in_round_two_and_resume_equals_continuous
#       tests/unit/persistence/test_store.py, tests/unit/state/test_save_bundle.py,
#       tests/unit/persistence/test_schema_fingerprint.py
#   3 миграция v0 -> v1 + бэкап:
#       test_v0_fixture_loads_as_v1_with_backup
#       tests/unit/persistence/test_migrations.py
#   4 структурные условия триггеров по состоянию:
#       test_trigger_*, test_mixed_fight_*
#       tests/unit/rules/test_triggers_eval.py, tests/unit/rules/test_auto_flags.py,
#       tests/unit/state/test_triggers.py
#   Чек-лист релиза (session без голых dict): test_release_checklist_*
#       tests/unit/state/test_save_bundle.py
#   Сторож архитектуры: tests/unit/test_architecture.py (здесь только проверка наличия)
import re
import shutil
from pathlib import Path

import pytest

from ai_dm.combat.defeat import DefeatParams, apply_defeat_outcome
from ai_dm.combat.engine import CombatEngine
from ai_dm.content.loader import load_registry
from ai_dm.core.rng import Rng
from ai_dm.devtools.sim_combat import build_scenario, find_seed, simulate
from ai_dm.persistence.migrations import CURRENT_SCHEMA_VERSION, MigrationContext
from ai_dm.persistence.store import load_slot, save_slot
from ai_dm.rules.triggers_eval import Truth, evaluate, fire, is_ready
from ai_dm.state.combat import Participant
from ai_dm.state.memory import Chronicle, Memory
from ai_dm.state.save import Manifest, SaveBundle
from ai_dm.state.session import SessionState
from ai_dm.state.triggers import Trigger
from ai_dm.state.world import NPC, GlobalEvent, Tone

TESTS = Path(__file__).resolve().parents[1]
FIXTURE_V0 = TESTS / "fixtures" / "saves" / "v0"
SAVED_AT = "2026-01-01T12:00:00Z"
LATER = "2026-02-02T09:30:00Z"
BACKUP_TS = "20260101T000000Z"


def tree(folder):
    return {
        p.relative_to(folder).as_posix(): p.read_bytes()
        for p in sorted(folder.rglob("*")) if p.is_file()
    }


def add_world_content(world):
    # NPC с триггером steal_grail-типа, секретом, событием, тоном; пантеон остаётся пустым
    aldric = NPC.model_validate({
        "id": "mentor_aldric", "name": "Олдрик", "named": True, "key": True,
        "means": ["магия крови"], "motive": "спасти сестру", "attitude": 20,
        "opportunity": [
            {
                "id": "steal_grail",
                "if": {"all": [
                    {"hero_has": "blood_grail"},
                    {"npc_status": {"id": "mentor_aldric", "is": "alive"}},
                ]},
                "then": "выкрадет Грааль", "once": True,
            },
            {
                "id": "after_fight",
                "if": {"flag": "combat_ended:fight_1"},
                "then": "Олдрик слышит о бое", "once": True,
            },
        ],
        "secrets": [
            {"id": "sister_vampire", "text": "сестра -- вампир", "reveal_if": {"flag": "found"}}
        ],
    })
    world.npcs[aldric.id] = aldric
    world.flags["met_aldric"] = True
    world.events.append(GlobalEvent(id="grey_plague", type="plague", regions=["port_vale"]))
    world.tone = Tone(mood="мрачный", hard_limits=["насилие над детьми"])


def goblins_scenario(registry, cfg, seed, **kwargs):
    scenario = build_scenario("goblins3", registry, cfg, seed, **kwargs)
    add_world_content(scenario.world)
    return scenario


def bundle_of(scenario, active_combat=None):
    scenario.world.rng = scenario.rng.state
    heroes = list(scenario.heroes.values())
    return SaveBundle(
        manifest=Manifest(
            schema_version=1, engine_version="0.1.0", world_id=scenario.world.world_id,
            campaign_id=None, slot="auto", saved_at=SAVED_AT,
            current_hero_id=heroes[0].id, heroes=[h.id for h in heroes],
        ),
        world=scenario.world, chronicle=Chronicle(), memory=Memory(),
        heroes=heroes, session=SessionState(active_combat=active_combat),
    )


def rng_tail(state, n=20):
    rng = Rng.from_state(state)
    return [rng.d(20) for _ in range(n)]


# критерии 1 + 2: полный цикл, три исхода (победа, 0 HP с капитуляцией, смерть героя)

# смерть героя бой не обрывает, но сценарии смерти/плена идут на слабом герое, как в критерии 1
# (одинокий герой: бой кончается сразу); воин при kill тоже может погибнуть -- сид находится
CASES = [
    ("default", "kill", "victory"),
    ("weak", "capture", "defeat_pending"),
    ("weak", "kill", "hero_dead"),
]


@pytest.mark.parametrize("variant,intent,outcome", CASES)
def test_full_cycle(registry, cfg, tmp_path, variant, intent, outcome):
    kw = {"registry": registry, "cfg": cfg, "variant": variant, "intent": intent}
    seed = find_seed("goblins3", outcome, **kw)
    assert seed is not None
    # бой по сиду детерминирован
    again = simulate(goblins_scenario(registry, cfg, seed, variant=variant, intent=intent))
    result = simulate(goblins_scenario(registry, cfg, seed, variant=variant, intent=intent))
    assert result.outcome == again.outcome == outcome
    assert result.log == again.log
    scenario = result.scenario
    hero = scenario.heroes["hero"]
    if outcome == "defeat_pending":
        assert hero.creature.hp_current == 0
        done = apply_defeat_outcome(
            scenario.state, ["rob", "left_to_die"], DefeatParams(), world=scenario.world,
            hero=hero, registry=registry, cfg=cfg, rng=scenario.rng,
        )
        assert done.status in ("applied", "clamped")
    if outcome == "hero_dead":
        assert hero.status == "dead"
        assert scenario.world.flags["hero_dead:hero"] is True
    assert scenario.world.flags[f"combat_ended:{scenario.state.id}"] is True
    # сейв -> загрузка
    bundle = bundle_of(scenario)
    save_slot(tmp_path, bundle, "auto", saved_at=SAVED_AT)
    loaded = load_slot(tmp_path, "sim", "auto")
    assert loaded.world == bundle.world
    assert loaded.heroes == bundle.heroes
    assert loaded.session == bundle.session
    assert loaded.chronicle == bundle.chronicle
    assert loaded.memory == bundle.memory
    assert loaded.manifest.saved_at == SAVED_AT
    # пустые секции пережили цикл
    assert loaded.world.pantheon == {}
    assert loaded.world.factions == {}
    assert loaded.chronicle == Chronicle()
    assert loaded.memory == Memory()
    assert loaded.session.pending_decision is None
    # повторный save: побайтно то же; с другим saved_at -- кроме manifest.json
    first = tree(tmp_path / "sim" / "slots" / "auto")
    save_slot(tmp_path, loaded, "auto", saved_at=SAVED_AT)
    assert tree(tmp_path / "sim" / "slots" / "auto") == first
    save_slot(tmp_path, loaded, "auto", saved_at=LATER)
    third = tree(tmp_path / "sim" / "slots" / "auto")
    assert {k: v for k, v in third.items() if k != "manifest.json"} == {
        k: v for k, v in first.items() if k != "manifest.json"
    }
    assert third["manifest.json"] != first["manifest.json"]
    # ГСЧ продолжает ту же последовательность
    assert rng_tail(loaded.world.rng) == rng_tail(scenario.rng.state)


# критерий 2: сейв посреди боя

def midfight(registry, cfg):
    for variant in ("default", "weak"):
        for seed in range(100):
            if simulate(goblins_scenario(registry, cfg, seed, variant=variant)).rounds >= 3:
                return seed, variant
    pytest.fail("нет боя длиннее 2 раундов")


def finish(engine):
    engine.run_to_end()
    engine.world.rng = engine.rng.state
    return (
        engine.state.model_dump_json(),
        engine.world.model_dump_json(),
        [h.model_dump_json() for h in engine.heroes.values()],
        engine.rng.state,
    )


def test_save_in_round_two_and_resume_equals_continuous(registry, cfg, tmp_path):
    seed, variant = midfight(registry, cfg)
    whole = goblins_scenario(registry, cfg, seed, variant=variant).engine()
    whole.start()
    expected = finish(whole)
    scenario = goblins_scenario(registry, cfg, seed, variant=variant)
    engine = scenario.engine()
    engine.start()
    while engine.state.round < 2 and not engine.is_over:
        engine.step()
    assert engine.state.round == 2
    save_slot(tmp_path, bundle_of(scenario, active_combat=engine.state), "auto", saved_at=SAVED_AT)
    loaded = load_slot(tmp_path, "sim", "auto")
    assert loaded.session.active_combat == engine.state
    assert loaded.session.active_combat.round == 2
    heroes = {h.id: h for h in loaded.heroes}
    resumed = CombatEngine(
        loaded.session.active_combat, loaded.world, heroes, registry, cfg,
        Rng.from_state(loaded.world.rng),
    )
    assert finish(resumed) == expected


# критерий 4: триггеры по состоянию после боя

def test_trigger_flag_false_before_and_true_after_fight(registry, cfg, tmp_path):
    scenario = goblins_scenario(registry, cfg, 3)
    hero = scenario.heroes["hero"]
    trigger = scenario.world.npcs["mentor_aldric"].opportunity[1]
    assert evaluate(trigger.if_, scenario.world, hero).truth == Truth.FALSE
    result = simulate(scenario)
    save_slot(tmp_path, bundle_of(result.scenario), "auto", saved_at=SAVED_AT)
    loaded = load_slot(tmp_path, "sim", "auto")
    trigger = loaded.world.npcs["mentor_aldric"].opportunity[1]
    now_s = loaded.world.clock.now_s
    assert evaluate(trigger.if_, loaded.world, loaded.heroes[0]).truth == Truth.TRUE
    assert is_ready(trigger, now_s)
    fire(trigger, now_s)
    assert trigger.state == "fired"
    assert not is_ready(trigger, now_s)


def test_trigger_steal_grail_is_false_without_the_grail(registry, cfg):
    scenario = goblins_scenario(registry, cfg, 3)
    trigger = scenario.world.npcs["mentor_aldric"].opportunity[0]
    result = evaluate(trigger.if_, scenario.world, scenario.heroes["hero"])
    assert result.truth == Truth.FALSE


def named_boss_scenario(registry, cfg, seed):
    scenario = goblins_scenario(registry, cfg, seed)
    scenario.world.npcs["boss"] = NPC(
        id="boss", name="Вожак", named=True, means=["сила"],
        opportunity=[Trigger.model_validate({
            "id": "avenge", "if": {"flag": "npc_dead:boss"}, "then": "месть", "once": True,
        })],
    )
    for index, p in enumerate(scenario.state.participants):
        if p.ref == "goblin_2":
            scenario.state.participants[index] = Participant(
                ref="boss", side="enemies", group_id="goblins", zone_id="hall",
                monster_id="goblin_warrior", name="Вожак",
            )
    return scenario


def test_mixed_fight_named_npc_death_sets_flag_and_trigger_fires(registry, cfg, tmp_path):
    for seed in range(100):
        result = simulate(named_boss_scenario(registry, cfg, seed))
        if result.outcome == "victory":
            break
    else:
        pytest.fail("нет победы среди первых 100 сидов")
    scenario = result.scenario
    world = scenario.world
    assert world.npcs["boss"].status == "dead"
    assert world.flags["npc_dead:boss"] is True
    # безымянные гоблины следа в мире не оставляют
    assert [k for k in world.flags if k.startswith("npc_dead:")] == ["npc_dead:boss"]
    assert world.flags["combat_ended:fight_1"] is True
    save_slot(tmp_path, bundle_of(scenario), "auto", saved_at=SAVED_AT)
    loaded = load_slot(tmp_path, "sim", "auto")
    assert loaded.world == world
    trigger = loaded.world.npcs["boss"].opportunity[0]
    hero = loaded.heroes[0]
    assert evaluate(trigger.if_, loaded.world, hero).truth == Truth.TRUE
    assert is_ready(trigger, loaded.world.clock.now_s)
    fire(trigger, loaded.world.clock.now_s)
    assert not is_ready(trigger, loaded.world.clock.now_s)


# критерий 3: миграция v0 -> v1

def test_v0_fixture_loads_as_v1_with_backup(tmp_path):
    slot = tmp_path / "old_world" / "slots" / "auto"
    shutil.copytree(FIXTURE_V0, slot)
    original = tree(FIXTURE_V0)
    context = MigrationContext.from_registry(load_registry())
    loaded = load_slot(tmp_path, "old_world", "auto", backup_ts=BACKUP_TS, context=context)
    assert loaded.manifest.schema_version == CURRENT_SCHEMA_VERSION
    assert [h.id for h in loaded.heroes] == ["h1"]
    assert loaded.manifest.heroes == ["h1"]
    assert loaded.chronicle == Chronicle()
    assert loaded.memory == Memory()
    backups = sorted((tmp_path / "old_world" / "backups").glob("auto-v0-*"))
    assert len(backups) == 1
    assert tree(backups[0]) == original
    # на диске уже текущая версия, повторная загрузка бэкап не плодит
    manifest_text = (slot / "manifest.json").read_text(encoding="utf-8")
    assert f'"schema_version": {CURRENT_SCHEMA_VERSION}' in manifest_text
    assert load_slot(tmp_path, "old_world", "auto", backup_ts=BACKUP_TS, context=context) == loaded
    assert len(list((tmp_path / "old_world" / "backups").glob("auto-v0-*"))) == 1


# чек-лист релиза этапа 1

def test_release_checklist_combat_fields_are_typed():
    for name in ("active_combat", "pending_decision"):
        annotation = SessionState.model_fields[name].annotation
        assert annotation is not dict
        assert "dict" not in str(annotation)


def test_release_checklist_chapter_guard_is_strict_xfail():
    text = (TESTS / "unit" / "state" / "test_save_bundle.py").read_text(encoding="utf-8")
    found = re.search(
        r"@pytest\.mark\.xfail\(strict=True[^\n]*\)\n"
        r"@pytest\.mark\.parametrize\(\"name\", \[\"current_chapter\"\]\)\n"
        r"def test_session_field_is_not_bare_dict",
        text,
    )
    # этап 3: current_chapter типизирован (ChapterState), метка xfail снята, сторож обычный
    assert found is None
    assert "dict" not in str(SessionState.model_fields["current_chapter"].annotation)
    assert "dict" not in str(SessionState.model_fields["current_scene"].annotation)


def test_architecture_guard_exists():
    assert (TESTS / "unit" / "test_architecture.py").is_file()


def test_hero_is_human_fighter_soldier(registry, cfg):
    hero = build_scenario("goblins3", registry, cfg, 1).heroes["hero"]
    assert (hero.sheet.species_id, hero.sheet.class_id) == ("human", "fighter")
    assert hero.sheet.background.name == "Солдат"
