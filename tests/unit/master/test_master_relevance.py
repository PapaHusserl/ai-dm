# Ожидаемый API (STAGE3-PLAN A7, П3): ai_dm.master.relevance.relevant_npcs(bundle) -> list[str]
# id NPC: живые в локации героя + живые key=true + владельцы активных триггеров (is_ready: state
# active, once не отработал, cooldown прошёл); без повторов, сортировка по id. Герой в protocol_kit
# стоит в "vale", Гракх (key) -- в "vale", Олдрик -- без локации.
# Состояние хода (state_data): known_npcs = relevant_npcs; секреты -- только у NPC сцены (локация
# героя), в сообщении (messages[0]) с пометкой «скрыто»; в system секретов нет (кэш-префикс).
import json

from master_kit import make_bundle, make_ctx

from ai_dm.master.prompt import PromptBuilder
from ai_dm.master.relevance import known_places, relevant_npcs
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


def test_npc_named_in_oblique_case_is_relevant(registry):
    # 137: «подошёл к Бранке» -- падеж имени
    from master_kit import turn_record

    bundle = make_bundle(registry)
    far_npc(bundle)
    bundle.memory.recent_turns.append(turn_record(1, "Вы подошли к Бранке."))
    assert "branka" in relevant_npcs(bundle)


def test_two_word_name_is_found_in_cases(registry):
    from master_kit import turn_record

    bundle = make_bundle(registry)
    add_npc(bundle, "greta", name="Матушка Грета", location_id="forest")
    bundle.memory.recent_turns.append(turn_record(1, "Вы живёте у матушки Греты."))
    assert "greta" in relevant_npcs(bundle)


def test_short_name_is_not_found_inside_longer_word(registry):
    from master_kit import turn_record

    bundle = make_bundle(registry)
    add_npc(bundle, "yan", name="Ян", location_id="forest")
    bundle.memory.recent_turns.append(turn_record(1, "Вы зашли в Яндексе поискать."))
    assert "yan" not in relevant_npcs(bundle)


# absent_mentions / previous_narration (214)

def scene_turn(bundle, narration, scene_id="scene_1", n=1):
    from master_kit import turn_record

    record = turn_record(n, narration)
    record.scene_id = scene_id
    bundle.memory.recent_turns.append(record)


def test_previous_narration_is_last_turn_of_current_scene(registry):
    from ai_dm.master.relevance import previous_narration

    bundle = make_bundle(registry)
    scene_turn(bundle, "Первый.", n=1)
    scene_turn(bundle, "Второй.", n=2)
    assert previous_narration(bundle).startswith("Второй.")


def test_previous_narration_of_other_scene_is_empty(registry):
    from ai_dm.master.relevance import previous_narration

    bundle = make_bundle(registry)
    scene_turn(bundle, "Чужая сцена.", scene_id="scene_0")
    assert previous_narration(bundle) == ""


def test_previous_narration_without_turns_or_scene_is_empty(registry):
    from ai_dm.master.relevance import previous_narration

    bundle = make_bundle(registry)
    assert previous_narration(bundle) == ""
    scene_turn(bundle, "Ход.")
    bundle.session.current_scene = None
    assert previous_narration(bundle) == ""


def test_absent_mentions_finds_named_npc_elsewhere_in_case(registry):
    from ai_dm.master.relevance import absent_mentions

    bundle = make_bundle(registry)
    far_npc(bundle)
    assert absent_mentions(bundle, "Вы ждёте Бранку.") == ["branka"]


def test_absent_mentions_ignores_npc_in_hero_location(registry):
    from ai_dm.master.relevance import absent_mentions

    bundle = make_bundle(registry)
    add_npc(bundle, "branka", name="Бранка", location_id="vale")
    assert absent_mentions(bundle, "Бранка рядом.") == []


def test_absent_mentions_ignores_dead_unnamed_and_unmentioned(registry):
    from ai_dm.master.relevance import absent_mentions

    bundle = make_bundle(registry)
    add_npc(bundle, "dead_one", name="Покойник", location_id="forest", status="dead")
    add_npc(bundle, "rat", name="Крыса", named=False, location_id="forest")
    far_npc(bundle)
    assert absent_mentions(bundle, "Покойник и Крыса.") == []


