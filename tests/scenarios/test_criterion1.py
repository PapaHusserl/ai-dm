# Критерий 1 этапа 1 -- «бой детерминирован» (ARCHITECTURE, «Тестовые сценарии»).
# Фикстура «гоблины-3» -- ai_dm.devtools.sim_combat.build_scenario("goblins3", ...) (контракт и
# состав -- в шапке tests/unit/devtools/test_sim_combat.py): hero (воин; вариант "weak" --
# волшебник)
# у двери, goblin_1/goblin_2 в центре зала, goblin_3 с луком на балконе (cover_half), группа
# "goblins" (лидер goblin_1). Контракт боя и событий -- в шапке tests/unit/combat/combat_kit.py.
#
# СИДЫ. Константы S_* ниже -- ФИКСИРОВАННЫЕ сиды сценариев (подобраны и вписаны). Сид можно найти
# заново (например, после осознанной смены правил боя):
#   S_WIN          -- первый сид победы воина (нужен для golden):
#       uv run python -m ai_dm.devtools.sim_combat --scenario goblins3 --find-outcome victory
#   S_DOWN_CAPTURE -- слабый герой, намерение capture, исход defeat_pending:
#       uv run python -m ai_dm.devtools.sim_combat --scenario goblins3 --variant weak \
#           --intent capture --find-outcome defeat_pending
#   S_DOWN_KILL    -- слабый герой, намерение kill, исход hero_dead:
#       uv run python -m ai_dm.devtools.sim_combat --scenario goblins3 --variant weak \
#           --intent kill --find-outcome hero_dead
# Новое число вписывается в константу и перегенерируется golden.
#
# GOLDEN tests/golden/goblins3_win.txt -- вывод CLI для S_WIN, ровно stdout:
#   uv run python -m ai_dm.devtools.sim_combat --seed <S_WIN> --scenario goblins3 \
#       > tests/golden/goblins3_win.txt
# ПРАВИЛО ПЕРЕГЕНЕРАЦИИ: golden меняется ОСОЗНАННО -- только после изменения правил боя / лога
# (в том числе имён в логе, п. 16 ревью партии 5), с просмотром диффа (что именно поменялось в
# ходе боя); падение golden без такой правки -- баг. После перегенерации S_* проверяются заново.
#
# Свойства на 200 сидах (воин и слабый герой): бой кончается за <= 100 раундов, HP в [0, max],
# никто не ходит дважды за раунд (события turn_started), ячейки >= 0, мёртвые не ходят,
# время мира растёт ровно на раунды × 6 с.
# Сценарии падения героя: S_DOWN_CAPTURE -> apply_defeat_outcome([rob, left_to_die]);
# S_DOWN_KILL -> hero_dead с DeathRecord(cause="goal", by=<гоблин>); смешанная группа; две группы
# (решает группа последнего удара); герой + Guard; сейв посреди боя (раунд 2) -> загрузка ->
# доигрыш идентичен непрерывному. Не покрыто здесь: ScriptedRng-сценарии death saves
# (3 успеха -> стабилен, nat 20 -> 1 HP) -- см. tests/unit/combat/test_downed.py.
from collections import Counter
from pathlib import Path

import pytest

from ai_dm.combat.defeat import DefeatParams, apply_defeat_outcome
from ai_dm.combat.engine import CombatEngine
from ai_dm.core.rng import Rng
from ai_dm.devtools.sim_combat import build_scenario, find_seed, main, simulate
from ai_dm.persistence.store import load_slot, write_slot
from ai_dm.rules.death_saves import is_stable
from ai_dm.state.combat import Group, Participant
from ai_dm.state.creature import CreatureState
from ai_dm.state.memory import Chronicle, Memory
from ai_dm.state.save import Manifest, SaveBundle
from ai_dm.state.session import SessionState

S_WIN = 2  # первый сид победы воина (find-outcome victory)
S_DOWN_CAPTURE = 0  # первый сид defeat_pending: weak, capture
S_DOWN_KILL = 0  # первый сид hero_dead: weak, kill (есть спасброски от смерти)

GOLDEN = Path(__file__).resolve().parents[1] / "golden" / "goblins3_win.txt"
TERMINAL = {"victory", "defeat_pending", "hero_dead", "fled", "ended_by_master"}
SEEDS = range(200)


def build(registry, cfg, seed, **kwargs):
    return build_scenario("goblins3", registry, cfg, seed, **kwargs)


def run(registry, cfg, seed, tweak=None, **kwargs):
    scenario = build(registry, cfg, seed, **kwargs)
    if tweak is not None:
        tweak(scenario)
    start = scenario.world.clock.now_s
    return simulate(scenario), start


