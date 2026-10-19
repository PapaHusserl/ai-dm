# Ожидаемый API: ai_dm.master.prompt.PromptBuilder -- контракт в master_kit.py.
# Порядок: tools -> system[0] (правила) -> system[1] (мир) -> messages[0] (переменное).
# Главное -- стабильность кэшируемого префикса между ходами (llm-notes/claude-api-facts.md).
import json
import re
from importlib import resources

import pytest
from master_kit import app_cfg, combat_ctx, make_bundle, make_ctx, turn_record

from ai_dm.llm.types import ChatRequest, SystemBlock, Text, ToolSpec
from ai_dm.master.prompt import PromptBuilder
from ai_dm.protocol.schema import tool_set

MODES = ["explore", "combat_classify", "combat_narrate", "npc_choice"]
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
TIME_RE = re.compile(r"\b\d{1,2}:\d{2}\b")
UUID_RE = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")


def build(ctx, text="Осматриваюсь.", mode="explore", app=None, **kwargs):
    return PromptBuilder(app or app_cfg(), **kwargs).build(ctx, text, mode)


def data_of(request):
    return json.loads(request.messages[0].content[0].text)


def rules_text():
    return (resources.files("ai_dm.master") / "prompts" / "narrator_rules.md").read_text(
        encoding="utf-8"
    )


# форма запроса

def test_build_returns_chat_request(registry, cfg):
    assert isinstance(build(make_ctx(registry, cfg)), ChatRequest)


def test_request_role_model_and_limits_come_from_config(registry, cfg):
    app = app_cfg()
    request = build(make_ctx(registry, cfg))
    assert request.role == "narrator"
    assert request.model == app.roles.narrator.model
    assert request.max_tokens == app.roles.narrator.max_tokens
    assert request.effort == app.roles.narrator.effort


def test_explicit_model_overrides_role_model(registry, cfg):
    request = build(make_ctx(registry, cfg), model="claude-sonnet-5-5")
    assert request.model == "claude-sonnet-5-5"


@pytest.mark.parametrize("mode", MODES)
def test_tools_are_tool_set_of_mode(registry, cfg, mode):
    request = build(make_ctx(registry, cfg, mode=mode), mode=mode)
    assert request.tools == [ToolSpec.model_validate(d) for d in tool_set(mode)]


@pytest.mark.parametrize("mode", MODES)
def test_tools_are_sorted_by_name(registry, cfg, mode):
    names = [t.name for t in build(make_ctx(registry, cfg, mode=mode), mode=mode).tools]
    assert names == sorted(names)


def test_system_has_three_cached_blocks(registry, cfg):
    system = build(make_ctx(registry, cfg)).system
    assert len(system) == 3
    assert all(isinstance(b, SystemBlock) for b in system)
    assert [b.cache for b in system] == [True, True, True]


def test_turn_message_has_cache_point(registry, cfg):
    messages = build(make_ctx(registry, cfg)).messages
    assert len(messages) == 1
    assert messages[0].cache is True


def test_system_0_is_narrator_rules(registry, cfg):
    assert build(make_ctx(registry, cfg)).system[0].text == rules_text()


def test_system_1_has_monster_and_item_ids_from_registry(registry, cfg):
    text = build(make_ctx(registry, cfg)).system[1].text
    assert "goblin_warrior" in text
    assert "guard" in text
    assert "crowbar" in text


def test_system_1_has_all_registry_monster_ids(registry, cfg):
    text = build(make_ctx(registry, cfg)).system[1].text
    assert [m for m in registry.ids("monster") if m not in text] == []


def test_system_1_has_world_id_and_tone(registry, cfg):
    bundle = make_bundle(registry)
    bundle.world.tone.mood = "мрачное фэнтези"
    text = build(make_ctx(registry, cfg, bundle=bundle)).system[1].text
    assert "w1" in text
    assert "мрачное фэнтези" in text


def test_one_user_message_with_one_text_block(registry, cfg):
    messages = build(make_ctx(registry, cfg)).messages
    assert len(messages) == 1
    assert messages[0].role == "user"
    assert len(messages[0].content) == 1
    assert isinstance(messages[0].content[0], Text)


def test_message_is_json_with_sorted_keys_on_all_levels(registry, cfg):
    ctx = combat_ctx(registry, cfg, mode="combat_narrate")
    ctx.bundle.memory.recent_turns = [turn_record(1)]
    text = build(ctx, mode="combat_narrate").messages[0].content[0].text
    assert text == json.dumps(json.loads(text), sort_keys=True, ensure_ascii=False)


