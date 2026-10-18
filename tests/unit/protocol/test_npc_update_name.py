# Ж1 (docs/plan-zh1.md, п. 0.7-0.9, коммит 2): npc_update с полем name -- имя выжившего боя.
#   * NpcUpdate.name: "" -- нейтраль (не менять); в схеме рассказчика поле есть и обязательно;
#   * name принимается только для NPC с origin="engine" и named=False; после назначения named=True
#     (known_name не трогается -- игрок имени ещё не слышал);
#   * NPC пака/ai или уже именованный -> Invalid name_locked; имя занято (именованный NPC, бог,
#     фракция, герой) -> rejected, ничего не меняется (отношение тоже);
#   * все строки лога и тексты для игрока зовут NPC через npc_label (shown_name): настоящее имя
#     скрытого выжившего в логах не появляется.
import pytest
from protocol_kit import make_bundle, make_ctx, req

from ai_dm.protocol.apply import apply
from ai_dm.protocol.decision import Decision, Invalid
from ai_dm.protocol.requests import NpcUpdate
from ai_dm.protocol.schema import tool_defs
from ai_dm.state.world import NPC, Faction, God

SID = "goblin_warrior_t1_1"
LABEL = "Воин-гоблин 1"
SECRET_NAME = "Мурк"


def add_survivor(bundle, **fields):
    data = {
        "id": SID, "name": LABEL, "named": False, "means": [LABEL], "origin": "engine",
        "location_id": "vale", "combat": {"monster_id": "goblin_warrior", "label": LABEL},
    }
    npc = NPC(**{**data, **fields})
    bundle.world.npcs[npc.id] = npc


def ctx_with_survivor(registry, cfg, **fields):
    bundle = make_bundle(registry)
    add_survivor(bundle, **fields)
    return make_ctx(registry, cfg, bundle=bundle)


def rename(ctx, name=SECRET_NAME, npc_id=SID, **fields):
    return apply(ctx, req("npc_update", npc_id=npc_id, name=name, **fields))


def survivor(ctx):
    return ctx.bundle.world.npcs[SID]


def text_of(decision):
    # всё, что из решения может дойти до игрока или лога
    parts = [decision.reason, decision.signal_to_master or "", *decision.log]
    return "\n".join(parts)


# запрос и схема

def test_name_neutral_is_empty():
    assert NpcUpdate.NEUTRAL["name"] == ""


def test_name_absent_in_parsed_request_is_none():
    assert req("npc_update", npc_id="aldric", attitude_delta=1).name is None


def test_tool_schema_has_required_name_field():
    schema = tool_defs(["npc_update"])[0]["input_schema"]
    assert "name" in schema["properties"]
    assert "name" in schema["required"]


def test_world_role_npc_update_has_no_name_field():
    schema = tool_defs(["npc_update"], "world")[0]["input_schema"]
    assert "name" not in schema["properties"]


# назначение имени

def test_name_is_assigned_to_unnamed_survivor(registry, cfg):
    ctx = ctx_with_survivor(registry, cfg)
    decision = rename(ctx)
    assert isinstance(decision, Decision)
    assert decision.status == "accepted"
    assert (survivor(ctx).name, survivor(ctx).named) == (SECRET_NAME, True)


def test_assigned_name_stays_hidden_from_player(registry, cfg):
    from ai_dm.rules.npc_names import name_hidden, shown_name

    ctx = ctx_with_survivor(registry, cfg)
    rename(ctx)
    assert survivor(ctx).known_name is None
    assert name_hidden(survivor(ctx)) is True
    assert shown_name(survivor(ctx)) == LABEL


def test_name_log_is_by_label_without_real_name(registry, cfg):
    ctx = ctx_with_survivor(registry, cfg)
    decision = rename(ctx)
    assert decision.log == [f"{LABEL}: получил имя"]
    assert SECRET_NAME not in text_of(decision)


def test_name_with_spaces_is_kept_as_given(registry, cfg):
    ctx = ctx_with_survivor(registry, cfg)
    rename(ctx, name="Мурк Хромой")
    assert survivor(ctx).name == "Мурк Хромой"


def test_name_together_with_attitude_logs_only_label(registry, cfg):
    ctx = ctx_with_survivor(registry, cfg)
    decision = rename(ctx, attitude_delta=5)
    assert survivor(ctx).attitude == 5
    assert SECRET_NAME not in text_of(decision)
    assert any(line.startswith(f"Отношение {LABEL}") for line in decision.log)


def test_name_together_with_memory_logs_only_label(registry, cfg):
    ctx = ctx_with_survivor(registry, cfg)
    decision = rename(ctx, memory_kind="helped", memory_text="помог")
    assert SECRET_NAME not in text_of(decision)
    assert f"{LABEL} запомнил: helped" in decision.log