def test_absent_mentions_is_sorted_by_id(registry):
    from ai_dm.master.relevance import absent_mentions

    bundle = make_bundle(registry)
    add_npc(bundle, "zed", name="Зед", location_id="forest")
    far_npc(bundle)
    assert absent_mentions(bundle, "Зед и Бранка.") == ["branka", "zed"]


def test_absent_mentions_counts_mentioned_npc_without_location_as_absent(registry):
    # текущее поведение: location_id=None != локации героя -- NPC отсутствует
    from ai_dm.master.relevance import absent_mentions

    bundle = make_bundle(registry)
    add_npc(bundle, "branka", name="Бранка")
    assert absent_mentions(bundle, "Вы ждёте Бранку.") == ["branka"]


def test_absent_mentions_without_hero_location_is_empty(registry):
    from ai_dm.master.relevance import absent_mentions

    bundle = make_bundle(registry)
    far_npc(bundle)
    bundle.heroes[0].location_id = None
    assert absent_mentions(bundle, "Бранка.") == []


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


# Л1: known_places -- посещённые не соседние места (цели travel_to и «Знакомые места» /where)

def test_known_places_is_empty_when_nothing_is_visited(registry):
    bundle = make_bundle(registry)
    assert known_places(bundle.world, set()) == []


def test_known_places_lists_places_with_visited_field(registry):
    bundle = make_bundle(registry)
    bundle.world.locations["forest"].visited = True
    assert [p.id for p in known_places(bundle.world, set())] == ["forest"]


def test_known_places_lists_places_with_visited_flag(registry):
    bundle = make_bundle(registry)
    bundle.world.flags["visited:goblin_den"] = True
    assert [p.id for p in known_places(bundle.world, set())] == ["goblin_den"]


def test_known_places_skips_the_given_neighbour_ids(registry):
    bundle = make_bundle(registry)
    bundle.world.locations["forest"].visited = True
    bundle.world.locations["goblin_den"].visited = True
    assert [p.id for p in known_places(bundle.world, {"forest"})] == ["goblin_den"]


def test_known_places_are_sorted_by_id(registry):
    bundle = make_bundle(registry)
    for place_id in ("vale", "goblin_den", "forest"):
        bundle.world.locations[place_id].visited = True
    assert [p.id for p in known_places(bundle.world, set())] == ["forest", "goblin_den", "vale"]


def test_known_places_ignores_unvisited_false_flag(registry):
    bundle = make_bundle(registry)
    bundle.world.flags["visited:forest"] = False
    assert known_places(bundle.world, set()) == []


# Л1 П2: absent_location_mention, moved_last_turn (герой в vale, сосед forest «Лес»)

def moved_turn(bundle, narration="Ход.", player_input=None, outcomes=()):
    scene_turn(bundle, narration)
    record = bundle.memory.recent_turns[-1]
    if player_input is not None:
        record.player_input = player_input
    record.outcomes = list(outcomes)


def test_absent_location_finds_named_neighbour(registry):
    from ai_dm.master.relevance import absent_location_mention

    bundle = make_bundle(registry)
    assert absent_location_mention(bundle, "Вы думаете про лес.") == ["forest"]


def test_absent_location_finds_known_far_place(registry):
    from ai_dm.master.relevance import absent_location_mention

    bundle = make_bundle(registry)
    bundle.world.locations["goblin_den"].visited = True
    assert absent_location_mention(bundle, "Вы вспоминаете Логово.") == ["goblin_den"]


def test_absent_location_ignores_unvisited_far_place(registry):
    from ai_dm.master.relevance import absent_location_mention

    bundle = make_bundle(registry)
    assert absent_location_mention(bundle, "Вы вспоминаете Логово.") == []


def test_absent_location_ignores_the_current_place(registry):
    from ai_dm.master.relevance import absent_location_mention

    bundle = make_bundle(registry)
    assert absent_location_mention(bundle, "Вы стоите в Вейле.") == []


def test_absent_location_is_sorted_by_id(registry):
    from ai_dm.master.relevance import absent_location_mention

    bundle = make_bundle(registry)
    bundle.world.locations["goblin_den"].visited = True
    assert absent_location_mention(bundle, "Логово и лес.") == ["forest", "goblin_den"]


