# Ж0 подшаг 2 (docs/plan-zh0.md, пп. 15-16): память NPC через npc_update.
# Ожидаемый API: NpcUpdate.memory_kind: Literal[MEMORY_KINDS + "none"] = "none",
#   memory_text: str = "" (<= NPC_EVENT_TEXT_MAX, пусто = нет); в WorldNpcUpdate полей памяти нет.
#   * memory_text без memory_kind (none) -> Invalid; память пишет только npc_update рассказчика;
#   * вид + текст -> событие в NPC.memory за текущую сцену (current_scene), turn_seq -- ctx.turn_seq
#     если есть; запись после change_attitude, вес записи = attitude_spent[npc] после изменения;
#   * нет current_scene -> Invalid, code "no_scene";
#   * лимит событий в сцене (cfg.npc_memory.max_events_per_scene) -> rejected, report_tag
#     "limit-exceeded", память не растёт;
#   * change_attitude обновляет вес уже записанной за эту сцену памяти (refresh_weight).
import pytest
from protocol_kit import dump, make_bundle, make_ctx, req

from ai_dm.protocol.apply import apply
from ai_dm.protocol.decision import Invalid
from ai_dm.protocol.handlers.world import shorten_memory_text
from ai_dm.protocol.requests import NpcUpdate
from ai_dm.protocol.schema import tool_defs
from ai_dm.state.relations import MEMORY_KINDS, NPC_EVENT_TEXT_MAX


def remember_call(ctx, kind="helped", text="помог с долгом", **fields):
    return apply(
        ctx, req("npc_update", npc_id="aldric", memory_kind=kind, memory_text=text, **fields)
    )


def memory(ctx):
    return ctx.bundle.world.npcs["aldric"].memory


# запрос

def test_memory_kind_neutral_is_none_value():
    assert NpcUpdate.NEUTRAL["memory_kind"] == "none"


def test_memory_text_neutral_is_empty():
    assert NpcUpdate.NEUTRAL["memory_text"] == ""


def test_memory_fields_absent_in_parsed_request_are_none():
    request = req("npc_update", npc_id="aldric", attitude_delta=1)
    assert (request.memory_kind, request.memory_text) == (None, None)


@pytest.mark.parametrize("kind", MEMORY_KINDS)
def test_every_memory_kind_is_accepted(kind, registry, cfg):
    ctx = make_ctx(registry, cfg)
    assert remember_call(ctx, kind).status == "accepted"


def test_unknown_memory_kind_is_rejected_by_parser():
    with pytest.raises(ValueError):
        req("npc_update", npc_id="aldric", memory_kind="whatever", memory_text="x")


def test_tool_schema_lists_memory_kind_enum():
    schema = tool_defs(["npc_update"])[0]["input_schema"]
    assert set(schema["properties"]["memory_kind"]["enum"]) == {*MEMORY_KINDS, "none"}


def test_tool_schema_requires_memory_fields():
    schema = tool_defs(["npc_update"])[0]["input_schema"]
    assert {"memory_kind", "memory_text"} <= set(schema["required"])


# схема режима world: памяти нет (Q7)

def test_world_role_npc_update_has_no_memory_fields():
    schema = tool_defs(["npc_update"], "world")[0]["input_schema"]
    assert "memory_kind" not in schema["properties"]
    assert "memory_text" not in schema["properties"]


def test_world_role_npc_update_memory_not_required():
    schema = tool_defs(["npc_update"], "world")[0]["input_schema"]
    assert "memory_kind" not in schema["required"]
    assert "memory_text" not in schema["required"]


# запись

def test_memory_only_update_is_accepted(registry, cfg):
    ctx = make_ctx(registry, cfg)
    assert remember_call(ctx).status == "accepted"


def test_memory_kind_with_empty_text_is_accepted(registry, cfg):
    ctx = make_ctx(registry, cfg)
    assert remember_call(ctx, "helped", "").status == "accepted"


def test_memory_kind_with_empty_text_stores_empty_text(registry, cfg):
    ctx = make_ctx(registry, cfg)
    remember_call(ctx, "helped", "")
    assert memory(ctx)[0].events[0].text == ""