def seed_for(constant, registry, cfg, outcome, **kwargs):
    if constant is not None:
        return constant
    found = find_seed("goblins3", outcome, registry=registry, cfg=cfg, **kwargs)
    assert found is not None, f"не найден сид для {outcome} {kwargs}: подберите S_*"
    return found


def types(events):
    return [e.type for e in events]


# фикстура

def test_scenario_is_the_goblins_fixture(registry, cfg):
    state = build(registry, cfg, 1).state
    assert [p.ref for p in state.participants] == ["hero", "goblin_1", "goblin_2", "goblin_3"]
    assert state.groups["goblins"].leader_id == "goblin_1"


# имена в логе (п. 16 ревью партии 5)

def test_log_shows_numbered_monster_names_instead_of_refs(registry, cfg):
    result, _ = run(registry, cfg, 1)
    text = "\n".join(result.log)
    for number in (1, 2, 3):
        assert f"Воин-гоблин {number}" in text
    for ref in ("goblin_1", "goblin_2", "goblin_3"):
        assert ref not in text


def test_no_shot_in_the_three_zone_hall_has_the_range_penalty(registry, cfg):
    # К1 (В1а): через одну зону 60 фт < 80 фт короткого лука -- «помеха: дальность» здесь невозможна
    for seed in range(40):
        result, _ = run(registry, cfg, seed)
        assert "помеха: дальность" not in "\n".join(result.log)


def test_hero_dead_only_with_a_dead_hero_in_every_run(registry, cfg):
    for seed in range(60):
        result, _ = run(registry, cfg, seed, variant="weak")
        if result.outcome == "hero_dead":
            assert result.scenario.heroes["hero"].status == "dead"


# детерминизм

def test_two_runs_with_one_seed_are_byte_identical(registry, cfg):
    first, _ = run(registry, cfg, 11)
    second, _ = run(registry, cfg, 11)
    assert first.log == second.log
    assert first.scenario.state.model_dump_json() == second.scenario.state.model_dump_json()
    assert first.scenario.world.model_dump_json() == second.scenario.world.model_dump_json()
    assert (
        first.scenario.heroes["hero"].model_dump_json()
        == second.scenario.heroes["hero"].model_dump_json()
    )
    assert first.scenario.rng.state == second.scenario.rng.state
    assert [e.model_dump_json() for e in first.events] == [
        e.model_dump_json() for e in second.events
    ]


def test_weak_hero_runs_are_deterministic_too(registry, cfg):
    first, _ = run(registry, cfg, 11, variant="weak")
    second, _ = run(registry, cfg, 11, variant="weak")
    assert first.log == second.log
    assert first.scenario.rng.state == second.scenario.rng.state


def test_other_seed_gives_other_log(registry, cfg):
    first, _ = run(registry, cfg, 1)
    second, _ = run(registry, cfg, 2)
    assert first.log != second.log


def test_the_fight_actually_draws_from_the_rng(registry, cfg):
    result, _ = run(registry, cfg, 1)
    assert result.scenario.rng.state.draws > 0
    assert result.scenario.rng.state != build(registry, cfg, 1).rng.state


# golden

def test_golden_log_for_the_winning_seed(registry, cfg, capsys):
    assert GOLDEN.is_file(), (
        "нет tests/golden/goblins3_win.txt: подберите S_WIN и сгенерируйте файл "
        "(команда в шапке test_criterion1.py)"
    )
    assert main(["--seed", str(S_WIN), "--scenario", "goblins3"]) == 0
    assert capsys.readouterr().out == GOLDEN.read_text(encoding="utf-8")


def test_winning_seed_really_wins(registry, cfg):
    result, _ = run(registry, cfg, S_WIN)
    assert result.outcome == "victory"


# слабый герой: капитуляция и смерть

def test_downed_hero_with_capture_intent_is_pending_defeat(registry, cfg):
    seed = seed_for(
        S_DOWN_CAPTURE, registry, cfg, "defeat_pending", variant="weak", intent="capture"
    )
    result, _ = run(registry, cfg, seed, variant="weak", intent="capture")
    hero = result.scenario.heroes["hero"]
    assert result.outcome == "defeat_pending"
    assert hero.creature.hp_current == 0
    assert hero.creature.death_saves.failures == 0
    assert hero.status == "active"
    assert is_stable(hero.creature)