def test_name_together_with_gender_logs_only_label(registry, cfg):
    ctx = ctx_with_survivor(registry, cfg)
    decision = rename(ctx, gender="male")
    assert SECRET_NAME not in text_of(decision)
    assert decision.log[1].startswith(f"{LABEL}: пол")


def test_name_together_with_follows_logs_only_label(registry, cfg):
    ctx = ctx_with_survivor(registry, cfg)
    decision = rename(ctx, follows="hero")
    assert SECRET_NAME not in text_of(decision)
    assert f"{LABEL} идёт с героем" in decision.log


def test_name_is_assigned_only_once(registry, cfg):
    ctx = ctx_with_survivor(registry, cfg)
    rename(ctx)
    again = rename(ctx, name="Другой")
    assert isinstance(again, Invalid)
    assert again.code == "name_locked"
    assert survivor(ctx).name == SECRET_NAME


# name_locked

def test_pack_npc_name_is_locked(registry, cfg):
    ctx = make_ctx(registry, cfg)
    result = rename(ctx, name="Новое", npc_id="aldric")
    assert isinstance(result, Invalid)
    assert result.code == "name_locked"
    assert ctx.bundle.world.npcs["aldric"].name == "Олдрик"


def test_ai_npc_name_is_locked(registry, cfg):
    ctx = ctx_with_survivor(registry, cfg, origin="ai")
    result = rename(ctx)
    assert isinstance(result, Invalid)
    assert result.code == "name_locked"


def test_engine_npc_already_named_is_locked(registry, cfg):
    ctx = ctx_with_survivor(registry, cfg, named=True)
    result = rename(ctx)
    assert isinstance(result, Invalid)
    assert result.code == "name_locked"
    assert survivor(ctx).name == LABEL


def test_locked_message_uses_label_not_real_name(registry, cfg):
    ctx = ctx_with_survivor(registry, cfg, named=True, name=SECRET_NAME)
    result = rename(ctx, name="Другой")
    assert LABEL in result.message
    assert SECRET_NAME not in result.message


def test_locked_name_leaves_bundle_unchanged(registry, cfg):
    ctx = make_ctx(registry, cfg)
    before = ctx.bundle.model_dump_json()
    rename(ctx, name="Новое", npc_id="aldric")
    assert ctx.bundle.model_dump_json() == before


# занятое имя

def test_name_of_named_npc_is_rejected(registry, cfg):
    ctx = ctx_with_survivor(registry, cfg)
    decision = rename(ctx, name="Олдрик")
    assert isinstance(decision, Decision)
    assert decision.status == "rejected"
    assert (survivor(ctx).name, survivor(ctx).named) == (LABEL, False)


def test_taken_name_ignores_case_and_edge_spaces(registry, cfg):
    ctx = ctx_with_survivor(registry, cfg)
    assert rename(ctx, name="  олдрик ").status == "rejected"


def test_name_of_god_is_rejected(registry, cfg):
    ctx = ctx_with_survivor(registry, cfg)
    ctx.bundle.world.pantheon["morrah"] = God(id="morrah", name="Моррах")
    assert rename(ctx, name="Моррах").status == "rejected"


def test_name_of_faction_is_rejected(registry, cfg):
    ctx = ctx_with_survivor(registry, cfg)
    ctx.bundle.world.factions["guild"] = Faction(id="guild", name="Гильдия")
    assert rename(ctx, name="Гильдия").status == "rejected"


def test_name_of_hero_is_rejected(registry, cfg):
    ctx = ctx_with_survivor(registry, cfg)
    assert rename(ctx, name=ctx.bundle.heroes[0].name).status == "rejected"


@pytest.mark.parametrize("name", [LABEL, "Воин-гоблин", "  воин-гоблин 1 ", "Кабан"])
def test_kind_as_name_is_rejected(registry, cfg, name):
    ctx = ctx_with_survivor(registry, cfg)
    decision = rename(ctx, name=name)
    assert isinstance(decision, Decision)
    assert decision.status == "rejected"
    assert (survivor(ctx).name, survivor(ctx).named) == (LABEL, False)


def test_kind_as_name_signals_master_to_pick_personal_name(registry, cfg):
    ctx = ctx_with_survivor(registry, cfg)
    decision = rename(ctx, name=LABEL)
    assert LABEL in decision.signal_to_master
    assert "личное имя" in decision.signal_to_master


def test_kind_as_name_changes_nothing_else(registry, cfg):
    ctx = ctx_with_survivor(registry, cfg)
    before = ctx.bundle.model_dump_json()
    rename(ctx, name=LABEL, attitude_delta=5, memory_kind="helped", memory_text="помог")
    assert ctx.bundle.model_dump_json() == before


