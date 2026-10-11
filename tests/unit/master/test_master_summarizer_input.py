# Этап 4, P1+ (R1): вход summarizer (SummarizerPromptBuilder.state_data) -- только известное
# герою. NPC: с непустым known_to_player, из локации сцены, или упомянутые по имени в ходах
# сцены; локации: visited=True и локация сцены. Герой в protocol_kit стоит в "vale".
from master_kit import make_bundle, make_ctx, turn_record

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