def test_pending_defeat_then_rob_and_left_to_die(registry, cfg):
    seed = seed_for(
        S_DOWN_CAPTURE, registry, cfg, "defeat_pending", variant="weak", intent="capture"
    )
    result, _ = run(registry, cfg, seed, variant="weak", intent="capture")
    scenario = result.scenario
    hero = scenario.heroes["hero"]
    money_before = hero.money_cp
    items_before = sum(e.qty for e in hero.inventory)
    clock_before = scenario.world.clock.now_s
    done = apply_defeat_outcome(
        scenario.state, ["rob", "left_to_die"], DefeatParams(), world=scenario.world,
        hero=hero, registry=registry, cfg=cfg, rng=scenario.rng,
    )
    assert done.status in ("applied", "clamped")
    assert hero.money_cp == money_before - money_before * cfg.defeat.robbery_gold_percent // 100
    assert sum(e.qty for e in hero.inventory) < items_before
    assert hero.creature.hp_current == cfg.defeat.left_to_die_hp
    hours = (scenario.world.clock.now_s - clock_before) / 3600
    assert 1 <= hours <= 8


def test_downed_hero_with_kill_intent_dies_with_a_goal_cause(registry, cfg):
    seed = seed_for(S_DOWN_KILL, registry, cfg, "hero_dead", variant="weak", intent="kill")
    result, _ = run(registry, cfg, seed, variant="weak", intent="kill")
    hero = result.scenario.heroes["hero"]
    assert result.outcome == "hero_dead"
    assert hero.status == "dead"
    assert hero.death.cause == "goal"
    assert hero.death.by in ("goblin_1", "goblin_2", "goblin_3")
    died = [e for e in result.events if e.type == "hero_died"]
    assert [e.data for e in died] == [{"id": "hero", "cause": "goal", "by": hero.death.by}]
    assert result.scenario.world.flags["hero_dead:hero"] is True


def test_melee_blows_on_the_lying_hero_are_crits_or_misses(registry, cfg):
    seed = seed_for(S_DOWN_KILL, registry, cfg, "hero_dead", variant="weak", intent="kill")
    result, _ = run(registry, cfg, seed, variant="weak", intent="kill")
    saved = False
    for event in result.events:
        if event.type == "death_save":
            saved = True
        if saved and event.type == "attack":
            data = event.data
            if data["target"] == "hero" and data["mode"] == "melee":
                assert data["outcome"] in ("crit", "miss")
    assert saved


# смешанная группа и две группы

def mixed_group(scenario):
    # лидер -- capture, рядовой лично настроен на kill
    scenario.state.groups["goblins"].intent = "capture"
    for p in scenario.state.participants:
        if p.ref == "goblin_2":
            p.intent = "kill"


def test_mixed_group_follows_the_leader_capture(registry, cfg):
    outcomes = Counter()
    for seed in range(120):
        result, _ = run(registry, cfg, seed, tweak=mixed_group, variant="weak", intent="capture")
        outcomes[result.outcome] += 1
    assert outcomes["defeat_pending"] > 0
    assert set(outcomes) <= {"victory", "defeat_pending"}


def two_groups(scenario):
    # goblin_3 -- отдельная группа с kill; goblin_1 и goblin_2 -- capture
    scenario.state.groups["goblins"].intent = "capture"
    scenario.state.groups["archers"] = Group(leader_id="goblin_3", intent="kill")
    for p in scenario.state.participants:
        if p.ref == "goblin_3":
            p.group_id = "archers"


def test_two_groups_the_group_of_the_last_blow_decides(registry, cfg):
    seen = set()
    for seed in range(200):
        result, _ = run(registry, cfg, seed, tweak=two_groups, variant="weak", intent="capture")
        state = result.scenario.state
        if state.defeat_group_id is None:
            continue
        seen.add(state.defeat_group_id)
        if state.defeat_group_id == "goblins":
            assert result.outcome == "defeat_pending"
        else:
            assert state.defeat_group_id == "archers"
            assert result.outcome in ("hero_dead", "victory")
    assert seen == {"goblins", "archers"}


# герой + Guard

def with_guard(scenario):
    monster = scenario.registry.get("monster", "guard")
    scenario.state.participants.append(
        Participant(
            ref="guard_1", side="heroes", group_id="allies", zone_id="door",
            monster_id="guard", name="Стражник",
            creature=CreatureState(hp_current=monster.hp, hp_max=monster.hp),
        )
    )
    scenario.state.groups["allies"] = Group(leader_id="guard_1")


def test_hero_and_guard_win_and_the_fallen_hero_is_stabilized(registry, cfg):
    rescued = 0
    for seed in range(200):
        result, _ = run(registry, cfg, seed, tweak=with_guard, variant="weak", intent="kill")
        hero = result.scenario.heroes["hero"]
        if result.outcome == "victory" and hero.creature.hp_current == 0:
            rescued += 1
            assert is_stable(hero.creature)
            assert hero.status == "active"
            assert hero.creature.death_saves.failures == 0
    assert rescued > 0