def test_memory_event_is_stored_with_kind_and_text(registry, cfg):
    ctx = make_ctx(registry, cfg)
    remember_call(ctx, "gift", "подарил кинжал")
    [event] = memory(ctx)[0].events
    assert (event.kind, event.text) == ("gift", "подарил кинжал")


def test_memory_entry_belongs_to_current_scene(registry, cfg):
    ctx = make_ctx(registry, cfg)
    remember_call(ctx)
    assert memory(ctx)[0].scene_id == "scene_1"


def test_memory_event_has_log_line(registry, cfg):
    ctx = make_ctx(registry, cfg)
    assert remember_call(ctx).log


def test_two_events_in_one_scene_share_entry(registry, cfg):
    ctx = make_ctx(registry, cfg)
    remember_call(ctx, "helped", "раз")
    remember_call(ctx, "gift", "два")
    assert len(memory(ctx)) == 1
    assert len(memory(ctx)[0].events) == 2


def test_memory_kind_none_with_attitude_writes_nothing(registry, cfg):
    ctx = make_ctx(registry, cfg)
    apply(ctx, req("npc_update", npc_id="aldric", attitude_delta=5, memory_kind="none"))
    assert memory(ctx) == []


# порядок: после change_attitude

def test_memory_weight_includes_attitude_change_of_same_request(registry, cfg):
    ctx = make_ctx(registry, cfg)
    remember_call(ctx, attitude_delta=7)
    assert memory(ctx)[0].weight == 7


def test_memory_weight_counts_clamped_attitude(registry, cfg):
    ctx = make_ctx(registry, cfg)
    remember_call(ctx, attitude_delta=50)
    assert memory(ctx)[0].weight == cfg.attitude.step


def test_memory_weight_is_absolute_for_negative_delta(registry, cfg):
    ctx = make_ctx(registry, cfg)
    remember_call(ctx, "insult", "оскорбил", attitude_delta=-6)
    assert memory(ctx)[0].weight == 6


def test_memory_without_attitude_change_has_zero_weight(registry, cfg):
    ctx = make_ctx(registry, cfg)
    remember_call(ctx)
    assert memory(ctx)[0].weight == 0


# refresh_weight в change_attitude

def test_later_attitude_change_refreshes_weight_of_scene_memory(registry, cfg):
    ctx = make_ctx(registry, cfg)
    remember_call(ctx, attitude_delta=5)
    apply(ctx, req("npc_update", npc_id="aldric", attitude_delta=8))
    assert memory(ctx)[0].weight == 13


def test_attitude_change_without_memory_creates_none(registry, cfg):
    ctx = make_ctx(registry, cfg)
    apply(ctx, req("npc_update", npc_id="aldric", attitude_delta=8))
    assert memory(ctx) == []


def test_attitude_change_of_other_npc_does_not_touch_weight(registry, cfg):
    ctx = make_ctx(registry, cfg)
    remember_call(ctx, attitude_delta=5)
    apply(ctx, req("npc_update", npc_id="grakh", attitude_delta=8))
    assert memory(ctx)[0].weight == 5


def test_memory_text_over_limit_is_truncated(registry, cfg):
    ctx = make_ctx(registry, cfg)
    remember_call(ctx, text="я" * 300)
    assert memory(ctx)[0].events[0].text == "я" * (NPC_EVENT_TEXT_MAX - 1) + "…"


def test_memory_text_at_limit_is_kept(registry, cfg):
    ctx = make_ctx(registry, cfg)
    remember_call(ctx, text="я" * NPC_EVENT_TEXT_MAX)
    assert len(memory(ctx)[0].events[0].text) == NPC_EVENT_TEXT_MAX


# укорочение текста памяти (подшаг 2, последнее решение)

def test_shorten_text_at_limit_is_unchanged():
    text = "я" * NPC_EVENT_TEXT_MAX
    assert shorten_memory_text(text) == text


def test_shorten_empty_text_is_unchanged():
    assert shorten_memory_text("") == ""


