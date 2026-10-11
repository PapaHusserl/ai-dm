# Сквозной сценарий этапа 2 на моке: «разговор -> проверка -> бой» (STAGE2-PLAN, «Критерий
# готово»). Мир «Вейл» (game.starter), герой Арн, сид, GameApp как точка входа UI. Живых вызовов
# нет: первые три хода -- YAML tests/fixtures/scripts/talk_check_fight.yaml (ScriptedAdapter),
# дальше ReactiveAdapter из game_kit (классификация текста героя, выбор ключевого NPC,
# defeat_outcome -- по режиму запроса, потому что число ходов боя зависит от бросков), потом
# Replay по журналу.
# Контракт API -- tests/unit/game/game_kit.py.
#
# Как сделать бой достижимым детерминированно: HP героя поднимается до 200 (победа без риска
# поражения при любых бросках), героя ведёт жадная тактика по номерам (атака / шаг к врагу), а
# сценарий поражения слабит героя до 1 HP ПОСЛЕ старта боя (чтобы ход со start_combat не мог
# закончиться поражением до первого решения героя). Сид один и тот же; исход от порядка бросков
# не зависит.
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unit" / "game"))

from game_kit import (  # noqa: E402
    OPUS,
    SAVED_AT,
    ReactiveAdapter,
    ScriptThenReactive,
    attack_or_move_number,
    core_dump,
    end_turn_number,
    make_app,
    player_action_input,
    requests_with_tools,
    scripted_from_yaml,
    settings,
    state_of,
    tool_names,
)
from slots_kit import list_slots, saved_close_reason  # noqa: E402

from ai_dm.llm.replay import ReplayAdapter, ReplayDivergence  # noqa: E402
from ai_dm.persistence.store import load_slot  # noqa: E402
from ai_dm.protocol.schema import tool_set  # noqa: E402
from ai_dm.rules.xp import combat_xp  # noqa: E402

SEED = 7
TALK = "Спрашиваю трактирщика, что слышно в округе"
PERSUADE = "Убеждаю трактирщика пустить меня в подвал"
DESCEND = "Спускаюсь в подвал"
KICK = "Опрокидываю бочку на ближнего гоблина"
IMPROVISE = {
    "skill": "athletics", "category": "medium", "effect": "prone", "target": "goblin_1",
    "zone": "",
}
NARRATE = {d["name"] for d in tool_set("combat_narrate")}
CLASSIFY = {"player_action", "unsupported_action"}
ENEMIES = ["goblin_warrior", "goblin_warrior", "goblin_boss"]


class Story:
    def __init__(self, app, adapter, replies):
        self.app = app
        self.adapter = adapter
        self.replies = replies

    @property
    def bundle(self):
        return self.app.bundle


def new_app(registry, root, adapter, hero_hp=200):
    from slots_kit import WORLD_TEXT

    from ai_dm.game.starter import new_world

    rules = settings().rules
    bundle = new_world(
        registry, rules, hero="arn", seed=SEED, world_id="vale-e2e", saved_at=SAVED_AT
    )
    hero = bundle.heroes[0]
    hero.creature.hp_max = hero.creature.hp_current = hero_hp
    return make_app(registry, root, adapter, bundle=bundle, world_text=WORLD_TEXT, model=OPUS)


def live_adapter(**reactive):
    first = scripted_from_yaml("talk_check_fight.yaml")
    return ScriptThenReactive(first, ReactiveAdapter(**reactive))


def three_turns(app, talk=TALK):
    return [app.handle(talk), app.handle(PERSUADE), app.handle(DESCEND)]


def fight(app, pick, first_text=None, limit=80):
    replies = []
    if first_text is not None:
        replies.append(app.handle(first_text))
    for _ in range(limit):
        if app.bundle.session.active_combat is None:
            break
        replies.append(app.handle(str(pick(app.runner))))
        assert replies[-1].turn.committed is True
    return replies


def victory_story(registry, root):
    adapter = live_adapter(classify=[player_action_input([], improvise=IMPROVISE)])
    app = new_app(registry, root, adapter)
    replies = three_turns(app)
    replies += fight(app, attack_or_move_number, first_text=KICK)
    return Story(app, adapter, replies)


def defeat_story(registry, root):
    adapter = live_adapter(defeat="text_first")
    app = new_app(registry, root, adapter)
    replies = three_turns(app)
    app.bundle.heroes[0].creature.hp_current = 1
    replies += fight(app, end_turn_number)
    return Story(app, adapter, replies)


def requests_dump(adapter):
    return [r.model_dump_json() for r in adapter.requests]


# ходы 1-3: разговор, проверка, старт боя

