# Ожидаемый API (STAGE3-PLAN A7, П3): ai_dm.master.relevance.relevant_npcs(bundle) -> list[str]
# id NPC: живые в локации героя + живые key=true + владельцы активных триггеров (is_ready: state
# active, once не отработал, cooldown прошёл); без повторов, сортировка по id. Герой в protocol_kit
# стоит в "vale", Гракх (key) -- в "vale", Олдрик -- без локации.
# Состояние хода (state_data): known_npcs = relevant_npcs; секреты -- только у NPC сцены (локация
# героя), в сообщении (messages[0]) с пометкой «скрыто»; в system секретов нет (кэш-префикс).
import json

from master_kit import make_bundle, make_ctx

from ai_dm.master.prompt import PromptBuilder
from ai_dm.master.relevance import relevant_npcs
from ai_dm.state.triggers import Secret, Trigger
from ai_dm.state.world import NPC


def add_npc(bundle, npc_id, **fields):
    data = {"id": npc_id, "name": npc_id, "named": True, "means": ["m"]}
    data.update(fields)
    bundle.world.npcs[npc_id] = NPC(**data)


def trigger(trigger_id="t1", **fields):
    return Trigger(id=trigger_id, **{"if": {"flag": "x"}}, then="что-то", **fields)


def test_npc_in_hero_location_is_relevant(registry):
    bundle = make_bundle(registry)
    add_npc(bundle, "clerk", location_id="vale")
    assert "clerk" in relevant_npcs(bundle)


def test_key_npc_elsewhere_is_relevant(registry):
    bundle = make_bundle(registry)
    add_npc(bundle, "baron", key=True, location_id="forest")
    assert "baron" in relevant_npcs(bundle)


def test_owner_of_active_trigger_elsewhere_is_relevant(registry):
    bundle = make_bundle(registry)
    add_npc(bundle, "spy", location_id="forest", opportunity=[trigger()])
    assert "spy" in relevant_npcs(bundle)


def test_nonkey_without_trigger_elsewhere_is_not_relevant(registry):
    bundle = make_bundle(registry)
    add_npc(bundle, "farmer", location_id="forest")
    assert "farmer" not in relevant_npcs(bundle)


def test_nonkey_without_location_and_trigger_is_not_relevant(registry):
    assert "aldric" not in relevant_npcs(make_bundle(registry))


def test_owner_of_fired_once_trigger_is_not_relevant(registry):
    bundle = make_bundle(registry)
    add_npc(bundle, "spy", location_id="forest", opportunity=[trigger(once=True, state="fired")])
    assert "spy" not in relevant_npcs(bundle)


def test_owner_of_disabled_trigger_is_not_relevant(registry):
    bundle = make_bundle(registry)
    add_npc(bundle, "spy", location_id="forest", opportunity=[trigger(state="disabled")])
    assert "spy" not in relevant_npcs(bundle)


def test_owner_of_trigger_on_cooldown_is_not_relevant(registry):
    bundle = make_bundle(registry)
    bundle.world.clock.now_s = 1000
    add_npc(
        bundle, "spy", location_id="forest",
        opportunity=[trigger(cooldown="7d", fired_count=1, last_fired_at=900)],
    )
    assert "spy" not in relevant_npcs(bundle)


def test_dead_npc_is_not_relevant_even_if_key_or_in_scene(registry):
    bundle = make_bundle(registry)
    bundle.world.npcs["grakh"].status = "dead"
    add_npc(bundle, "clerk", location_id="vale", status="dead")
    ids = relevant_npcs(bundle)
    assert "grakh" not in ids
    assert "clerk" not in ids


def test_result_is_sorted_and_without_duplicates(registry):
    bundle = make_bundle(registry)
    add_npc(bundle, "zed", key=True, location_id="vale", opportunity=[trigger()])
    add_npc(bundle, "abe", key=True, location_id="vale")
    ids = relevant_npcs(bundle)
    assert ids == sorted(set(ids))
    assert ids == ["abe", "grakh", "zed"]


