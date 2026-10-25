# Этап 4, P1+ (R1): вход summarizer (SummarizerPromptBuilder.state_data) -- только известное
# герою. NPC: с непустым known_to_player, из локации сцены, или упомянутые по имени в ходах
# сцены; локации: visited=True и локация сцены. Герой в protocol_kit стоит в "vale".
from master_kit import make_bundle, make_ctx, turn_record

from ai_dm.core.clock import DAY, GameClock
from ai_dm.master.summarizer import SummarizerPromptBuilder
from ai_dm.state.world import NPC


def add_npc(bundle, npc_id, **fields):
    data = {"id": npc_id, "name": npc_id, "named": True, "means": ["m"]}
    data.update(fields)
    bundle.world.npcs[npc_id] = NPC(**data)


def state_of(registry, cfg, bundle):
    ctx = make_ctx(registry, cfg, bundle=bundle)
    return SummarizerPromptBuilder(ctx_app()).state_data(ctx)


def ctx_app():
    from llm_kit import app_cfg

    return app_cfg()


def npc_ids(state):
    return [n["id"] for n in state["npcs"]]


def location_ids(state):
    return [p["id"] for p in state["locations"]]


def scene_turn(bundle, n, narration, player_input="иду"):
    record = turn_record(n, narration)
    record.player_input = player_input
    record.scene_id = bundle.session.current_scene.id
    bundle.memory.recent_turns.append(record)


def test_unknown_npc_elsewhere_is_not_in_input(registry, cfg):
    bundle = make_bundle(registry)
    add_npc(bundle, "farmer", name="Фермер", location_id="forest")
    assert "farmer" not in npc_ids(state_of(registry, cfg, bundle))


def test_npc_without_location_and_secrets_is_not_in_input(registry, cfg):
    bundle = make_bundle(registry)
    assert "aldric" not in npc_ids(state_of(registry, cfg, bundle))


def test_npc_with_known_secret_is_in_input(registry, cfg):
    bundle = make_bundle(registry)
    add_npc(bundle, "spy", name="Шпион", location_id="forest", known_to_player=["s1"])
    assert "spy" in npc_ids(state_of(registry, cfg, bundle))


def test_npc_mentioned_in_scene_narration_is_in_input(registry, cfg):
    bundle = make_bundle(registry)
    add_npc(bundle, "farmer", name="Фермер", location_id="forest")
    scene_turn(bundle, 1, "К герою подошёл фермер и поклонился.")
    assert "farmer" in npc_ids(state_of(registry, cfg, bundle))


def test_npc_mentioned_in_scene_player_input_is_in_input(registry, cfg):
    bundle = make_bundle(registry)
    add_npc(bundle, "farmer", name="Фермер", location_id="forest")
    scene_turn(bundle, 1, "Тишина.", player_input="спрашиваю Фермера о дороге")
    assert "farmer" in npc_ids(state_of(registry, cfg, bundle))


def test_npc_mentioned_only_in_other_scene_turn_is_not_in_input(registry, cfg):
    bundle = make_bundle(registry)
    add_npc(bundle, "farmer", name="Фермер", location_id="forest")
    record = turn_record(1, "Фермер ушёл.")
    record.scene_id = "scene_0"
    bundle.memory.recent_turns.append(record)
    assert "farmer" not in npc_ids(state_of(registry, cfg, bundle))


def test_npc_in_scene_location_is_in_input(registry, cfg):
    bundle = make_bundle(registry)
    add_npc(bundle, "clerk", name="Писарь", location_id="vale")
    assert "clerk" in npc_ids(state_of(registry, cfg, bundle))


def test_unnamed_npc_is_not_in_input_even_if_known(registry, cfg):
    bundle = make_bundle(registry)
    add_npc(bundle, "guard", name="Стражник", named=False, location_id="vale",
            known_to_player=["s1"])
    assert "guard" not in npc_ids(state_of(registry, cfg, bundle))


def test_companion_of_hero_is_in_input(registry, cfg):
    bundle = make_bundle(registry)
    add_npc(bundle, "squire", name="Оруженосец", location_id="forest", follows="hero")
    assert "squire" in npc_ids(state_of(registry, cfg, bundle))


def test_unvisited_location_is_not_in_input(registry, cfg):
    bundle = make_bundle(registry)
    assert "goblin_den" not in location_ids(state_of(registry, cfg, bundle))


def test_visited_location_is_in_input(registry, cfg):
    bundle = make_bundle(registry)
    bundle.world.locations["forest"].visited = True
    assert "forest" in location_ids(state_of(registry, cfg, bundle))


def test_scene_location_is_in_input_even_if_not_visited(registry, cfg):
    bundle = make_bundle(registry)
    assert bundle.world.locations["vale"].visited is False
    assert "vale" in location_ids(state_of(registry, cfg, bundle))