# содержимое messages[0]

def test_message_has_player_input(registry, cfg):
    assert data_of(build(make_ctx(registry, cfg), "Бью стражника!"))["player_input"] == (
        "Бью стражника!"
    )


def test_message_has_date_and_time(registry, cfg):
    ctx = make_ctx(registry, cfg)
    ctx.bundle.world.clock.advance(100_000)
    time = data_of(build(ctx))["time"]
    assert time["date"] == ctx.bundle.world.clock.to_date()
    assert time["now_s"] == 100_000


def test_message_has_hero_location(registry, cfg):
    assert data_of(build(make_ctx(registry, cfg)))["location"] == {"id": "vale", "name": "Вейл"}


def test_message_hero_block(registry, cfg):
    ctx = make_ctx(registry, cfg)
    hero = ctx.hero
    hero.creature.hp_current = 150
    hero.money_cp = 345
    hero.sheet.xp = 40
    data = data_of(build(ctx))["hero"]
    assert data["name"] == "Арн"
    assert data["hp"] == 150
    assert data["hp_max"] == 200
    assert data["gold_cp"] == 345
    assert data["xp"] == 40
    assert data["level"] == 1
    assert {"item_id": "longsword", "qty": 1, "cost_cp": 1500, "name": "Длинный меч"} in (
        data["inventory"]
    )
    assert data["conditions"] == []


def test_message_hero_conditions_are_ids(registry, cfg):
    from ai_dm.state.creature import AppliedCondition

    ctx = make_ctx(registry, cfg)
    ctx.hero.creature.conditions.append(AppliedCondition(id="poisoned"))
    assert data_of(build(ctx))["hero"]["conditions"] == ["poisoned"]


def test_message_scene_npcs_are_alive_npcs_of_hero_location(registry, cfg):
    npcs = data_of(build(make_ctx(registry, cfg)))["scene_npcs"]
    assert [n["id"] for n in npcs] == ["grakh"]
    assert npcs[0]["name"] == "Гракх"
    assert npcs[0]["attitude"] == 0


def test_message_scene_npcs_skip_dead(registry, cfg):
    ctx = make_ctx(registry, cfg)
    ctx.bundle.world.npcs["grakh"].status = "dead"
    assert data_of(build(ctx))["scene_npcs"] == []


def test_message_without_combat_has_null_combat(registry, cfg):
    assert data_of(build(make_ctx(registry, cfg)))["combat"] is None


def test_message_combat_summary(registry, cfg):
    ctx = combat_ctx(registry, cfg, mode="combat_narrate", outcome="victory")
    combat = data_of(build(ctx, mode="combat_narrate"))["combat"]
    assert combat["id"] == ctx.bundle.session.active_combat.id
    assert combat["outcome"] == "victory"
    refs = [p["ref"] for p in combat["participants"]]
    assert "g1" in refs
    assert "g2" in refs


def combat_participants(ctx):
    combat = data_of(build(ctx, mode="combat_narrate"))["combat"]
    return {p["ref"]: p for p in combat["participants"]}


def test_combat_participant_with_conditions_lists_their_ids(registry, cfg):
    from ai_dm.state.creature import AppliedCondition

    ctx = combat_ctx(registry, cfg, mode="combat_narrate")
    target = next(p for p in ctx.bundle.session.active_combat.participants if p.ref == "g1")
    target.creature.conditions.append(AppliedCondition(id="unconscious"))
    target.creature.conditions.append(AppliedCondition(id="poisoned"))
    assert combat_participants(ctx)["g1"]["conditions"] == ["unconscious", "poisoned"]


def test_combat_participant_without_conditions_has_no_key(registry, cfg):
    ctx = combat_ctx(registry, cfg, mode="combat_narrate")
    assert "conditions" not in combat_participants(ctx)["g2"]


def test_combat_conditions_of_a_named_npc_are_listed(registry, cfg):
    from ai_dm.state.creature import AppliedCondition, CreatureState

    ctx = combat_ctx(registry, cfg, mode="combat_narrate")
    target = next(p for p in ctx.bundle.session.active_combat.participants if p.ref == "g1")
    target.creature = None
    npc = ctx.bundle.world.npcs["grakh"]
    target.ref = "grakh"
    npc.creature = CreatureState(hp_current=5, hp_max=5)
    npc.creature.conditions.append(AppliedCondition(id="unconscious"))
    assert combat_participants(ctx)["grakh"]["conditions"] == ["unconscious"]