def test_shorten_text_one_over_limit_is_changed():
    result = shorten_memory_text("я" * (NPC_EVENT_TEXT_MAX + 1))
    assert result == "я" * (NPC_EVENT_TEXT_MAX - 1) + "…"


def test_shorten_cuts_at_last_space():
    text = "слово " * 30
    head = text[: NPC_EVENT_TEXT_MAX - 1]
    assert shorten_memory_text(text) == head[: head.rfind(" ")] + "…"


def test_shorten_result_fits_limit():
    assert len(shorten_memory_text("слово " * 50)) <= NPC_EVENT_TEXT_MAX


def test_shorten_no_space_before_ellipsis():
    # пробел сразу перед срезом (индекс 118) -- не остаётся перед «…»
    text = "я" * 118 + " " + "я" * 50
    assert shorten_memory_text(text) == "я" * 118 + "…"


def test_shorten_strips_several_spaces_before_ellipsis():
    text = "я" * 100 + "   " + "я" * 100
    assert shorten_memory_text(text) == "я" * 100 + "…"


def test_shorten_space_at_index_119_is_ignored():
    # пробел на индексе 119 вне head (text[:119]): жёсткий срез по 119 знакам
    text = "я" * 119 + " " + "я" * 50
    assert shorten_memory_text(text) == "я" * 119 + "…"


def test_shorten_no_spaces_is_hard_cut():
    assert shorten_memory_text("я" * 300) == "я" * 119 + "…"


def test_shorten_space_only_at_position_zero_is_hard_cut():
    text = " " + "я" * 300
    assert shorten_memory_text(text) == (" " + "я" * 118).rstrip() + "…"


def test_shorten_space_at_position_one_cuts_there():
    text = "я " + "я" * 300
    assert shorten_memory_text(text) == "я…"


def test_memory_text_at_limit_is_accepted(registry, cfg):
    ctx = make_ctx(registry, cfg)
    assert remember_call(ctx, text="я" * NPC_EVENT_TEXT_MAX).status == "accepted"


def test_memory_text_at_limit_has_no_tag(registry, cfg):
    ctx = make_ctx(registry, cfg)
    assert remember_call(ctx, text="я" * NPC_EVENT_TEXT_MAX).report_tag is None


def test_memory_text_at_limit_has_no_shorten_signal(registry, cfg):
    ctx = make_ctx(registry, cfg)
    d = remember_call(ctx, text="я" * NPC_EVENT_TEXT_MAX)
    assert not d.signal_to_master


def test_memory_text_at_limit_has_no_shorten_log(registry, cfg):
    ctx = make_ctx(registry, cfg)
    d = remember_call(ctx, text="я" * NPC_EVENT_TEXT_MAX)
    assert not any("укорочен" in line for line in d.log)


def test_memory_text_over_limit_by_one_is_clamped(registry, cfg):
    ctx = make_ctx(registry, cfg)
    assert remember_call(ctx, text="я" * (NPC_EVENT_TEXT_MAX + 1)).status == "clamped"


def test_memory_text_over_limit_is_clamped(registry, cfg):
    ctx = make_ctx(registry, cfg)
    assert remember_call(ctx, text="я" * 300).status == "clamped"


def test_memory_text_over_limit_has_text_shortened_tag(registry, cfg):
    ctx = make_ctx(registry, cfg)
    assert remember_call(ctx, text="я" * 300).report_tag == "text-shortened"


def test_memory_text_over_limit_reason(registry, cfg):
    ctx = make_ctx(registry, cfg)
    assert remember_call(ctx, text="я" * 300).reason == "текст укорочен до 120"


def test_memory_text_over_limit_signal(registry, cfg):
    ctx = make_ctx(registry, cfg)
    d = remember_call(ctx, text="я" * 300)
    assert d.signal_to_master == "Память NPC: текст укорочен до 120 знаков."


def test_memory_text_over_limit_log_line(registry, cfg):
    ctx = make_ctx(registry, cfg)
    d = remember_call(ctx, text="я" * 300)
    assert "Олдрик: текст укорочен до 120" in d.log