def test_hero_and_guard_usually_beat_three_goblins(registry, cfg):
    wins = 0
    for seed in range(60):
        result, _ = run(registry, cfg, seed, tweak=with_guard, intent="kill")
        wins += result.outcome == "victory"
    assert wins > 30


# свойства на 200 сидах

@pytest.fixture(scope="module")
def strong_runs(registry, cfg):
    return [run(registry, cfg, seed) for seed in SEEDS]


@pytest.fixture(scope="module")
def weak_runs(registry, cfg):
    return [run(registry, cfg, seed, variant="weak") for seed in SEEDS]


def all_runs(strong_runs, weak_runs):
    return strong_runs + weak_runs


def test_every_fight_ends_within_100_rounds(strong_runs, weak_runs):
    for result, _ in all_runs(strong_runs, weak_runs):
        assert result.outcome in TERMINAL
        assert 1 <= result.rounds <= 100


def test_hp_stays_between_zero_and_max(strong_runs, weak_runs):
    for result, _ in all_runs(strong_runs, weak_runs):
        scenario = result.scenario
        creatures = [h.creature for h in scenario.heroes.values()]
        creatures += [p.creature for p in scenario.state.participants if p.creature is not None]
        for creature in creatures:
            assert 0 <= creature.hp_current <= creature.hp_max


def test_nobody_acts_twice_in_a_round(strong_runs, weak_runs):
    for result, _ in all_runs(strong_runs, weak_runs):
        turns = Counter(
            (e.data["round"], e.data["id"]) for e in result.events if e.type == "turn_started"
        )
        assert max(turns.values()) == 1


def test_spell_slots_never_go_negative(strong_runs, weak_runs):
    for result, _ in all_runs(strong_runs, weak_runs):
        for hero in result.scenario.heroes.values():
            for name, pool in hero.creature.resources.items():
                assert pool.current >= 0, name


def test_the_dead_do_not_act(strong_runs, weak_runs):
    for result, _ in all_runs(strong_runs, weak_runs):
        dead_at = {}
        for index, event in enumerate(result.events):
            if event.type in ("monster_died", "hero_died"):
                dead_at[event.data["id"]] = index
            if event.type == "turn_started" and event.data["id"] in dead_at:
                pytest.fail(f"{event.data['id']} ходит после смерти")


def test_time_grows_by_rounds_times_six_seconds(strong_runs, weak_runs):
    for result, start in all_runs(strong_runs, weak_runs):
        assert result.scenario.world.clock.now_s == start + result.rounds * 6


def test_outcome_matches_the_final_state(strong_runs, weak_runs):
    for result, _ in all_runs(strong_runs, weak_runs):
        scenario = result.scenario
        hero = scenario.heroes["hero"]
        if result.outcome == "victory":
            for p in scenario.state.participants:
                if p.side == "enemies":
                    assert p.status != "active" or p.creature.hp_current == 0
        if result.outcome == "hero_dead":
            assert hero.status == "dead"
        if result.outcome == "defeat_pending":
            assert hero.creature.hp_current == 0


def test_combat_ended_flag_is_set_in_every_run(strong_runs, weak_runs):
    for result, _ in all_runs(strong_runs, weak_runs):
        flag = f"combat_ended:{result.scenario.state.id}"
        assert result.scenario.world.flags[flag] is True
        assert types(result.events).count("combat_ended") == 1


def test_the_strong_hero_wins_sometimes_and_the_weak_one_loses_sometimes(strong_runs, weak_runs):
    assert any(r.outcome == "victory" for r, _ in strong_runs)
    assert any(r.outcome != "victory" for r, _ in weak_runs)


# контракт событий для авто-флагов (D11)

def test_event_keys_are_exactly_the_contract(registry, cfg):
    expected = {
        "location_visited": {"id"},
        "combat_ended": {"id"},
        "item_gained": {"hero", "item"},
        "monster_died": {"id", "monster_id", "by"},
        "hero_died": {"id", "cause", "by"},
    }
    seen = set()
    for seed in range(40):
        result, _ = run(registry, cfg, seed, variant="weak", intent="capture")
        events = list(result.events)
        scenario = result.scenario
        if result.outcome == "defeat_pending":
            hero = scenario.heroes["hero"]
            done = apply_defeat_outcome(
                scenario.state, ["capture", "rob"], DefeatParams(lair_location_id="goblin_den"),
                world=scenario.world, hero=hero, registry=registry, cfg=cfg, rng=scenario.rng,
            )
            events += done.events
        for event in events:
            if event.type in expected:
                seen.add(event.type)
                assert set(event.data) == expected[event.type], event.type
    assert {"combat_ended", "monster_died"} <= seen