def test_kind_as_name_is_checked_before_name_conflict(registry, cfg):
    ctx = ctx_with_survivor(registry, cfg)
    ctx.bundle.world.npcs["thug"] = NPC(id="thug", name=LABEL, named=True, means=["x"])
    decision = rename(ctx, name=LABEL)
    assert decision.status == "rejected"
    assert "личное имя" in decision.signal_to_master


def test_personal_name_with_kind_word_is_accepted(registry, cfg):
    ctx = ctx_with_survivor(registry, cfg)
    assert rename(ctx, name="Мурк Кабан").status == "accepted"


def test_rejected_name_helper_returns_none_for_free_personal_name(registry, cfg):
    from ai_dm.protocol.handlers.world import rejected_name

    ctx = ctx_with_survivor(registry, cfg)
    assert rejected_name(ctx, survivor(ctx), SECRET_NAME) is None


def test_rejected_name_helper_rejects_kind_and_taken_names(registry, cfg):
    from ai_dm.protocol.handlers.world import rejected_name

    ctx = ctx_with_survivor(registry, cfg)
    assert rejected_name(ctx, survivor(ctx), LABEL).status == "rejected"
    assert rejected_name(ctx, survivor(ctx), "Олдрик").status == "rejected"


def test_empty_name_is_invalid_not_rejected(registry, cfg):
    ctx = ctx_with_survivor(registry, cfg)
    assert isinstance(rename(ctx, name="   "), Invalid)


def test_rejected_name_signals_master_to_pick_another(registry, cfg):
    ctx = ctx_with_survivor(registry, cfg)
    decision = rename(ctx, name="Олдрик")
    assert "Олдрик" in decision.signal_to_master
    assert "другое имя" in decision.signal_to_master


def test_rejected_name_changes_nothing_else(registry, cfg):
    ctx = ctx_with_survivor(registry, cfg)
    before = ctx.bundle.model_dump_json()
    rename(ctx, name="Олдрик", attitude_delta=5, memory_kind="helped", memory_text="помог")
    assert ctx.bundle.model_dump_json() == before


def test_two_survivors_cannot_take_the_same_name(registry, cfg):
    ctx = ctx_with_survivor(registry, cfg)
    add_survivor(ctx.bundle, id="goblin_warrior_t1_2", name="Воин-гоблин 2")
    rename(ctx)
    second = rename(ctx, npc_id="goblin_warrior_t1_2")
    assert second.status == "rejected"


def test_unnamed_npc_with_same_name_does_not_block(registry, cfg):
    ctx = ctx_with_survivor(registry, cfg)
    ctx.bundle.world.npcs["thug"] = NPC(id="thug", name=SECRET_NAME, named=False, means=["x"])
    assert rename(ctx).status == "accepted"


# пустое и неизвестное

def test_empty_name_alone_is_empty_update(registry, cfg):
    ctx = ctx_with_survivor(registry, cfg)
    result = rename(ctx, name="")
    assert isinstance(result, Invalid)
    assert result.code == "empty_update"


def test_empty_name_with_other_change_does_not_rename(registry, cfg):
    ctx = ctx_with_survivor(registry, cfg)
    rename(ctx, name="", attitude_delta=3)
    assert (survivor(ctx).name, survivor(ctx).named) == (LABEL, False)


# имя обрезается по краям

def test_blank_name_is_empty_name(registry, cfg):
    ctx = ctx_with_survivor(registry, cfg)
    result = rename(ctx, name="  ")
    assert isinstance(result, Invalid)
    assert result.code == "empty_name"
    assert (survivor(ctx).name, survivor(ctx).named) == (LABEL, False)


def test_blank_name_changes_nothing_even_with_other_fields(registry, cfg):
    ctx = ctx_with_survivor(registry, cfg)
    before = ctx.bundle.model_dump_json()
    rename(ctx, name="\t ", attitude_delta=5)
    assert ctx.bundle.model_dump_json() == before


def test_name_is_stored_trimmed(registry, cfg):
    ctx = ctx_with_survivor(registry, cfg)
    assert rename(ctx, name=" Грок ").status == "accepted"
    assert (survivor(ctx).name, survivor(ctx).named) == ("Грок", True)


def test_trimmed_name_is_opened_by_text(registry, cfg):
    from ai_dm.rules.survivors import reveal_names

    ctx = ctx_with_survivor(registry, cfg)
    rename(ctx, name=" Грок ")
    reveal_names(ctx.hero, ctx.bundle.world, "Гоблин хрипит: я Грок.")
    assert survivor(ctx).known_name == "Грок"


def test_taken_check_uses_trimmed_name(registry, cfg):
    ctx = ctx_with_survivor(registry, cfg)
    decision = rename(ctx, name="  Олдрик  ")
    assert decision.status == "rejected"
    assert survivor(ctx).named is False