def test_message_has_offered_choices(registry, cfg):
    ctx = make_ctx(registry, cfg)
    ctx.bundle.session.offered_choices = ["Поговорить", "Уйти"]
    assert data_of(build(ctx))["offered_choices"] == ["Поговорить", "Уйти"]


def test_message_has_recent_turns_in_order(registry, cfg):
    ctx = make_ctx(registry, cfg)
    ctx.bundle.memory.recent_turns = [turn_record(1), turn_record(2)]
    turns = data_of(build(ctx))["recent_turns"]
    assert [t["turn_seq"] for t in turns] == [1, 2]
    assert turns[0]["player_input"] == "ввод 1"
    assert turns[1]["narration"] == "Ход. 2"


def test_recent_turns_window_is_8_by_default(registry, cfg):
    ctx = make_ctx(registry, cfg)
    ctx.bundle.memory.recent_turns = [turn_record(n) for n in range(1, 13)]
    turns = data_of(build(ctx))["recent_turns"]
    assert [t["turn_seq"] for t in turns] == [5, 6, 7, 8, 9, 10, 11, 12]


def test_recent_turns_window_comes_from_config(registry, cfg):
    app = app_cfg().model_copy(deep=True)
    app.master.recent_turns = 3
    ctx = make_ctx(registry, cfg)
    ctx.bundle.memory.recent_turns = [turn_record(n) for n in range(1, 13)]
    turns = data_of(build(ctx, app=app))["recent_turns"]
    assert [t["turn_seq"] for t in turns] == [10, 11, 12]


# бюджет контекста (P3: детерминированная оценка, подробно -- test_master_context*.py)

def small_window_app(window):
    app = app_cfg().model_copy(deep=True)
    app.context_windows["claude-opus-5-5"] = window
    return app


def test_over_budget_drops_oldest_turns_down_to_floor(registry, cfg):
    app = small_window_app(700)
    ctx = make_ctx(registry, cfg)
    ctx.bundle.memory.recent_turns = [turn_record(n) for n in range(1, 9)]
    seqs = [t["turn_seq"] for t in data_of(build(ctx, app=app))["recent_turns"]]
    assert seqs == [8]


def test_within_budget_nothing_is_dropped(registry, cfg):
    ctx = make_ctx(registry, cfg)
    ctx.bundle.memory.recent_turns = [turn_record(n) for n in range(1, 5)]
    assert len(data_of(build(ctx))["recent_turns"]) == 4


def test_model_change_changes_budget(registry, cfg):
    app = small_window_app(100_000)
    app.context_windows["claude-haiku-4-5"] = 500
    ctx = make_ctx(registry, cfg)
    ctx.bundle.memory.recent_turns = [turn_record(n) for n in range(1, 5)]
    on_opus = build(ctx, app=app)
    on_haiku = build(ctx, app=app, model="claude-haiku-4-5")
    assert len(data_of(on_opus)["recent_turns"]) == 4
    assert len(data_of(on_haiku)["recent_turns"]) < 4


def test_budget_never_drops_state_or_rules(registry, cfg):
    app = small_window_app(10)
    ctx = make_ctx(registry, cfg)
    ctx.bundle.memory.recent_turns = [turn_record(n) for n in range(1, 9)]
    request = build(ctx, app=app)
    data = data_of(request)
    assert data["hero"]["name"] == "Арн"
    assert request.system[0].text == rules_text()


def test_budget_floor_zero_can_drop_every_turn(registry, cfg):
    app = small_window_app(10)
    app.master.recent_turns_floor = 0
    ctx = make_ctx(registry, cfg)
    ctx.bundle.memory.recent_turns = [turn_record(n) for n in range(1, 9)]
    assert data_of(build(ctx, app=app))["recent_turns"] == []


def test_build_does_not_change_the_bundle(registry, cfg):
    ctx = make_ctx(registry, cfg)
    ctx.bundle.memory.recent_turns = [turn_record(n) for n in range(1, 13)]
    before = ctx.bundle.model_dump_json()
    build(ctx)
    assert ctx.bundle.model_dump_json() == before


# стабильность префикса