def test_anonymous_monsters_leave_no_trace_in_the_world(strong_runs):
    for result, _ in strong_runs:
        scenario = result.scenario
        assert scenario.world.npcs == {}
        assert [k for k in scenario.world.flags if k.startswith("npc_dead:")] == []


def test_hp_of_anonymous_monsters_survives_the_save_cycle(registry, cfg):
    seed, variant = midfight_seed(registry, cfg)
    engine = engine_at_round_two(registry, cfg, seed, variant)
    before = {
        p.ref: (p.creature.hp_current, p.status)
        for p in engine.state.participants if p.creature is not None
    }
    bundle = SaveBundle.model_validate_json(make_bundle(engine).model_dump_json())
    after = {
        p.ref: (p.creature.hp_current, p.status)
        for p in bundle.session.active_combat.participants if p.creature is not None
    }
    assert after == before


# сейв посреди боя

def midfight_seed(registry, cfg):
    for variant in ("default", "weak"):
        for seed in range(100):
            result, _ = run(registry, cfg, seed, variant=variant)
            if result.rounds >= 3:
                return seed, variant
    pytest.fail("нет боя длиннее 2 раундов среди первых 100 сидов")


def finish(engine):
    # доигрывает бой и снимает итог: состояние боя, мир, герои, состояние ГСЧ
    engine.run_to_end()
    engine.world.rng = engine.rng.state
    return (
        engine.state.model_dump_json(),
        engine.world.model_dump_json(),
        [h.model_dump_json() for h in engine.heroes.values()],
        engine.rng.state,
    )


def continuous_result(registry, cfg, seed, variant):
    engine = build(registry, cfg, seed, variant=variant).engine()
    engine.start()
    return finish(engine)


def engine_at_round_two(registry, cfg, seed, variant):
    engine = build(registry, cfg, seed, variant=variant).engine()
    engine.start()
    while engine.state.round < 2 and not engine.is_over:
        engine.step()
    assert engine.state.round == 2
    assert not engine.is_over
    engine.world.rng = engine.rng.state
    return engine


def make_bundle(engine):
    hero_ids = list(engine.heroes)
    return SaveBundle(
        manifest=Manifest(
            schema_version=1, engine_version="0.1.0", world_id=engine.world.world_id,
            campaign_id=None, slot="auto", saved_at="2026-01-01T12:00:00Z",
            current_hero_id=hero_ids[0], heroes=hero_ids,
        ),
        world=engine.world, chronicle=Chronicle(), memory=Memory(),
        heroes=list(engine.heroes.values()),
        session=SessionState(active_combat=engine.state),
    )


def resume(bundle, registry, cfg):
    heroes = {h.id: h for h in bundle.heroes}
    return CombatEngine(
        bundle.session.active_combat, bundle.world, heroes, registry, cfg,
        Rng.from_state(bundle.world.rng),
    )


def test_save_in_round_two_and_resume_equals_continuous_run(registry, cfg, tmp_path):
    seed, variant = midfight_seed(registry, cfg)
    expected = continuous_result(registry, cfg, seed, variant)
    engine = engine_at_round_two(registry, cfg, seed, variant)
    world_id = engine.world.world_id
    write_slot(
        tmp_path, world_id, make_bundle(engine), "auto", saved_at="2026-01-01T12:00:00Z"
    )
    loaded = load_slot(tmp_path, world_id, "auto")
    assert loaded.session.active_combat.round == 2
    assert finish(resume(loaded, registry, cfg)) == expected


def test_json_roundtrip_in_round_two_equals_continuous_run(registry, cfg):
    seed, variant = midfight_seed(registry, cfg)
    expected = continuous_result(registry, cfg, seed, variant)
    engine = engine_at_round_two(registry, cfg, seed, variant)
    bundle = SaveBundle.model_validate_json(make_bundle(engine).model_dump_json())
    assert finish(resume(bundle, registry, cfg)) == expected


def test_saved_combat_is_the_same_object_state_as_in_memory(registry, cfg):
    seed, variant = midfight_seed(registry, cfg)
    engine = engine_at_round_two(registry, cfg, seed, variant)
    bundle = SaveBundle.model_validate_json(make_bundle(engine).model_dump_json())
    assert bundle.session.active_combat == engine.state