def test_turn_1_text_and_offered_choices(registry, tmp_path):
    app = new_app(registry, tmp_path, live_adapter())
    reply = app.handle(TALK)
    assert reply.turn.committed is True
    assert "подвале" in reply.narration
    assert app.bundle.session.offered_choices == ["Спросить про подвал", "Заказать эль"]
    assert reply.turn.requests == ["offer_choices"]


def test_turn_1_prompt_has_world_text_and_player_input(registry, tmp_path):
    from slots_kit import WORLD_TEXT

    adapter = live_adapter()
    app = new_app(registry, tmp_path, adapter)
    app.handle(TALK)
    request = adapter.requests[0]
    assert state_of(request)["player_input"] == TALK
    assert WORLD_TEXT in request.system[1].text
    assert tool_names(request) == {d["name"] for d in tool_set("explore")}
    assert request.model == OPUS


def test_turn_2_skill_check_gives_dc_15_and_roll_line(registry, tmp_path):
    adapter = live_adapter()
    app = new_app(registry, tmp_path, adapter)
    app.handle(TALK)
    draws = app.bundle.world.rng.draws
    reply = app.handle(PERSUADE)
    assert reply.turn.requests == ["skill_check"]
    assert "СЛ 15" in reply.turn.lines[0]
    assert app.bundle.world.rng.draws > draws
    result_block = adapter.requests[3].messages[-1].content[0]
    assert '"dc": 15' in result_block.content
    assert "СЛ 15" in result_block.content


def test_turn_3_starts_combat_with_goblins_and_grakh(registry, tmp_path):
    app = new_app(registry, tmp_path, live_adapter())
    three_turns(app)
    state = app.bundle.session.active_combat
    assert [z.id for z in state.zones] == ["stairs", "floor", "barrels"]
    assert {p.ref for p in state.participants} == {"hero", "goblin_1", "goblin_2", "grakh"}
    by_ref = {p.ref: p for p in state.participants}
    assert by_ref["grakh"].monster_id == "goblin_boss"
    assert by_ref["grakh"].controller == "external"
    assert by_ref["goblin_1"].controller == "engine"
    assert state.groups["goblins"].intent == "capture"
    assert state.groups["goblins"].leader_id == "grakh"
    assert state.initiative_order[state.turn_index] == "hero"


def test_turn_3_tool_result_has_npc_turn_log(registry, tmp_path):
    adapter = live_adapter()
    app = new_app(registry, tmp_path, adapter)
    three_turns(app)
    state = app.bundle.session.active_combat
    body = adapter.requests[5].messages[-1].content[0].content
    for line in state.log:
        assert line in body


def test_turns_1_to_3_are_committed_with_records(registry, tmp_path):
    app = new_app(registry, tmp_path, live_adapter())
    three_turns(app)
    assert app.bundle.session.turn_seq == 3
    assert [t.requests for t in app.bundle.memory.recent_turns] == [
        ["offer_choices"], ["skill_check"], ["start_combat"],
    ]


# бой: ввод номером и текстом -> победа

def test_victory_fight_ends_in_victory(registry, tmp_path):
    story = victory_story(registry, tmp_path)
    assert story.replies[-1].turn.combat_outcome == "victory"
    assert story.bundle.session.active_combat is None


def test_fight_first_turn_by_text_with_improvise_rest_by_numbers(registry, tmp_path):
    story = victory_story(registry, tmp_path)
    classify = requests_with_tools(story.adapter, CLASSIFY)
    assert len(classify) == 2
    assert state_of(classify[0])["player_input"] == KICK
    assert story.replies[3].turn.requests == ["player_action"]
    # остальные ходы героя -- номерами: только повествование
    number_replies = story.replies[4:]
    assert number_replies
    assert all(r.turn.requests == [] for r in number_replies)
    assert len(requests_with_tools(story.adapter, NARRATE)) == len(story.replies) - 3


def test_fight_improvise_rolled_dice(registry, tmp_path):
    story = victory_story(registry, tmp_path)
    log = [line for r in story.replies[3:] for line in r.turn.log]
    assert any("импровизация (Лежит)" in line for line in log)


def test_victory_xp_is_sum_of_cr_xp(registry, tmp_path):
    story = victory_story(registry, tmp_path)
    assert story.bundle.heroes[0].sheet.xp == combat_xp(ENEMIES, registry) == 300


def test_victory_sets_flags_and_kills_grakh(registry, tmp_path):
    story = victory_story(registry, tmp_path)
    flags = story.bundle.world.flags
    assert flags["combat_ended:combat_1"] is True
    assert flags["npc_dead:grakh"] is True
    assert story.bundle.world.npcs["grakh"].status == "dead"