def second_turn_ctx(registry, cfg):
    # другое время, HP, ввод, история и варианты
    ctx = make_ctx(registry, cfg)
    ctx.bundle.world.clock.advance(4321)
    ctx.hero.creature.hp_current = 17
    ctx.hero.money_cp = 999
    ctx.bundle.memory.recent_turns = [turn_record(1), turn_record(2)]
    ctx.bundle.session.offered_choices = ["Да", "Нет"]
    return ctx


@pytest.mark.parametrize("mode", MODES)
def test_tools_bytes_equal_between_turns(registry, cfg, mode):
    one = build(make_ctx(registry, cfg, mode=mode), "Раз", mode)
    two = build(second_turn_ctx(registry, cfg), "Два совсем другое", mode)
    dump_one = json.dumps([t.model_dump() for t in one.tools], sort_keys=True)
    dump_two = json.dumps([t.model_dump() for t in two.tools], sort_keys=True)
    assert dump_one.encode() == dump_two.encode()


def test_system_bytes_equal_between_turns(registry, cfg):
    one = build(make_ctx(registry, cfg), "Раз")
    two = build(second_turn_ctx(registry, cfg), "Два совсем другое")
    assert [b.model_dump_json() for b in one.system] == [b.model_dump_json() for b in two.system]


def test_cacheable_prefix_equal_but_messages_differ(registry, cfg):
    one = build(make_ctx(registry, cfg), "Раз")
    two = build(second_turn_ctx(registry, cfg), "Два совсем другое")
    prefix_one = (one.model_dump_json(include={"tools", "system"}))
    prefix_two = (two.model_dump_json(include={"tools", "system"}))
    assert prefix_one == prefix_two
    assert one.messages != two.messages


def test_last_cache_block_is_last_system_block(registry, cfg):
    system = build(make_ctx(registry, cfg)).system
    cached = [i for i, b in enumerate(system) if b.cache]
    assert max(cached) == len(system) - 1


def test_prefix_is_stable_when_world_flags_and_npcs_change(registry, cfg):
    one = build(make_ctx(registry, cfg))
    ctx = make_ctx(registry, cfg)
    ctx.bundle.world.flags["met_aldric"] = True
    ctx.bundle.world.npcs["aldric"].attitude = 15
    two = build(ctx)
    assert [b.text for b in one.system] == [b.text for b in two.system]


def test_two_builds_of_same_state_are_byte_equal(registry, cfg):
    one = build(make_ctx(registry, cfg))
    two = build(make_ctx(registry, cfg))
    assert one.model_dump_json() == two.model_dump_json()


@pytest.mark.parametrize("index", [0, 1])
def test_system_has_no_time_dates_or_uuid(registry, cfg, index):
    ctx = second_turn_ctx(registry, cfg)
    text = build(ctx).system[index].text
    assert not DATE_RE.search(text)
    assert not TIME_RE.search(text)
    assert not UUID_RE.search(text)
    assert ctx.bundle.world.clock.to_date() not in text


def test_system_has_no_hero_state_or_player_input(registry, cfg):
    text = "".join(b.text for b in build(second_turn_ctx(registry, cfg), "Секретный ввод").system)
    assert "Секретный ввод" not in text
    assert "Гракх" not in text


# D1: world_text

def test_world_text_is_in_system_1(registry, cfg):
    request = PromptBuilder(app_cfg()).build(
        make_ctx(registry, cfg), "Иду.", "explore", world_text="Лор Вейла: древний лес"
    )
    assert "Лор Вейла: древний лес" in request.system[1].text


def test_world_text_does_not_touch_system_0(registry, cfg):
    request = PromptBuilder(app_cfg()).build(
        make_ctx(registry, cfg), "Иду.", "explore", world_text="Лор"
    )
    assert request.system[0].text == rules_text()


def test_system_with_world_text_is_stable_between_turns(registry, cfg):
    builder = PromptBuilder(app_cfg())
    ctx = make_ctx(registry, cfg)
    first = builder.build(ctx, "Первый ход.", "explore", world_text="Лор Вейла")
    ctx.bundle.world.clock.advance(7000)
    ctx.bundle.memory.recent_turns = [turn_record(1)]
    second = builder.build(ctx, "Второй ход.", "explore", world_text="Лор Вейла")
    assert first.system == second.system
    assert first.tools == second.tools


# оценка бюджета: без count_tokens адаптера

def test_builder_has_no_count_tokens_parameter(registry, cfg):
    with pytest.raises(TypeError):
        PromptBuilder(app_cfg(), count_tokens=lambda request: 1)