def test_memory_text_over_limit_still_logs_remembered(registry, cfg):
    ctx = make_ctx(registry, cfg)
    d = remember_call(ctx, text="я" * 300)
    assert "Олдрик запомнил: helped" in d.log


def test_memory_text_over_limit_event_is_recorded(registry, cfg):
    ctx = make_ctx(registry, cfg)
    remember_call(ctx, text="слово " * 50)
    assert len(memory(ctx)[0].events) == 1


def test_memory_text_over_limit_event_text_is_shortened(registry, cfg):
    ctx = make_ctx(registry, cfg)
    text = "слово " * 50
    remember_call(ctx, text=text)
    assert memory(ctx)[0].events[0].text == shorten_memory_text(text)


def test_memory_text_over_limit_event_text_ends_with_ellipsis(registry, cfg):
    ctx = make_ctx(registry, cfg)
    remember_call(ctx, text="слово " * 50)
    assert memory(ctx)[0].events[0].text.endswith("слово…")


def test_memory_text_over_limit_with_clamped_attitude_stays_clamped(registry, cfg):
    ctx = make_ctx(registry, cfg)
    d = remember_call(ctx, text="я" * 300, attitude_delta=50)
    assert d.status == "clamped"
    assert d.report_tag == "limit-exceeded"


def test_memory_text_over_limit_with_clamped_attitude_joins_reason(registry, cfg):
    ctx = make_ctx(registry, cfg)
    d = remember_call(ctx, text="я" * 300, attitude_delta=50)
    assert d.reason == f"запрошено +50, применено +{cfg.attitude.step}; текст укорочен до 120"


def test_memory_text_over_limit_with_clamped_attitude_joins_signal(registry, cfg):
    ctx = make_ctx(registry, cfg)
    d = remember_call(ctx, text="я" * 300, attitude_delta=50)
    assert d.signal_to_master == (
        f"Отношение изменено только на +{cfg.attitude.step}: опиши реакцию по факту. "
        "Память NPC: текст укорочен до 120 знаков."
    )


def test_memory_text_over_limit_with_clamped_attitude_writes_shortened_text(registry, cfg):
    ctx = make_ctx(registry, cfg)
    remember_call(ctx, text="я" * 300, attitude_delta=50)
    assert memory(ctx)[0].events[0].text == "я" * 119 + "…"


# Invalid

def test_memory_text_without_kind_is_invalid(registry, cfg):
    ctx = make_ctx(registry, cfg)
    d = apply(ctx, req("npc_update", npc_id="aldric", memory_text="что-то было"))
    assert isinstance(d, Invalid)


def test_memory_text_alone_has_own_code(registry, cfg):
    ctx = make_ctx(registry, cfg)
    d = apply(ctx, req("npc_update", npc_id="aldric", memory_text="что-то было"))
    assert isinstance(d, Invalid)
    assert d.code == "memory_text_without_kind"


def test_memory_text_without_kind_next_to_attitude_has_own_code(registry, cfg):
    ctx = make_ctx(registry, cfg)
    d = apply(
        ctx, req("npc_update", npc_id="aldric", attitude_delta=5, memory_text="что-то было")
    )
    assert isinstance(d, Invalid)
    assert d.code == "memory_text_without_kind"


def test_memory_text_without_kind_changes_nothing(registry, cfg):
    ctx = make_ctx(registry, cfg)
    before = dump(ctx)
    apply(ctx, req("npc_update", npc_id="aldric", attitude_delta=5, memory_text="что-то было"))
    assert dump(ctx) == before


def test_memory_without_scene_is_invalid_no_scene(registry, cfg):
    ctx = make_ctx(registry, cfg, bundle=make_bundle(registry, with_scene=False))
    d = remember_call(ctx)
    assert isinstance(d, Invalid)
    assert d.code == "no_scene"


def test_memory_without_scene_writes_nothing(registry, cfg):
    ctx = make_ctx(registry, cfg, bundle=make_bundle(registry, with_scene=False))
    remember_call(ctx)
    assert memory(ctx) == []


# лимит событий

def fill_scene(ctx, cfg):
    for i in range(cfg.npc_memory.max_events_per_scene):
        assert remember_call(ctx, text=f"событие {i}").status == "accepted"