def test_result_does_not_depend_on_insertion_order(registry):
    first = make_bundle(registry)
    second = make_bundle(registry)
    for bundle, order in ((first, ["b", "a"]), (second, ["a", "b"])):
        for npc_id in order:
            add_npc(bundle, npc_id, key=True)
    assert relevant_npcs(first) == relevant_npcs(second)


def test_relevant_npcs_does_not_change_bundle(registry):
    bundle = make_bundle(registry)
    before = bundle.model_dump_json()
    relevant_npcs(bundle)
    assert bundle.model_dump_json() == before


# состояние хода

def build(ctx):
    from master_kit import app_cfg

    return PromptBuilder(app_cfg()).build(ctx, "Осматриваюсь.", "explore")


def data_of(request):
    return json.loads(request.messages[0].content[0].text)


def message_text(request):
    return request.messages[0].content[0].text


def test_state_known_npcs_are_relevant_ones_and_nearby(registry, cfg):
    # P3: NPC в соседней локации (forest) тоже известен; в далёкой (goblin_den) -- нет
    bundle = make_bundle(registry)
    add_npc(bundle, "farmer", location_id="goblin_den")
    add_npc(bundle, "baron", key=True, location_id="forest")
    add_npc(bundle, "hunter", location_id="forest")
    ids = [n["id"] for n in data_of(build(make_ctx(registry, cfg, bundle=bundle)))["known_npcs"]]
    assert ids == sorted(set(relevant_npcs(bundle)) | {"hunter"})
    assert "farmer" not in ids


def test_state_secret_of_scene_npc_is_hidden_marked(registry, cfg):
    bundle = make_bundle(registry)
    add_npc(
        bundle, "clerk", location_id="vale",
        secrets=[Secret(id="s1", text="СЕКРЕТ-В-СЦЕНЕ", reveal_if={"flag": "x"})],
    )
    text = message_text(build(make_ctx(registry, cfg, bundle=bundle)))
    assert "СЕКРЕТ-В-СЦЕНЕ" in text
    assert "скрыто" in text


def test_state_secret_of_npc_elsewhere_is_not_in_prompt(registry, cfg):
    bundle = make_bundle(registry)
    add_npc(
        bundle, "baron", key=True, location_id="forest",
        secrets=[Secret(id="s1", text="СЕКРЕТ-ДАЛЕКО", reveal_if={"flag": "x"})],
    )
    request = build(make_ctx(registry, cfg, bundle=bundle))
    assert "СЕКРЕТ-ДАЛЕКО" not in message_text(request)
    assert all("СЕКРЕТ-ДАЛЕКО" not in block.text for block in request.system)


def test_state_revealed_secret_is_not_hidden_text(registry, cfg):
    bundle = make_bundle(registry)
    add_npc(
        bundle, "clerk", location_id="vale",
        secrets=[Secret(id="s1", text="СЕКРЕТ-ОТКРЫТ", reveal_if={"flag": "x"}, revealed=True)],
    )
    assert "СЕКРЕТ-ОТКРЫТ" not in message_text(build(make_ctx(registry, cfg, bundle=bundle)))


def test_secrets_are_not_in_system_blocks(registry, cfg):
    bundle = make_bundle(registry)
    add_npc(
        bundle, "clerk", location_id="vale",
        secrets=[Secret(id="s1", text="СЕКРЕТ-В-СЦЕНЕ", reveal_if={"flag": "x"})],
    )
    request = build(make_ctx(registry, cfg, bundle=bundle))
    assert all("СЕКРЕТ-В-СЦЕНЕ" not in block.text for block in request.system)


def test_prefix_bytes_do_not_change_between_turns(registry, cfg):
    bundle = make_bundle(registry)
    first = build(make_ctx(registry, cfg, bundle=bundle))
    add_npc(bundle, "baron", key=True, location_id="forest")
    bundle.world.flags["x"] = True
    second = build(make_ctx(registry, cfg, bundle=bundle))
    assert [b.text for b in first.system] == [b.text for b in second.system]
    assert first.tools == second.tools