def test_default_count_tokens_helper_is_gone():
    import ai_dm.master.prompt as prompt

    assert not hasattr(prompt, "default_count_tokens")


def test_estimate_is_deterministic_between_builds(registry, cfg):
    ctx = make_ctx(registry, cfg)
    ctx.bundle.memory.recent_turns = [turn_record(n) for n in range(1, 9)]
    first = PromptBuilder(app_cfg())
    second = PromptBuilder(app_cfg())
    first.build(ctx, "а", "explore")
    second.build(ctx, "а", "explore")
    assert first.last_plan.estimate == second.last_plan.estimate


# варианты боя в state-JSON (TurnContext.combat_options), в system их нет

OPTIONS = [
    {"id": "move:hall", "label": "Шаг в зал"},
    {"id": "attack:longsword:g1", "label": "Атака мечом"},
    {"id": "end_turn", "label": "Закончить ход"},
]


@pytest.mark.parametrize("mode", ["combat_classify", "combat_narrate"])
def test_combat_options_go_to_state_json(registry, cfg, mode):
    ctx = combat_ctx(registry, cfg, mode=mode)
    ctx.combat_options = OPTIONS
    combat = data_of(build(ctx, mode=mode))["combat"]
    assert combat["options"] == OPTIONS


@pytest.mark.parametrize("mode", ["combat_classify", "combat_narrate"])
def test_combat_options_none_gives_empty_list(registry, cfg, mode):
    ctx = combat_ctx(registry, cfg, mode=mode)
    combat = data_of(build(ctx, mode=mode))["combat"]
    assert combat["options"] == []


def test_combat_options_are_not_in_system_blocks(registry, cfg):
    ctx = combat_ctx(registry, cfg, mode="combat_classify")
    ctx.combat_options = OPTIONS
    request = build(ctx, mode="combat_classify")
    system = "\n".join(block.text for block in request.system)
    assert "attack:longsword:g1" not in system
    assert "Шаг в зал" not in system


def test_system_prefix_does_not_depend_on_combat_options(registry, cfg):
    first = combat_ctx(registry, cfg, mode="combat_classify")
    first.combat_options = OPTIONS
    second = combat_ctx(registry, cfg, mode="combat_classify")
    second.combat_options = OPTIONS[:1]
    one = build(first, mode="combat_classify")
    two = build(second, mode="combat_classify")
    assert [b.model_dump_json() for b in one.system] == [b.model_dump_json() for b in two.system]


def test_rules_say_to_use_only_ids_from_combat_options():
    text = rules_text()
    assert "combat.options" in text
    assert "player_action" in text


# E2: id для travel_to и ref в state-JSON

def test_message_locations_have_current_and_linked_with_distance(registry, cfg):
    locations = data_of(build(make_ctx(registry, cfg)))["locations"]
    by_id = {place["id"]: place for place in locations}
    assert set(by_id) == {"vale", "forest"}
    assert by_id["forest"]["name"] == "Лес"
    assert by_id["forest"]["distance_m"] == 4800


def test_message_locations_include_reverse_links(registry, cfg):
    ctx = make_ctx(registry, cfg)
    ctx.hero.location_id = "forest"
    ids = [place["id"] for place in data_of(build(ctx))["locations"]]
    assert "vale" in ids


def test_message_locations_skip_unconnected(registry, cfg):
    ids = [place["id"] for place in data_of(build(make_ctx(registry, cfg)))["locations"]]
    assert "goblin_den" not in ids


def test_message_known_npcs_are_named_alive_with_id_name_location_key(registry, cfg):
    npcs = data_of(build(make_ctx(registry, cfg)))["known_npcs"]
    by_id = {n["id"]: n for n in npcs}
    # с этапа 3 (П3) только релевантные: Олдрик без локации и триггеров не попадает (relevance)
    assert set(by_id) == {"grakh"}
    assert by_id["grakh"]["name"] == "Гракх"
    assert by_id["grakh"]["location_id"] == "vale"
    assert by_id["grakh"]["key"] is True


def test_message_known_npcs_skip_dead_and_unnamed(registry, cfg):
    from ai_dm.state.world import NPC

    ctx = make_ctx(registry, cfg)
    ctx.bundle.world.npcs["aldric"].status = "dead"
    ctx.bundle.world.npcs["rat"] = NPC(id="rat", name="Крыса", means=["зубы"])
    ids = [n["id"] for n in data_of(build(ctx))["known_npcs"]]
    assert ids == ["grakh"]