def test_absent_location_needs_the_full_name(registry):
    from ai_dm.master.relevance import absent_location_mention
    from ai_dm.state.world import Connection, Location

    bundle = make_bundle(registry)
    bundle.world.locations["vale"].connections.append(Connection(to="docks", distance_m=40))
    bundle.world.locations["docks"] = Location(id="docks", name="Нижние верфи")
    assert absent_location_mention(bundle, "У наковальни верфи гремит молот.") == []
    assert absent_location_mention(bundle, "У наковальни Нижние верфи гремит молот.") == ["docks"]
    assert absent_location_mention(bundle, "У наковальни Нижних верфей гремит молот.") == ["docks"]


def test_absent_location_is_empty_without_hero_location(registry):
    from ai_dm.master.relevance import absent_location_mention

    bundle = make_bundle(registry)
    bundle.heroes[0].location_id = None
    assert absent_location_mention(bundle, "Вы думаете про лес.") == []


def test_absent_location_is_empty_after_a_travel_outcome(registry):
    from ai_dm.master.relevance import absent_location_mention

    bundle = make_bundle(registry)
    moved_turn(bundle, outcomes=["Путь в «Лес»: 60 с"])
    assert absent_location_mention(bundle, "Вы думаете про лес.") == []


def test_absent_location_is_empty_after_an_arrival_note_in_player_input(registry):
    from ai_dm.master.relevance import absent_location_mention

    bundle = make_bundle(registry)
    moved_turn(bundle, player_input="(Перед этим герой сам: пришёл в «Лес» (60 с).) Осматриваюсь")
    assert absent_location_mention(bundle, "Вы думаете про лес.") == []


def test_absent_location_stays_when_the_move_was_in_an_older_turn(registry):
    from ai_dm.master.relevance import absent_location_mention

    bundle = make_bundle(registry)
    moved_turn(bundle, outcomes=["Путь в «Лес»: 60 с"])
    scene_turn(bundle, "Тихо.", n=2)
    assert absent_location_mention(bundle, "Вы думаете про лес.") == ["forest"]


def test_moved_last_turn_is_false_without_turns_and_for_plain_turn(registry):
    from ai_dm.master.relevance import moved_last_turn

    bundle = make_bundle(registry)
    assert moved_last_turn(bundle) is False
    moved_turn(bundle, outcomes=["Золото: +5"])
    assert moved_last_turn(bundle) is False


def test_moved_last_turn_by_outcome_and_by_note(registry):
    from ai_dm.master.relevance import moved_last_turn

    by_outcome = make_bundle(registry)
    moved_turn(by_outcome, outcomes=["Путь в «Лес»: 60 с"])
    by_note = make_bundle(registry)
    moved_turn(by_note, player_input="(Перед этим герой сам: пришёл в «Лес» (60 с).) Жду")
    assert moved_last_turn(by_outcome) is True
    assert moved_last_turn(by_note) is True


def test_moved_last_turn_ignores_a_turn_of_another_scene(registry):
    from ai_dm.master.relevance import moved_last_turn

    bundle = make_bundle(registry)
    moved_turn(bundle, outcomes=["Путь в «Лес»: 60 с"])
    bundle.memory.recent_turns[-1].scene_id = "scene_0"
    assert moved_last_turn(bundle) is False


# Л1 П2: travel_intent («иду в X» в тексте игрока)

def places_of(*pairs):
    from ai_dm.state.world import Location

    return [Location(id=i, name=n) for i, n in pairs]


WHARF = ("stone_nests_wharf", "Причал Каменных Гнёзд")
TAVERN = ("stone_nests_tavern", "Таверна «Каменный очаг»")


def test_travel_intent_first_word_of_the_name_after_a_move_verb():
    from ai_dm.master.relevance import travel_intent

    assert travel_intent(places_of(WHARF, TAVERN), "иду на причал") == "stone_nests_wharf"


def test_travel_intent_works_with_case_and_other_move_verbs():
    from ai_dm.master.relevance import travel_intent

    places = places_of(WHARF, TAVERN)
    assert travel_intent(places, "Пойдём к Причалу") == "stone_nests_wharf"
    assert travel_intent(places, "Отправляюсь на причал, к кузнецу") == "stone_nests_wharf"