def test_input_text_has_no_unknown_npc_or_location(registry, cfg):
    bundle = make_bundle(registry)
    add_npc(bundle, "farmer", name="Секретный_Фермер", location_id="forest")
    ctx = make_ctx(registry, cfg, bundle=bundle)
    request = SummarizerPromptBuilder(ctx_app()).build(ctx, "", "summarize_scene")
    text = request.messages[0].content[0].text
    assert "Секретный_Фермер" not in text
    assert "Логово" not in text


# Ж1 (docs/plan-zh1.md, п. 0.9): именованный NPC движка со скрытым именем идёт во вход под видом

def add_hidden(bundle, **fields):
    data = {
        "origin": "engine", "name": "Гракх", "location_id": "vale",
        "combat": {"label": "Воин-гоблин 1"},
    }
    data.update(fields)
    add_npc(bundle, "goblin_warrior_1", **data)


def name_in(state, npc_id):
    return [n["name"] for n in state["npcs"] if n["id"] == npc_id]


def test_hidden_name_is_shown_as_label_in_input(registry, cfg):
    bundle = make_bundle(registry)
    add_hidden(bundle)
    assert name_in(state_of(registry, cfg, bundle), "goblin_warrior_1") == ["Воин-гоблин 1"]


def test_known_name_is_shown_in_input(registry, cfg):
    bundle = make_bundle(registry)
    add_hidden(bundle, known_name="Гракх")
    assert name_in(state_of(registry, cfg, bundle), "goblin_warrior_1") == ["Гракх"]


def test_hidden_npc_elsewhere_is_in_input_when_label_is_said(registry, cfg):
    bundle = make_bundle(registry)
    add_hidden(bundle, location_id="forest")
    scene_turn(bundle, 1, "Воин-гоблин 1 пропал в лесу.")
    assert "goblin_warrior_1" in npc_ids(state_of(registry, cfg, bundle))


def test_hidden_npc_elsewhere_is_not_found_by_real_name(registry, cfg):
    bundle = make_bundle(registry)
    add_hidden(bundle, location_id="forest")
    scene_turn(bundle, 1, "Гракх пропал в лесу.")
    assert "goblin_warrior_1" not in npc_ids(state_of(registry, cfg, bundle))


def test_npc_with_empty_name_is_not_found_by_empty_string(registry, cfg):
    bundle = make_bundle(registry)
    add_npc(bundle, "nameless", name="", location_id="forest")
    scene_turn(bundle, 1, "Тихо.")
    assert "nameless" not in npc_ids(state_of(registry, cfg, bundle))


def test_scene_has_start_and_end_dates_and_days(registry, cfg):
    bundle = make_bundle(registry)
    bundle.session.current_scene.started_at_s = 1 * DAY + 3600
    bundle.world.clock.now_s = 15 * DAY + 7200
    scene = state_of(registry, cfg, bundle)["scene"]
    assert scene["date_start"] == GameClock(now_s=1 * DAY).to_date()
    assert scene["date"] == GameClock(now_s=15 * DAY).to_date()
    assert scene["days"] == 14


def test_scene_days_is_calendar_difference_across_midnight(registry, cfg):
    bundle = make_bundle(registry)
    bundle.session.current_scene.started_at_s = 3 * DAY + 23 * 3600
    bundle.world.clock.now_s = 4 * DAY + 3600
    assert state_of(registry, cfg, bundle)["scene"]["days"] == 1


def test_scene_start_date_uses_world_calendar(registry, cfg):
    from ai_dm.core.clock import Calendar, Month

    bundle = make_bundle(registry)
    bundle.world.clock = GameClock(
        now_s=15 * DAY,
        calendar=Calendar(months=[Month(name="Первый", days=10), Month(name="Второй", days=10)]),
    )
    bundle.session.current_scene.started_at_s = 12 * DAY
    assert state_of(registry, cfg, bundle)["scene"]["date_start"] == "0001-02-03"


def test_scene_days_is_zero_within_one_day(registry, cfg):
    bundle = make_bundle(registry)
    bundle.session.current_scene.started_at_s = 3 * DAY + 3600
    bundle.world.clock.now_s = 3 * DAY + 20 * 3600
    assert state_of(registry, cfg, bundle)["scene"]["days"] == 0


def test_hidden_real_name_not_in_summarizer_text(registry, cfg):
    bundle = make_bundle(registry)
    add_hidden(bundle, name="Мурк")
    ctx = make_ctx(registry, cfg, bundle=bundle)
    request = SummarizerPromptBuilder(ctx_app()).build(ctx, "", "summarize_scene")
    text = request.messages[0].content[0].text
    assert "Воин-гоблин 1" in text
    assert "Мурк" not in text