def test_event_over_limit_is_rejected(registry, cfg):
    ctx = make_ctx(registry, cfg)
    fill_scene(ctx, cfg)
    assert remember_call(ctx, text="лишнее").status == "rejected"


def test_event_over_limit_has_limit_exceeded_tag(registry, cfg):
    ctx = make_ctx(registry, cfg)
    fill_scene(ctx, cfg)
    assert remember_call(ctx, text="лишнее").report_tag == "limit-exceeded"


def test_event_over_limit_tells_master(registry, cfg):
    ctx = make_ctx(registry, cfg)
    fill_scene(ctx, cfg)
    assert remember_call(ctx, text="лишнее").signal_to_master


def test_event_over_limit_does_not_grow_memory(registry, cfg):
    ctx = make_ctx(registry, cfg)
    fill_scene(ctx, cfg)
    remember_call(ctx, text="лишнее")
    assert len(memory(ctx)[0].events) == cfg.npc_memory.max_events_per_scene


def test_event_over_limit_with_attitude_is_rejected(registry, cfg):
    ctx = make_ctx(registry, cfg)
    fill_scene(ctx, cfg)
    assert remember_call(ctx, text="лишнее", attitude_delta=5).status == "rejected"


def test_event_over_limit_with_attitude_has_limit_exceeded_tag(registry, cfg):
    ctx = make_ctx(registry, cfg)
    fill_scene(ctx, cfg)
    assert remember_call(ctx, text="лишнее", attitude_delta=5).report_tag == "limit-exceeded"


def test_event_over_limit_with_attitude_keeps_attitude(registry, cfg):
    ctx = make_ctx(registry, cfg)
    fill_scene(ctx, cfg)
    before = ctx.bundle.world.npcs["aldric"].attitude
    remember_call(ctx, text="лишнее", attitude_delta=5)
    assert ctx.bundle.world.npcs["aldric"].attitude == before


def test_event_over_limit_with_attitude_keeps_attitude_spent(registry, cfg):
    ctx = make_ctx(registry, cfg)
    fill_scene(ctx, cfg)
    before = dict(ctx.bundle.session.current_scene.attitude_spent)
    remember_call(ctx, text="лишнее", attitude_delta=5)
    assert ctx.bundle.session.current_scene.attitude_spent == before


def test_event_over_limit_with_attitude_keeps_weight(registry, cfg):
    ctx = make_ctx(registry, cfg)
    fill_scene(ctx, cfg)
    remember_call(ctx, text="лишнее", attitude_delta=5)
    assert memory(ctx)[0].weight == 0


def test_event_over_limit_with_attitude_changes_nothing(registry, cfg):
    ctx = make_ctx(registry, cfg)
    fill_scene(ctx, cfg)
    before = dump(ctx)
    remember_call(ctx, text="лишнее", attitude_delta=5)
    assert dump(ctx) == before


def test_event_over_limit_stays_in_next_scene_ok(registry, cfg):
    from ai_dm.state.scene import SceneState

    ctx = make_ctx(registry, cfg)
    fill_scene(ctx, cfg)
    ctx.bundle.session.current_scene = SceneState(id="scene_2", started_at_s=500)
    assert remember_call(ctx).status == "accepted"
    assert [m.scene_id for m in memory(ctx)] == ["scene_1", "scene_2"]


def test_memory_over_scene_limit_evicts_lowest_weight(registry, cfg):
    from ai_dm.state.scene import SceneState

    ctx = make_ctx(registry, cfg)
    for n in range(1, cfg.npc_memory.max_scenes + 2):
        ctx.bundle.session.current_scene = SceneState(id=f"s{n}", started_at_s=n * 100)
        # у сцены 1 вес 1, у остальных 10 (знак чередуется: отношение не упирается в 100)
        remember_call(ctx, attitude_delta=1 if n == 1 else (10 if n % 2 else -10))
    assert len(memory(ctx)) == cfg.npc_memory.max_scenes
    assert "s1" not in [m.scene_id for m in memory(ctx)]