def test_travel_intent_full_name():
    from ai_dm.master.relevance import travel_intent

    places = places_of(WHARF, TAVERN)
    assert travel_intent(places, "иду в Причал Каменных Гнёзд") == "stone_nests_wharf"


def test_travel_intent_needs_a_move_verb():
    from ai_dm.master.relevance import travel_intent

    places = places_of(WHARF, TAVERN)
    assert travel_intent(places, "расспросить о причале") is None
    assert travel_intent(places, "причал") is None


def test_travel_intent_two_places_in_the_phrase_is_none():
    from ai_dm.master.relevance import travel_intent

    places = places_of(WHARF, ("tavern", "Таверна"))
    assert travel_intent(places, "иду с причала в таверну") is None


def test_travel_intent_shared_first_word_of_two_places_is_none():
    from ai_dm.master.relevance import travel_intent

    places = places_of(WHARF, ("fish_wharf", "Причал Рыбаков"))
    assert travel_intent(places, "иду на причал") is None


def test_travel_intent_adjective_name_in_accusative():
    from ai_dm.master.relevance import travel_intent

    places = places_of(("old_crypt", "Старая крипта"), TAVERN)
    assert travel_intent(places, "иду в Старую крипту") == "old_crypt"


def test_travel_intent_adjective_alone_does_not_move():
    from ai_dm.master.relevance import travel_intent

    places = places_of(("old_crypt", "Старая крипта"), ("old_mill", "Старая мельница"))
    assert travel_intent(places, "иду в Старую") is None


def test_travel_intent_old_adjective_in_another_phrase_does_not_move():
    from ai_dm.master.relevance import travel_intent

    places = places_of(("old_crypt", "Старая крипта"))
    assert travel_intent(places, "иду к старому кузнецу") is None
    assert travel_intent(places, "иду к старой ведьме") is None


def test_travel_intent_big_hall_is_not_the_big_square():
    from ai_dm.master.relevance import travel_intent

    places = places_of(("square", "Большая площадь"))
    assert travel_intent(places, "иду в большой зал") is None


def test_travel_intent_adjective_name_by_its_noun_in_a_case():
    from ai_dm.master.relevance import travel_intent

    places = places_of(("docks", "Нижние верфи"), TAVERN)
    assert travel_intent(places, "иду на Нижнюю верфь") == "docks"


def test_travel_intent_by_the_noun_of_the_name():
    from ai_dm.master.relevance import travel_intent

    places = places_of(("old_crypt", "Старая крипта"), TAVERN)
    assert travel_intent(places, "иду к крипте") == "old_crypt"


def test_travel_intent_two_taverns_is_none():
    from ai_dm.master.relevance import travel_intent

    places = places_of(("tavern_a", "Таверна «Каменный очаг»"), ("tavern_b", "Таверна «Гусь»"))
    assert travel_intent(places, "иду в таверну") is None


def test_travel_intent_full_name_with_cases():
    from ai_dm.master.relevance import travel_intent

    places = places_of(("old_crypt", "Старая крипта"), ("old_mill", "Старая мельница"))
    assert travel_intent(places, "иду в Старую крипту") == "old_crypt"
    assert travel_intent(places, "иду к Старой мельнице") == "old_mill"


# Л1 П2 круг 1: moved (ход перехода)

def test_moved_by_arrival_note_in_the_input():
    from ai_dm.master.relevance import moved

    assert moved("(Перед этим герой сам: пришёл в «Лес» (60 с).) Жду", []) is True


def test_moved_by_travel_outcome_of_the_narrator():
    from ai_dm.master.relevance import moved

    assert moved("Жду", ["Золото: +5", "Путь в «Лес»: 60 с"]) is True


def test_not_moved_without_note_and_travel_outcome():
    from ai_dm.master.relevance import moved

    assert moved("Иду в лес", ["Золото: +5", "Куда: Путь в «Лес»"]) is False


# Л1 П2 круг 2: place_keys и travel_intent по решению 29