def test_message_known_npcs_do_not_leak_motive_or_secrets(registry, cfg):
    ctx = make_ctx(registry, cfg)
    ctx.bundle.world.npcs["grakh"].motive = "ТАЙНЫЙ-МОТИВ"
    text = build(ctx).messages[0].content[0].text
    assert "ТАЙНЫЙ-МОТИВ" not in text
    for npc in data_of(build(ctx))["known_npcs"]:
        assert set(npc) == {"id", "name", "location_id", "key"}


def test_vale_start_world_fits_state_json_with_cellar_and_grakh(registry, cfg):
    from ai_dm.config.settings import load_rules_config
    from ai_dm.game.starter import new_world

    bundle = new_world(
        registry, load_rules_config(), hero="arn", seed=1, world_id="w9", saved_at="2026-10-03"
    )
    data = data_of(build(make_ctx(registry, cfg, bundle=bundle)))
    assert "cellar" in [place["id"] for place in data["locations"]]
    grakh = [n for n in data["known_npcs"] if n["id"] == "grakh"][0]
    assert grakh["key"] is True
    assert grakh["location_id"] == "cellar"


# T1: effort и max_tokens по роли выбранной модели

def test_gemini_model_takes_gemini_profile_limits(registry, cfg):
    app = app_cfg()
    profile = app.profiles["gemini"].narrator
    request = build(make_ctx(registry, cfg), model=profile.model)
    assert request.model == profile.model
    assert request.max_tokens == profile.max_tokens
    assert request.effort == profile.effort


def test_alternative_model_takes_alternative_limits(registry, cfg):
    app = app_cfg()
    alt = app.alternatives.narrator
    request = build(make_ctx(registry, cfg), model=alt.model)
    assert (request.max_tokens, request.effort) == (alt.max_tokens, alt.effort)


def test_narrator_max_tokens_is_16000_for_every_narrator_model(registry, cfg):
    app = app_cfg()
    models = [app.roles.narrator.model, app.alternatives.narrator.model]
    models.append(app.profiles["gemini"].narrator.model)
    for model in models:
        assert build(make_ctx(registry, cfg), model=model).max_tokens == 16000



# ТБ #56 (docs/plan-tb.md п.2): рассказчик видит в monster_ids только монстров пака

def scoped(registry, scope):
    reg = registry.with_items({})
    reg.monster_scope = scope
    return reg


def world_data(registry, cfg, reg):
    bundle = make_bundle(registry)
    return json.loads(build(make_ctx(reg, cfg, bundle=bundle)).system[1].text)


def test_system_1_monster_ids_are_scope_only(registry, cfg):
    data = world_data(registry, cfg, scoped(registry, ["wolf", "boar", "guard"]))
    assert data["monster_ids"] == ["boar", "guard", "wolf"]


def test_system_1_without_scope_has_all_monster_ids(registry, cfg):
    assert world_data(registry, cfg, registry)["monster_ids"] == registry.ids("monster")


def test_system_1_scope_keeps_item_ids(registry, cfg):
    scoped_data = world_data(registry, cfg, scoped(registry, ["wolf"]))
    assert scoped_data["item_ids"] == world_data(registry, cfg, registry)["item_ids"]


def test_system_1_scope_is_shorter_than_full_list(registry, cfg):
    short = build(make_ctx(scoped(registry, ["wolf"]), cfg)).system[1].text
    full = build(make_ctx(registry, cfg)).system[1].text
    assert len(short) < len(full)


def test_system_1_scope_is_stable_between_builds(registry, cfg):
    reg = scoped(registry, ["wolf", "boar"])
    first = build(make_ctx(reg, cfg)).system[1].text
    assert build(make_ctx(reg, cfg)).system[1].text == first


# Ж2 коммит 3: divine.deity -- текущий бог героя

def divine_of(registry, cfg, deity):
    ctx = make_ctx(registry, cfg)
    ctx.hero.deity_id = deity
    return data_of(build(ctx))["divine"]


def test_divine_data_has_current_deity(registry, cfg):
    assert divine_of(registry, cfg, "morrah")["deity"] == "morrah"


def test_divine_data_deity_is_none_for_hero_without_god(registry, cfg):
    divine = divine_of(registry, cfg, None)
    assert "deity" in divine
    assert divine["deity"] is None