# упоминания: именованный живой NPC вне сцены, не key, без триггера -- если назван в вариантах
# или в последних recent_turns (ввод игрока или рассказ); регистр не важен

def far_npc(bundle):
    add_npc(bundle, "branka", name="Бранка", location_id="forest")


def test_npc_named_in_offered_choices_is_relevant(registry):
    bundle = make_bundle(registry)
    far_npc(bundle)
    bundle.session.offered_choices = ["Пойти к Бранка", "Уйти"]
    assert "branka" in relevant_npcs(bundle)


def test_npc_named_in_recent_narration_is_relevant(registry):
    from master_kit import turn_record

    bundle = make_bundle(registry)
    far_npc(bundle)
    bundle.memory.recent_turns.append(turn_record(1, "Вы слышите, что Бранка ушла в лес."))
    assert "branka" in relevant_npcs(bundle)


def test_npc_named_in_recent_player_input_is_relevant(registry):
    from master_kit import turn_record

    bundle = make_bundle(registry)
    far_npc(bundle)
    record = turn_record(1)
    record.player_input = "Спрашиваю про Бранка"
    bundle.memory.recent_turns.append(record)
    assert "branka" in relevant_npcs(bundle)


def test_mention_is_case_insensitive(registry):
    from master_kit import turn_record

    bundle = make_bundle(registry)
    far_npc(bundle)
    bundle.memory.recent_turns.append(turn_record(1, "где-то там БРАНКА"))
    assert "branka" in relevant_npcs(bundle)


def test_unmentioned_far_npc_is_not_relevant(registry):
    from master_kit import turn_record

    bundle = make_bundle(registry)
    far_npc(bundle)
    bundle.memory.recent_turns.append(turn_record(1, "Ничего особенного."))
    bundle.session.offered_choices = ["Уйти", "Остаться"]
    assert "branka" not in relevant_npcs(bundle)


def test_mentioned_dead_or_unnamed_npc_is_not_relevant(registry):
    from master_kit import turn_record

    bundle = make_bundle(registry)
    add_npc(bundle, "dead_one", name="Покойник", location_id="forest", status="dead")
    add_npc(bundle, "rat", name="Крыса", named=False, location_id="forest")
    bundle.memory.recent_turns.append(turn_record(1, "Покойник и Крыса"))
    ids = relevant_npcs(bundle)
    assert "dead_one" not in ids
    assert "rat" not in ids


# S1: state_data.divine.gods[].power -- растёт / обычна / убывает (знак поправки текущего сезона)
def divine_item(registry, cfg, season_power, now_s):
    from ai_dm.state.world import God

    bundle = make_bundle(registry)
    bundle.world.pantheon["selune"] = God(id="selune", name="Селунэ", season_power=season_power)
    bundle.world.clock.now_s = now_s
    bundle.heroes[0].favor = {"selune": 1}
    gods = data_of(build(make_ctx(registry, cfg, bundle=bundle)))["divine"]["gods"]
    return next(g for g in gods if g["id"] == "selune")


def test_state_power_grows_in_spring(registry, cfg):
    assert divine_item(registry, cfg, {"весна": 15}, 35 * 86400)["power"] == "растёт"


def test_state_power_fades_in_winter(registry, cfg):
    assert divine_item(registry, cfg, {"зима": -25}, 3 * 86400)["power"] == "убывает"


def test_state_power_is_usual_when_season_bonus_is_zero(registry, cfg):
    assert divine_item(registry, cfg, {"весна": 15, "лето": 0}, 150 * 86400)["power"] == "обычна"


def test_state_has_no_power_without_season_power(registry, cfg):
    assert "power" not in divine_item(registry, cfg, {}, 35 * 86400)


def test_state_hero_shows_motive(registry, cfg):
    bundle = make_bundle(registry)
    bundle.heroes[0].motive = "МОТИВ-ГЕРОЯ"
    hero = data_of(build(make_ctx(registry, cfg, bundle=bundle)))["hero"]
    assert hero["motive"] == "МОТИВ-ГЕРОЯ"