def test_place_keys_full_name_first_noun_and_quoted_part():
    from ai_dm.master.relevance import place_keys

    assert place_keys("Подвал таверны") == ["подвал таверны", "подвал"]
    tavern = ["таверна «пьяный дракон»", "таверна", "пьяный дракон"]
    assert place_keys("Таверна «Пьяный Дракон»") == tavern
    assert place_keys("Лавка (Старая)") == ["лавка (старая)", "лавка", "старая"]


def test_place_keys_adjective_is_skipped_to_the_first_noun():
    from ai_dm.master.relevance import place_keys

    assert place_keys("Старая крипта") == ["старая крипта", "крипта"]


def test_place_keys_short_main_word_has_no_key():
    from ai_dm.master.relevance import place_keys

    assert place_keys("Неф Затонувшего собора") == ["неф затонувшего собора"]
    assert place_keys("Дом Веларов") == ["дом веларов"]


def test_place_keys_quoted_part_is_not_a_source_of_the_noun():
    from ai_dm.master.relevance import place_keys

    assert place_keys("Чайная «Под дождём»") == ["чайная «под дождём»", "под дождём"]
    assert place_keys("«Пьяный Дракон»") == ["«пьяный дракон»", "пьяный дракон"]


def test_place_keys_without_a_noun_is_the_full_name_only():
    from ai_dm.master.relevance import place_keys

    assert place_keys("Тёмный лес") == ["тёмный лес"]


def test_travel_intent_dependent_adjective_of_the_name_does_not_move():
    from ai_dm.master.relevance import travel_intent

    places = places_of(WHARF)
    assert travel_intent(places, "иду вдоль каменных домов") is None
    assert travel_intent(places, "иду к гнёздам") is None


def test_travel_intent_dependent_noun_of_the_name_does_not_move():
    from ai_dm.master.relevance import travel_intent

    places = places_of(("nef", "Неф Затонувшего собора"))
    assert travel_intent(places, "иду мимо затонувшего") is None
    assert travel_intent(places, "иду в собор") is None
    assert travel_intent(places, "иду к алтарю собора") is None
    assert travel_intent(places, "иду в Неф Затонувшего собора") == "nef"


def test_travel_intent_name_wholly_in_quotes():
    from ai_dm.master.relevance import travel_intent

    places = places_of(("dragon", "«Пьяный Дракон»"))
    assert travel_intent(places, "иду к дракону") is None
    assert travel_intent(places, "иду в «Пьяный Дракон»") == "dragon"
    assert travel_intent(places, "иду в Пьяный дракон") == "dragon"


def test_travel_intent_basement_by_its_noun_not_by_the_dependent_word():
    from ai_dm.master.relevance import travel_intent

    places = places_of(("cellar", "Подвал таверны"))
    assert travel_intent(places, "иду к выходу из таверны") is None
    assert travel_intent(places, "иду в подвал") == "cellar"


def test_travel_intent_forge_of_master_torin_not_by_the_master():
    from ai_dm.master.relevance import travel_intent

    places = places_of(("forge", "Кузница мастера Торина"))
    assert travel_intent(places, "иду к мастеру") is None
    assert travel_intent(places, "иду в кузницу") == "forge"


def test_travel_intent_quoted_part_of_the_name():
    from ai_dm.master.relevance import travel_intent

    places = places_of(("dragon", "Таверна «Пьяный Дракон»"))
    assert travel_intent(places, "иду в «Пьяный Дракон»") == "dragon"
    assert travel_intent(places, "иду к дракону") is None


def test_travel_intent_part_in_parentheses():
    from ai_dm.master.relevance import travel_intent

    places = places_of(("inn", "Постоялый двор (Ржавый Гвоздь)"))
    assert travel_intent(places, "иду в Ржавый Гвоздь") == "inn"
    assert travel_intent(places, "иду к гвоздю") is None


def test_travel_intent_unknown_place_or_no_places_is_none():
    from ai_dm.master.relevance import travel_intent

    assert travel_intent(places_of(WHARF), "иду в замок") is None
    assert travel_intent([], "иду на причал") is None


def test_place_keys_noun_after_adjective_and_quoted_part_in_the_middle():
    from ai_dm.master.relevance import place_keys

    assert place_keys("Старая «Ржавая» крипта") == ["старая «ржавая» крипта", "крипта", "ржавая"]