def test_victory_closes_scene_and_autosaves(registry, tmp_path):
    story = victory_story(registry, tmp_path)
    assert saved_close_reason(tmp_path, "vale-e2e") == "combat_ended"
    assert story.bundle.session.current_scene.id == "scene_2"
    assert story.bundle.session.current_scene.closed_reason is None
    assert list_slots(tmp_path, "vale-e2e") == ["auto"]
    saved = load_slot(tmp_path, "vale-e2e", "auto")
    assert saved.session.active_combat is None
    assert saved.session.current_scene.id == "scene_1"
    assert saved.session.current_scene.closed_reason == "combat_ended"
    assert saved.world.flags["combat_ended:combat_1"] is True
    assert saved.heroes[0].sheet.xp == 300


def test_victory_offers_level_up_then_applies_it(registry, tmp_path):
    story = victory_story(registry, tmp_path)
    last = story.replies[-1]
    assert last.pending == "level_up"
    assert last.menu == ["average", "roll"]
    done = story.app.choose("average")
    assert done.pending is None
    assert story.bundle.heroes[0].sheet.level == 2


def test_every_fight_turn_is_one_run_and_all_committed(registry, tmp_path):
    story = victory_story(registry, tmp_path)
    run_ids = [r.turn.run_id for r in story.replies]
    assert len(set(run_ids)) == len(run_ids)
    records = story.app.journal.read_records()
    assert {r["turn_status"] for r in records} == {"committed"}
    assert {r["run_id"] for r in records} == set(run_ids)


def test_cost_is_accounted_for_the_whole_story(registry, tmp_path):
    story = victory_story(registry, tmp_path)
    text = "\n".join(story.app.handle("/cost").lines)
    assert "narrator" in text
    assert OPUS in text


# детерминизм

def test_two_runs_give_byte_equal_bundles_and_requests(registry, tmp_path):
    one = victory_story(registry, tmp_path / "one")
    two = victory_story(registry, tmp_path / "two")
    assert core_dump(one.bundle) == core_dump(two.bundle)
    assert requests_dump(one.adapter) == requests_dump(two.adapter)
    assert [r.narration for r in one.replies] == [r.narration for r in two.replies]


# поражение

def test_defeat_requires_defeat_outcome(registry, tmp_path):
    story = defeat_story(registry, tmp_path)
    last = story.replies[-1].turn
    assert last.combat_outcome == "defeat_pending"
    assert "defeat_outcome" in last.requests
    notes = [
        r for r in requests_with_tools(story.adapter, NARRATE)
        if len(r.messages) == 3 and "defeat_outcome" in r.messages[-1].content[0].text
    ]
    assert notes


def test_defeat_applies_consequence_and_closes_scene(registry, tmp_path):
    story = defeat_story(registry, tmp_path)
    bundle = story.bundle
    assert bundle.heroes[0].scars == ["Шрам на плече"]
    assert bundle.heroes[0].sheet.xp == 0
    assert bundle.session.active_combat is None
    assert bundle.world.flags["combat_ended:combat_1"] is True
    assert saved_close_reason(tmp_path, "vale-e2e") == "combat_ended"
    assert list_slots(tmp_path, "vale-e2e") == ["auto"]


def test_defeat_asks_key_npc_about_intent_when_hero_falls(registry, tmp_path):
    story = defeat_story(registry, tmp_path)
    asked = requests_with_tools(story.adapter, {"npc_action"})
    assert asked
    options = state_of(asked[0])["player_input"].splitlines()
    assert "- keep" in options
    assert "- intent:kill" in options


def test_no_level_up_after_defeat(registry, tmp_path):
    story = defeat_story(registry, tmp_path)
    assert story.replies[-1].pending is None


# replay

def test_replay_reproduces_the_same_bundle(registry, tmp_path):
    story = victory_story(registry, tmp_path / "live")
    records = story.app.journal.read_records()
    replayed = new_app(registry, tmp_path / "replay", ReplayAdapter(records))
    three_turns(replayed)
    fight(replayed, attack_or_move_number, first_text=KICK)
    assert core_dump(replayed.bundle) == core_dump(story.bundle)


def test_replay_with_changed_first_input_diverges(registry, tmp_path):
    story = victory_story(registry, tmp_path / "live")
    records = story.app.journal.read_records()
    replayed = new_app(registry, tmp_path / "replay", ReplayAdapter(records))
    before = core_dump(replayed.bundle)
    with pytest.raises(ReplayDivergence):
        replayed.handle("Совсем другая фраза")
    assert core_dump(replayed.bundle) == before


def test_replay_with_changed_later_input_diverges_at_that_turn(registry, tmp_path):
    story = victory_story(registry, tmp_path / "live")
    records = story.app.journal.read_records()
    replayed = new_app(registry, tmp_path / "replay", ReplayAdapter(records))
    replayed.handle(TALK)
    with pytest.raises(ReplayDivergence):
        replayed.handle("Грожу трактирщику кулаком")
    assert replayed.bundle.session.turn_seq == 1