# спутники (stage3-live-followers, F3): «с тобой» в промпте, всегда релевантны

def test_follower_elsewhere_is_relevant(registry):
    bundle = make_bundle(registry)
    add_npc(bundle, "bran", location_id="forest", follows=bundle.heroes[0].id)
    assert "bran" in relevant_npcs(bundle)


def test_follower_of_another_hero_elsewhere_is_not_relevant(registry):
    bundle = make_bundle(registry)
    add_npc(bundle, "bran", location_id="forest", follows="someone_else")
    assert "bran" not in relevant_npcs(bundle)


def test_dead_follower_is_not_relevant(registry):
    bundle = make_bundle(registry)
    add_npc(
        bundle, "bran", location_id="forest", follows=bundle.heroes[0].id, status="dead"
    )
    assert "bran" not in relevant_npcs(bundle)


def known_entry(registry, cfg, bundle, npc_id):
    data = data_of(build(make_ctx(registry, cfg, bundle=bundle)))
    return next(n for n in data["known_npcs"] if n["id"] == npc_id)


def test_known_npc_marks_follower(registry, cfg):
    bundle = make_bundle(registry)
    add_npc(bundle, "bran", location_id="vale", follows=bundle.heroes[0].id)
    assert known_entry(registry, cfg, bundle, "bran")["follows"] == bundle.heroes[0].id


def test_known_npc_without_follow_is_not_marked(registry, cfg):
    bundle = make_bundle(registry)
    add_npc(bundle, "clerk", location_id="vale")
    assert not known_entry(registry, cfg, bundle, "clerk").get("follows")


def test_scene_npc_marks_follower(registry, cfg):
    bundle = make_bundle(registry)
    add_npc(bundle, "bran", location_id="vale", follows=bundle.heroes[0].id)
    data = data_of(build(make_ctx(registry, cfg, bundle=bundle)))
    entry = next(n for n in data["scene_npcs"] if n["id"] == "bran")
    assert entry["follows"] == bundle.heroes[0].id


# причины релевантности (этап 4, P3): npc_reasons -> {id: {причины}}

def test_reasons_here(registry):
    from ai_dm.master.relevance import npc_reasons

    bundle = make_bundle(registry)
    add_npc(bundle, "clerk", location_id="vale")
    assert npc_reasons(bundle)["clerk"] == {"here"}


def test_reasons_key_elsewhere(registry):
    from ai_dm.master.relevance import npc_reasons

    bundle = make_bundle(registry)
    add_npc(bundle, "baron", key=True, location_id="forest")
    assert npc_reasons(bundle)["baron"] == {"key"}


def test_reasons_key_and_here_are_both_kept(registry):
    from ai_dm.master.relevance import npc_reasons

    assert npc_reasons(make_bundle(registry))["grakh"] == {"key", "here"}


def test_reasons_active_trigger(registry):
    from ai_dm.master.relevance import npc_reasons

    bundle = make_bundle(registry)
    add_npc(bundle, "spy", location_id="far", opportunity=[trigger()])
    assert npc_reasons(bundle)["spy"] == {"active"}


def test_reasons_with_hero(registry):
    from ai_dm.master.relevance import npc_reasons

    bundle = make_bundle(registry)
    add_npc(bundle, "squire", location_id="far", follows="hero")
    assert npc_reasons(bundle)["squire"] == {"with_hero"}


def test_reasons_follower_of_other_hero_is_not_with_hero(registry):
    from ai_dm.master.relevance import npc_reasons

    bundle = make_bundle(registry)
    add_npc(bundle, "squire", location_id="far", follows="someone")
    assert "squire" not in npc_reasons(bundle)


def test_reasons_said_in_offered_choices(registry):
    from ai_dm.master.relevance import npc_reasons

    bundle = make_bundle(registry)
    add_npc(bundle, "boris", name="Борис", location_id="far")
    bundle.session.offered_choices = ["Найти БОРИСА"]
    assert npc_reasons(bundle)["boris"] == {"said"}