def test_trimmed_name_log_has_no_real_name(registry, cfg):
    ctx = ctx_with_survivor(registry, cfg)
    decision = rename(ctx, name=" Грок ")
    assert "Грок" not in text_of(decision)


# npc_label в прочих логах и сообщениях

def hidden_named(registry, cfg, **fields):
    # имя уже придумано (named=True), но игрок его не слышал
    return ctx_with_survivor(registry, cfg, named=True, name=SECRET_NAME, **fields)


def update(ctx, **fields):
    return apply(ctx, req("npc_update", npc_id=SID, **fields))


def test_attitude_log_uses_label(registry, cfg):
    ctx = hidden_named(registry, cfg)
    decision = update(ctx, attitude_delta=4)
    assert decision.log[0] == f"Отношение {LABEL}: +4 (теперь 4)"
    assert SECRET_NAME not in text_of(decision)


def test_follows_log_uses_label(registry, cfg):
    ctx = hidden_named(registry, cfg)
    decision = update(ctx, follows="hero")
    assert decision.log == [f"{LABEL} идёт с героем"]


def test_unfollow_log_uses_label(registry, cfg):
    ctx = hidden_named(registry, cfg, follows="hero")
    decision = update(ctx, follows="none")
    assert decision.log == [f"{LABEL} остаётся (не идёт с героем)"]


def test_memory_log_uses_label(registry, cfg):
    ctx = hidden_named(registry, cfg)
    decision = update(ctx, memory_kind="helped", memory_text="помог")
    assert decision.log == [f"{LABEL} запомнил: helped"]


def test_long_memory_note_log_uses_label(registry, cfg):
    ctx = hidden_named(registry, cfg)
    decision = update(ctx, memory_kind="helped", memory_text="а" * 300)
    assert SECRET_NAME not in text_of(decision)
    assert f"{LABEL}: текст укорочен до 120" in decision.log


def test_identity_log_uses_label(registry, cfg):
    ctx = hidden_named(registry, cfg)
    decision = update(ctx, pronouns="он")
    assert decision.log == [f"{LABEL}: местоимения он"]


def test_memory_limit_signal_uses_label(registry, cfg):
    ctx = hidden_named(registry, cfg)
    for n in range(cfg.npc_memory.max_events_per_scene):
        update(ctx, memory_kind="helped", memory_text=f"помог {n}")
    decision = update(ctx, memory_kind="helped", memory_text="ещё")
    assert decision.status == "rejected"
    assert decision.signal_to_master.startswith(LABEL)
    assert SECRET_NAME not in text_of(decision)


def test_not_alive_follow_message_uses_label(registry, cfg):
    ctx = hidden_named(registry, cfg, status="dead")
    result = update(ctx, follows="hero")
    assert result.message == f"{LABEL} не жив: не идёт с героем"


def test_death_refusal_signal_uses_label(registry, cfg):
    ctx = hidden_named(registry, cfg)
    decision = update(ctx, status="dead", cause="goal")
    assert decision.status == "rejected"
    assert decision.signal_to_master.startswith(f"{LABEL} остаётся жив")
    assert SECRET_NAME not in text_of(decision)


def test_trade_kind_for_dead_survivor_message_uses_label(registry, cfg):
    ctx = hidden_named(registry, cfg, status="dead")
    result = update(ctx, trade_kind="general")
    assert result.message == f"{LABEL} не жив: не торгует"


def test_trade_kind_log_uses_label(registry, cfg):
    ctx = hidden_named(registry, cfg)
    decision = update(ctx, trade_kind="general")
    assert decision.status == "accepted"
    assert decision.log == [f"{LABEL} торгует: general"]
    assert decision.result["trade_kind"] == "general"


def test_second_trade_kind_is_rejected_with_label(registry, cfg):
    ctx = hidden_named(registry, cfg)
    update(ctx, trade_kind="general")
    decision = update(ctx, trade_kind="general")
    assert decision.status == "rejected"
    assert decision.reason == f"{LABEL} уже торговец"
    assert decision.signal_to_master == f"{LABEL} уже торгует: тип торговца не меняется."


def test_known_name_is_used_in_logs_once_opened(registry, cfg):
    ctx = hidden_named(registry, cfg, known_name=SECRET_NAME)
    decision = update(ctx, follows="hero")
    assert decision.log == [f"{SECRET_NAME} идёт с героем"]


def test_pack_npc_log_keeps_real_name(registry, cfg):
    ctx = make_ctx(registry, cfg)
    decision = apply(ctx, req("npc_update", npc_id="aldric", follows="hero"))
    assert decision.log == ["Олдрик идёт с героем"]