def test_reasons_said_in_recent_turn_text(registry):
    from master_kit import turn_record

    from ai_dm.master.relevance import npc_reasons

    bundle = make_bundle(registry)
    add_npc(bundle, "boris", name="Борис", location_id="far")
    bundle.memory.recent_turns = [turn_record(1, narration="Пришёл Борис")]
    assert npc_reasons(bundle)["boris"] == {"said"}


def test_reasons_empty_name_is_never_said(registry):
    from ai_dm.master.relevance import npc_reasons

    bundle = make_bundle(registry)
    add_npc(bundle, "nameless", name="", location_id="far")
    bundle.session.offered_choices = ["что-то"]
    assert "nameless" not in npc_reasons(bundle)


def test_reasons_nearby_only_with_nearby_ids(registry):
    from ai_dm.master.relevance import npc_reasons

    bundle = make_bundle(registry)
    add_npc(bundle, "hunter", location_id="forest")
    assert "hunter" not in npc_reasons(bundle)
    assert "hunter" not in npc_reasons(bundle, nearby_ids=["goblin_den"])
    assert npc_reasons(bundle, nearby_ids=["forest"])["hunter"] == {"nearby"}


def test_reasons_nearby_accepts_any_iterable(registry):
    from ai_dm.master.relevance import npc_reasons

    bundle = make_bundle(registry)
    add_npc(bundle, "hunter", location_id="forest")
    assert npc_reasons(bundle, {"forest"})["hunter"] == {"nearby"}


def test_reasons_nearby_adds_to_other_reasons(registry):
    from ai_dm.master.relevance import npc_reasons

    bundle = make_bundle(registry)
    add_npc(bundle, "baron", key=True, location_id="forest")
    assert npc_reasons(bundle, ["forest"])["baron"] == {"key", "nearby"}


def test_reasons_nearby_is_not_given_for_hero_location(registry):
    from ai_dm.master.relevance import npc_reasons

    bundle = make_bundle(registry)
    add_npc(bundle, "clerk", location_id="vale")
    assert npc_reasons(bundle, ["vale"])["clerk"] == {"here"}


def test_reasons_dead_nearby_is_not_relevant(registry):
    from ai_dm.master.relevance import npc_reasons

    bundle = make_bundle(registry)
    add_npc(bundle, "hunter", location_id="forest", status="dead")
    assert "hunter" not in npc_reasons(bundle, ["forest"])


def test_reasons_unnamed_nearby_is_not_relevant(registry):
    from ai_dm.master.relevance import npc_reasons

    bundle = make_bundle(registry)
    add_npc(bundle, "hunter", location_id="forest", named=False)
    assert "hunter" not in npc_reasons(bundle, ["forest"])


def test_reasons_npc_without_location_is_not_nearby(registry):
    from ai_dm.master.relevance import npc_reasons

    bundle = make_bundle(registry)
    add_npc(bundle, "drifter")
    assert "drifter" not in npc_reasons(bundle, ["forest"])


def test_reasons_do_not_change_bundle(registry):
    from ai_dm.master.relevance import npc_reasons

    bundle = make_bundle(registry)
    before = bundle.model_dump_json()
    npc_reasons(bundle, ["forest"])
    assert bundle.model_dump_json() == before


def test_relevant_npcs_ignores_nearby(registry):
    bundle = make_bundle(registry)
    add_npc(bundle, "hunter", location_id="forest")
    assert "hunter" not in relevant_npcs(bundle)


def test_relevant_npcs_equals_sorted_reason_keys(registry):
    from ai_dm.master.relevance import npc_reasons

    bundle = make_bundle(registry)
    add_npc(bundle, "zed", key=True)
    add_npc(bundle, "abe", location_id="vale")
    assert relevant_npcs(bundle) == sorted(npc_reasons(bundle))


# Фикс ЖП4 (132): причина merchant -- торговец (цель визита), вытесняется после nearby

def add_merchant(bundle, npc_id, **fields):
    from ai_dm.state.world import TradeProfile

    add_npc(bundle, npc_id, trade=TradeProfile(kind="general", purse_cp=100), **fields)


def test_reasons_merchant_elsewhere(registry):
    from ai_dm.master.relevance import npc_reasons

    bundle = make_bundle(registry)
    add_merchant(bundle, "greta", location_id="goblin_den")
    assert npc_reasons(bundle)["greta"] == {"merchant"}


def test_reasons_npc_without_trade_is_not_merchant(registry):
    from ai_dm.master.relevance import npc_reasons

    bundle = make_bundle(registry)
    add_npc(bundle, "farmer", location_id="goblin_den")
    assert "farmer" not in npc_reasons(bundle)


def test_reasons_merchant_here_keeps_here(registry):
    from ai_dm.master.relevance import npc_reasons, rank_npcs

    bundle = make_bundle(registry)
    add_merchant(bundle, "greta", location_id="vale")
    reasons = npc_reasons(bundle)
    assert reasons["greta"] == {"here", "merchant"}
    assert "greta" in rank_npcs(reasons)[0]


def test_reasons_dead_merchant_is_not_relevant(registry):
    from ai_dm.master.relevance import npc_reasons

    bundle = make_bundle(registry)
    add_merchant(bundle, "greta", location_id="goblin_den", status="dead")
    assert "greta" not in npc_reasons(bundle)


def test_merchant_elsewhere_is_relevant(registry):
    bundle = make_bundle(registry)
    add_merchant(bundle, "greta", location_id="goblin_den")
    assert "greta" in relevant_npcs(bundle)


def test_reasons_provider_elsewhere_is_merchant_reason(registry):
    from ai_dm.master.relevance import npc_reasons

    bundle = make_bundle(registry)
    add_npc(bundle, "grok", location_id="goblin_den", services=["room_modest"])
    assert npc_reasons(bundle)["grok"] == {"merchant"}


def test_reasons_provider_here_keeps_here(registry):
    from ai_dm.master.relevance import npc_reasons

    bundle = make_bundle(registry)
    add_npc(bundle, "grok", location_id="vale", services=["room_modest"])
    assert npc_reasons(bundle)["grok"] == {"here", "merchant"}


def test_reasons_dead_provider_is_not_relevant(registry):
    from ai_dm.master.relevance import npc_reasons

    bundle = make_bundle(registry)
    add_npc(bundle, "grok", location_id="goblin_den", services=["ale"], status="dead")
    assert "grok" not in npc_reasons(bundle)


def test_provider_elsewhere_is_relevant(registry):
    bundle = make_bundle(registry)
    add_npc(bundle, "grok", location_id="goblin_den", services=["ale"])
    assert "grok" in relevant_npcs(bundle)


def test_rank_npcs_merchant_is_removable(registry):
    from ai_dm.master.relevance import rank_npcs

    fixed, ranked = rank_npcs({"greta": {"merchant"}})
    assert fixed == []
    assert ranked == ["greta"]


def test_rank_npcs_order_said_key_nearby_merchant():
    from ai_dm.master.relevance import rank_npcs

    reasons = {"a_m": {"merchant"}, "b_n": {"nearby"}, "c_k": {"key"}, "d_s": {"said"}}
    assert rank_npcs(reasons)[1] == ["d_s", "c_k", "b_n", "a_m"]


def test_rank_npcs_merchant_with_said_counts_as_merchant():
    from ai_dm.master.relevance import rank_npcs

    reasons = {"a": {"said", "merchant"}, "b": {"nearby"}}
    assert rank_npcs(reasons)[1] == ["b", "a"]


def test_far_merchant_is_in_known_npcs_with_location(registry, cfg):
    bundle = make_bundle(registry)
    add_merchant(bundle, "greta", location_id="goblin_den")
    data = data_of(build(make_ctx(registry, cfg, bundle=bundle)))
    entry = next(n for n in data["known_npcs"] if n["id"] == "greta")
    assert entry["location_id"] == "goblin_den"


# nearby_locations: вынесена в relevance

def test_nearby_locations_current_first_then_links_both_ways(registry):
    from ai_dm.master.relevance import nearby_locations

    bundle = make_bundle(registry)
    world = bundle.world
    world.locations["rev"] = type(world.locations["vale"])(
        id="rev", name="Обратная",
        connections=[type(world.locations["vale"].connections[0])(to="vale", distance_m=500)],
    )
    result = nearby_locations(world, world.locations["vale"])
    assert result[0] == {"id": "vale", "name": "Вейл", "distance_m": 0}
    assert result[1:] == [
        {"id": "forest", "name": "Лес", "distance_m": 4800},
        {"id": "rev", "name": "Обратная", "distance_m": 500},
    ]


def test_nearby_locations_of_isolated_place_is_only_itself(registry):
    from ai_dm.master.relevance import nearby_locations

    world = make_bundle(registry).world
    assert nearby_locations(world, world.locations["goblin_den"]) == [
        {"id": "goblin_den", "name": "Логово", "distance_m": 0}
    ]


# Ж2 (п. 0.10, BACKLOG 85): безымянный NPC с активной целью релевантен, как именованный

def avenger(bundle, npc_id="goblin_1", **fields):
    from ai_dm.rules.goals import add_goal

    add_npc(bundle, npc_id, name="Гоблин 1", named=False, **fields)
    add_goal(bundle.world.npcs[npc_id], "revenge", bundle.heroes[0].id, "мстит", 0)


def test_unnamed_npc_with_active_goal_is_relevant_here(registry):
    from ai_dm.master.relevance import npc_reasons

    bundle = make_bundle(registry)
    avenger(bundle, location_id="vale")
    assert npc_reasons(bundle)["goblin_1"] == {"here", "active"}
    assert "goblin_1" in relevant_npcs(bundle)


def test_unnamed_npc_with_active_goal_elsewhere_is_relevant(registry):
    bundle = make_bundle(registry)
    avenger(bundle, location_id="goblin_den")
    assert "goblin_1" in relevant_npcs(bundle)


def test_unnamed_npc_without_goal_is_not_relevant(registry):
    bundle = make_bundle(registry)
    add_npc(bundle, "goblin_1", name="Гоблин 1", named=False, location_id="vale")
    assert "goblin_1" not in relevant_npcs(bundle)


def test_unnamed_npc_with_closed_goal_is_not_relevant(registry):
    from ai_dm.rules.goals import close_goal

    bundle = make_bundle(registry)
    avenger(bundle, location_id="vale")
    close_goal(bundle.world.npcs["goblin_1"], "revenge", bundle.heroes[0].id, "done")
    assert "goblin_1" not in relevant_npcs(bundle)


def test_dead_unnamed_npc_with_goal_is_not_relevant(registry):
    bundle = make_bundle(registry)
    avenger(bundle, location_id="vale", status="dead")
    assert "goblin_1" not in relevant_npcs(bundle)


def test_unnamed_avenger_is_in_known_npcs_of_the_prompt(registry, cfg):
    bundle = make_bundle(registry)
    avenger(bundle, location_id="vale")
    items = data_of(build(make_ctx(registry, cfg, bundle=bundle)))["known_npcs"]
    assert "goblin_1" in [n["id"] for n in items]


def test_unnamed_npc_without_goal_is_not_in_known_npcs(registry, cfg):
    bundle = make_bundle(registry)
    add_npc(bundle, "goblin_1", name="Гоблин 1", named=False, location_id="vale")
    items = data_of(build(make_ctx(registry, cfg, bundle=bundle)))["known_npcs"]
    assert "goblin_1" not in [n["id"] for n in items]


def test_irrelevant_unnamed_npc_before_avenger_does_not_hide_him(registry):
    bundle = make_bundle(registry)
    add_npc(bundle, "plain", name="Простой", named=False, location_id="vale")
    avenger(bundle, location_id="vale")
    assert "goblin_1" in relevant_npcs(bundle)
