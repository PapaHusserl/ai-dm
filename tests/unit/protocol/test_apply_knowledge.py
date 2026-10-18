# Ж3 (docs/plan-zh3.md, пп. 0.2, 0.4-0.5, 0.8): запросы knowledge_note и scene_mood.
#   * knowledge_note{kind, ref, text, source, from_ref}: запись в hero.knowledge с at_s = now_s;
#     Invalid: empty_text, unknown_ref (+допустимые id), bad_ref (ситуация -- слаг a-z0-9_ 2-40),
#     told_without_from, unknown_npc (from_ref); дубль и спойлер -- rejected; длинный текст --
#     clamped "text-shortened"; лимит записей на сущность -- FIFO;
#   * scene_mood{mood: romance|none}: ставит/снимает scene.scene_mood; нет сцены -- Invalid
#     no_scene;
#   * reveal_secret и favor_change героя пишут журнал сами.
import pytest
from protocol_kit import dump, make_bundle, make_ctx, req

from ai_dm.protocol.apply import apply
from ai_dm.protocol.decision import Decision, Invalid
from ai_dm.state.knowledge import KNOWLEDGE_TEXT_MAX
from ai_dm.state.triggers import Secret
from ai_dm.state.world import Faction, God

SECRET_TEXT = "сестра Олдрика обращена вампиром и прячется в склепе"


def knowledge_ctx(registry, cfg, with_scene=True, now_s=500):
    bundle = make_bundle(registry, with_scene=with_scene)
    bundle.world.clock.now_s = now_s
    bundle.world.factions["guild"] = Faction(id="guild", name="Гильдия")
    bundle.world.pantheon["selune"] = God(id="selune", name="Селунэ")
    bundle.world.npcs["aldric"].secrets.append(
        Secret.model_validate({"id": "sister", "text": SECRET_TEXT, "reveal_if": {"flag": "found"}})
    )
    return make_ctx(registry, cfg, bundle=bundle)


def note(kind="npc", ref="aldric", text="Хранит ключ от склепа", source="seen", from_ref=""):
    return req("knowledge_note", kind=kind, ref=ref, text=text, source=source, from_ref=from_ref)


def journal(ctx):
    return ctx.hero.knowledge


# приём записи

def test_note_is_accepted(registry, cfg):
    ctx = knowledge_ctx(registry, cfg)
    d = apply(ctx, note())
    assert isinstance(d, Decision)
    assert d.status == "accepted"


def test_note_is_written_to_hero_journal(registry, cfg):
    ctx = knowledge_ctx(registry, cfg)
    apply(ctx, note(source="rumor"))
    [entry] = journal(ctx)
    assert (entry.kind, entry.ref, entry.text, entry.source) == (
        "npc", "aldric", "Хранит ключ от склепа", "rumor"
    )


def test_note_time_is_world_clock(registry, cfg):
    ctx = knowledge_ctx(registry, cfg, now_s=777)
    apply(ctx, note())
    assert journal(ctx)[0].at_s == 777


def test_note_without_from_ref_has_none(registry, cfg):
    ctx = knowledge_ctx(registry, cfg)
    apply(ctx, note())
    assert journal(ctx)[0].from_ref is None


def test_told_keeps_from_ref(registry, cfg):
    ctx = knowledge_ctx(registry, cfg)
    d = apply(ctx, note(source="told", from_ref="grakh"))
    assert d.status == "accepted"
    assert (journal(ctx)[0].source, journal(ctx)[0].from_ref) == ("told", "grakh")


def test_non_told_source_may_have_from_ref(registry, cfg):
    ctx = knowledge_ctx(registry, cfg)
    assert apply(ctx, note(source="rumor", from_ref="grakh")).status == "accepted"


def test_text_is_trimmed(registry, cfg):
    ctx = knowledge_ctx(registry, cfg)
    apply(ctx, note(text="  Хранит ключ  "))
    assert journal(ctx)[0].text == "Хранит ключ"


def test_accepted_log_mentions_entity_name(registry, cfg):
    ctx = knowledge_ctx(registry, cfg)
    d = apply(ctx, note())
    assert any("Олдрик" in line for line in d.log)


def test_accepted_has_no_signal_or_tag(registry, cfg):
    ctx = knowledge_ctx(registry, cfg)
    d = apply(ctx, note())
    assert (d.signal_to_master, d.report_tag) == (None, None)


@pytest.mark.parametrize(
    "kind,ref",
    [
        ("npc", "aldric"), ("location", "forest"), ("faction", "guild"), ("god", "selune"),
        ("creature", "goblin_warrior"), ("situation", "plague_rumor"),
    ],
)
def test_every_kind_is_accepted(kind, ref, registry, cfg):
    ctx = knowledge_ctx(registry, cfg)
    assert apply(ctx, note(kind=kind, ref=ref)).status == "accepted"
    assert (journal(ctx)[0].kind, journal(ctx)[0].ref) == (kind, ref)


# Invalid

def invalid_code(ctx, request):
    d = apply(ctx, request)
    assert isinstance(d, Invalid)
    return d.code


def test_blank_text_is_empty_text(registry, cfg):
    ctx = knowledge_ctx(registry, cfg)
    assert invalid_code(ctx, note(text="   ")) == "empty_text"


def test_empty_string_is_empty_text(registry, cfg):
    ctx = knowledge_ctx(registry, cfg)
    assert invalid_code(ctx, note(text="")) == "empty_text"


@pytest.mark.parametrize(
    "kind", ["npc", "location", "faction", "god", "creature"],
)
def test_unknown_ref_for_each_kind(kind, registry, cfg):
    ctx = knowledge_ctx(registry, cfg)
    assert invalid_code(ctx, note(kind=kind, ref="nowhere_1")) == "unknown_ref"


def test_unknown_ref_lists_allowed_ids(registry, cfg):
    ctx = knowledge_ctx(registry, cfg)
    d = apply(ctx, note(kind="faction", ref="nowhere_1"))
    assert "guild" in d.message


def test_unknown_ref_lists_npc_ids(registry, cfg):
    ctx = knowledge_ctx(registry, cfg)
    d = apply(ctx, note(ref="nobody"))
    assert "aldric" in d.message


@pytest.mark.parametrize("ref", ["", "a", "Plague", "two words", "чума", "a" * 41, "a-b"])
def test_bad_situation_ref(ref, registry, cfg):
    ctx = knowledge_ctx(registry, cfg)
    assert invalid_code(ctx, note(kind="situation", ref=ref)) == "bad_ref"


@pytest.mark.parametrize("ref", ["ab", "a_1", "0_9", "a" * 40])
def test_good_situation_ref(ref, registry, cfg):
    ctx = knowledge_ctx(registry, cfg)
    assert apply(ctx, note(kind="situation", ref=ref)).status == "accepted"


def test_situation_ref_need_not_exist_in_world(registry, cfg):
    ctx = knowledge_ctx(registry, cfg)
    assert apply(ctx, note(kind="situation", ref="no_such_thing")).status == "accepted"


def test_told_without_from_ref(registry, cfg):
    ctx = knowledge_ctx(registry, cfg)
    assert invalid_code(ctx, note(source="told")) == "told_without_from"


def test_unknown_from_ref(registry, cfg):
    ctx = knowledge_ctx(registry, cfg)
    assert invalid_code(ctx, note(source="told", from_ref="ghost")) == "unknown_npc"


def test_unknown_from_ref_even_for_non_told(registry, cfg):
    ctx = knowledge_ctx(registry, cfg)
    assert invalid_code(ctx, note(source="rumor", from_ref="ghost")) == "unknown_npc"


def test_unknown_from_ref_lists_npc_ids(registry, cfg):
    ctx = knowledge_ctx(registry, cfg)
    d = apply(ctx, note(source="told", from_ref="ghost"))
    assert "grakh" in d.message


@pytest.mark.parametrize(
    "request_",
    [
        note(text=""), note(ref="nobody"), note(kind="situation", ref="X"), note(source="told"),
        note(source="told", from_ref="ghost"),
    ],
)
def test_invalid_changes_nothing(request_, registry, cfg):
    ctx = knowledge_ctx(registry, cfg)
    before = dump(ctx)
    assert isinstance(apply(ctx, request_), Invalid)
    assert dump(ctx) == before


def test_invalid_has_no_mark(registry, cfg):
    ctx = knowledge_ctx(registry, cfg)
    apply(ctx, note(ref="nobody"))
    assert ctx.marks == []


# обрезка

def test_long_text_is_clamped(registry, cfg):
    ctx = knowledge_ctx(registry, cfg)
    d = apply(ctx, note(text="слово " * 50))
    assert d.status == "clamped"
    assert d.report_tag == "text-shortened"
    assert d.signal_to_master


def test_long_text_is_cut_to_limit(registry, cfg):
    ctx = knowledge_ctx(registry, cfg)
    apply(ctx, note(text="слово " * 50))
    text = journal(ctx)[0].text
    assert len(text) <= KNOWLEDGE_TEXT_MAX
    assert text.endswith("…")


def test_clamped_tag_goes_to_marks(registry, cfg):
    ctx = knowledge_ctx(registry, cfg)
    apply(ctx, note(text="слово " * 50))
    assert ctx.marks == ["text-shortened"]


def test_text_at_limit_is_accepted_as_is(registry, cfg):
    ctx = knowledge_ctx(registry, cfg)
    text = "я" * KNOWLEDGE_TEXT_MAX
    d = apply(ctx, note(text=text))
    assert d.status == "accepted"
    assert journal(ctx)[0].text == text


def test_text_over_limit_by_one_is_clamped(registry, cfg):
    ctx = knowledge_ctx(registry, cfg)
    assert apply(ctx, note(text="я" * (KNOWLEDGE_TEXT_MAX + 1))).status == "clamped"


def test_limit_constant_is_160():
    assert KNOWLEDGE_TEXT_MAX == 160


# дубли и лимит

def test_duplicate_is_rejected(registry, cfg):
    ctx = knowledge_ctx(registry, cfg)
    apply(ctx, note())
    d = apply(ctx, note())
    assert isinstance(d, Decision)
    assert d.status == "rejected"
    assert d.signal_to_master
    assert len(journal(ctx)) == 1


def test_duplicate_has_no_report_tag(registry, cfg):
    ctx = knowledge_ctx(registry, cfg)
    apply(ctx, note())
    assert apply(ctx, note()).report_tag is None


def test_duplicate_ignores_case_and_spaces(registry, cfg):
    ctx = knowledge_ctx(registry, cfg)
    apply(ctx, note(text="Хранит  ключ"))
    assert apply(ctx, note(text="хранит ключ ")).status == "rejected"


def test_same_text_for_other_ref_is_not_duplicate(registry, cfg):
    ctx = knowledge_ctx(registry, cfg)
    apply(ctx, note(ref="aldric"))
    assert apply(ctx, note(ref="grakh")).status == "accepted"


def test_same_text_for_other_kind_with_same_ref_is_not_duplicate(registry, cfg):
    ctx = knowledge_ctx(registry, cfg)
    apply(ctx, note(kind="situation", ref="aldric"))
    assert apply(ctx, note(kind="npc", ref="aldric")).status == "accepted"


def test_sixth_note_evicts_the_oldest(registry, cfg):
    ctx = knowledge_ctx(registry, cfg)
    for i in range(6):
        ctx.bundle.world.clock.now_s = 100 + i
        apply(ctx, note(text=f"факт {i}"))
    assert [e.text for e in journal(ctx)] == [f"факт {i}" for i in range(1, 6)]


def test_limit_is_per_entity(registry, cfg):
    ctx = knowledge_ctx(registry, cfg)
    for i in range(5):
        apply(ctx, note(text=f"факт {i}"))
    apply(ctx, note(ref="grakh", text="другой"))
    assert len(journal(ctx)) == 6


def test_limit_follows_config(registry, cfg):
    ctx = knowledge_ctx(registry, cfg)
    one = cfg.knowledge.model_copy(update={"max_per_ref": 1})
    ctx.cfg = cfg.model_copy(update={"knowledge": one})
    apply(ctx, note(text="первое"))
    apply(ctx, note(text="второе"))
    assert [e.text for e in journal(ctx)] == ["второе"]


# спойлер

def test_hidden_secret_retold_is_rejected_as_spoiler(registry, cfg):
    ctx = knowledge_ctx(registry, cfg)
    d = apply(ctx, note(text=SECRET_TEXT))
    assert isinstance(d, Decision)
    assert d.status == "rejected"
    assert d.report_tag == "spoiler"
    assert d.signal_to_master


def test_spoiler_writes_nothing(registry, cfg):
    ctx = knowledge_ctx(registry, cfg)
    before = dump(ctx)
    apply(ctx, note(text=SECRET_TEXT))
    assert dump(ctx) == before


def test_spoiler_tag_goes_to_marks(registry, cfg):
    ctx = knowledge_ctx(registry, cfg)
    apply(ctx, note(text=SECRET_TEXT))
    assert ctx.marks == ["spoiler"]


def test_spoiler_check_covers_secrets_of_other_npcs(registry, cfg):
    ctx = knowledge_ctx(registry, cfg)
    assert apply(ctx, note(ref="grakh", text=SECRET_TEXT)).report_tag == "spoiler"


def test_close_retelling_is_spoiler(registry, cfg):
    ctx = knowledge_ctx(registry, cfg)
    d = apply(ctx, note(text="Сестра Олдрика прячется в склепе, обращена вампиром"))
    assert d.report_tag == "spoiler"


def test_unrelated_text_is_not_spoiler(registry, cfg):
    ctx = knowledge_ctx(registry, cfg)
    assert apply(ctx, note(text="Любит эль и кости")).status == "accepted"


def test_revealed_secret_may_be_noted(registry, cfg):
    ctx = knowledge_ctx(registry, cfg)
    secret = ctx.bundle.world.npcs["aldric"].secrets[0]
    secret.revealed = True
    assert apply(ctx, note(text=SECRET_TEXT)).status == "accepted"


def test_secret_known_to_player_may_be_noted(registry, cfg):
    ctx = knowledge_ctx(registry, cfg)
    ctx.bundle.world.npcs["aldric"].known_to_player.append("sister")
    assert apply(ctx, note(text=SECRET_TEXT)).status == "accepted"


# scene_mood

def mood(value):
    return req("scene_mood", mood=value)


def test_scene_mood_romance_sets_scene(registry, cfg):
    ctx = knowledge_ctx(registry, cfg)
    d = apply(ctx, mood("romance"))
    assert isinstance(d, Decision)
    assert d.status == "accepted"
    assert ctx.scene.scene_mood == "romance"


def test_scene_mood_none_clears_scene(registry, cfg):
    ctx = knowledge_ctx(registry, cfg)
    apply(ctx, mood("romance"))
    d = apply(ctx, mood("none"))
    assert d.status == "accepted"
    assert ctx.scene.scene_mood == ""


def test_scene_mood_none_without_mood_stays_empty(registry, cfg):
    ctx = knowledge_ctx(registry, cfg)
    apply(ctx, mood("none"))
    assert ctx.scene.scene_mood == ""


def test_scene_mood_romance_again_is_accepted(registry, cfg):
    ctx = knowledge_ctx(registry, cfg)
    apply(ctx, mood("romance"))
    assert apply(ctx, mood("romance")).status == "accepted"
    assert ctx.scene.scene_mood == "romance"


def test_scene_mood_log_differs_for_set_and_clear(registry, cfg):
    ctx = knowledge_ctx(registry, cfg)
    on = apply(ctx, mood("romance")).log
    off = apply(ctx, mood("none")).log
    assert on and off
    assert on != off
    assert "none" not in off[0]


def test_scene_mood_without_scene_is_invalid(registry, cfg):
    ctx = knowledge_ctx(registry, cfg, with_scene=False)
    d = apply(ctx, mood("romance"))
    assert isinstance(d, Invalid)
    assert d.code == "no_scene"


def test_scene_mood_without_scene_changes_nothing(registry, cfg):
    ctx = knowledge_ctx(registry, cfg, with_scene=False)
    before = dump(ctx)
    apply(ctx, mood("none"))
    assert dump(ctx) == before


def test_scene_mood_unknown_value_is_rejected_by_parser():
    with pytest.raises(ValueError):
        req("scene_mood", mood="horror")


def test_new_scene_has_no_mood():
    from ai_dm.state.scene import SceneState

    assert SceneState(id="s2", started_at_s=0, location_id="vale").scene_mood == ""


# reveal_secret пишет журнал

def reveal(ctx):
    return apply(ctx, req("reveal_secret", npc_id="aldric", secret_id="sister"))


def test_reveal_secret_writes_journal(registry, cfg):
    ctx = knowledge_ctx(registry, cfg)
    ctx.bundle.world.flags["found"] = True
    reveal(ctx)
    [entry] = journal(ctx)
    assert (entry.kind, entry.ref, entry.text) == ("npc", "aldric", SECRET_TEXT)
    assert (entry.source, entry.at_s) == ("deduced", 500)


def test_reveal_secret_too_early_writes_nothing(registry, cfg):
    ctx = knowledge_ctx(registry, cfg)
    assert reveal(ctx).status == "rejected"
    assert journal(ctx) == []


def test_unknown_secret_writes_nothing(registry, cfg):
    ctx = knowledge_ctx(registry, cfg)
    apply(ctx, req("reveal_secret", npc_id="aldric", secret_id="nothing"))
    assert journal(ctx) == []


def test_revealed_secret_may_then_be_noted_by_narrator_but_not_twice(registry, cfg):
    ctx = knowledge_ctx(registry, cfg)
    ctx.bundle.world.flags["found"] = True
    reveal(ctx)
    assert apply(ctx, note(text=SECRET_TEXT)).status == "rejected"


# favor_change героя пишет журнал

def favor(delta, reason="помог жрецу", target="hero", god="selune"):
    return req("favor_change", target=target, god_id=god, delta=delta, reason=reason)


def test_favor_change_writes_god_entry(registry, cfg):
    ctx = knowledge_ctx(registry, cfg)
    apply(ctx, favor(1))
    [entry] = journal(ctx)
    assert (entry.kind, entry.ref, entry.source, entry.at_s) == ("god", "selune", "deduced", 500)


def test_favor_entry_names_god_and_reason(registry, cfg):
    ctx = knowledge_ctx(registry, cfg)
    apply(ctx, favor(1, reason="помог жрецу"))
    text = journal(ctx)[0].text
    assert text.startswith("Селунэ: ")
    assert "помог жрецу" in text


def test_clamped_favor_change_still_writes(registry, cfg):
    ctx = knowledge_ctx(registry, cfg)
    assert apply(ctx, favor(5)).status == "clamped"
    assert len(journal(ctx)) == 1


def test_unknown_god_writes_nothing(registry, cfg):
    ctx = knowledge_ctx(registry, cfg)
    assert isinstance(apply(ctx, favor(1, god="nobody")), Invalid)
    assert journal(ctx) == []


def test_frozen_god_rejected_writes_nothing(registry, cfg):
    ctx = knowledge_ctx(registry, cfg)
    ctx.hero.divine.frozen.append("selune")
    assert apply(ctx, favor(1)).status == "rejected"
    assert journal(ctx) == []


# тексты ответов рассказчику (мутанты Ж3)

def test_bad_situation_ref_message(registry, cfg):
    ctx = knowledge_ctx(registry, cfg)
    d = apply(ctx, note(kind="situation", ref="X"))
    assert d.message == "ref ситуации: слаг латиницей a-z, 0-9, _ (2-40 знаков)"


def test_told_without_from_message(registry, cfg):
    ctx = knowledge_ctx(registry, cfg)
    assert apply(ctx, note(source="told")).message == "source told: нужен from_ref (id NPC)"


def test_empty_text_message(registry, cfg):
    ctx = knowledge_ctx(registry, cfg)
    assert apply(ctx, note(text="")).message == "текст заметки пуст"


def test_no_scene_message(registry, cfg):
    ctx = knowledge_ctx(registry, cfg, with_scene=False)
    d = apply(ctx, mood("romance"))
    assert d.message == "настроение ставится в сцене, а сцены сейчас нет"


def test_duplicate_reason_and_signal(registry, cfg):
    ctx = knowledge_ctx(registry, cfg)
    apply(ctx, note())
    d = apply(ctx, note())
    assert d.reason == "уже записано"
    assert d.signal_to_master == "В журнале знаний это уже есть: не записывай повторно."


def test_spoiler_reason_and_signal(registry, cfg):
    ctx = knowledge_ctx(registry, cfg)
    d = apply(ctx, note(text=SECRET_TEXT))
    assert d.reason == "секрет ещё не раскрыт"
    assert d.signal_to_master == (
        "Секрет ещё не раскрыт: в журнал его не записать. Раскрой его через reveal_secret, "
        "когда условие выполнено."
    )


def test_clamped_reason_names_the_limit(registry, cfg):
    ctx = knowledge_ctx(registry, cfg)
    d = apply(ctx, note(text="слово " * 50))
    assert d.reason == f"текст укорочен до {KNOWLEDGE_TEXT_MAX}"
    assert d.signal_to_master == f"Журнал знаний: текст укорочен до {KNOWLEDGE_TEXT_MAX} знаков."


def test_clamped_log_mentions_the_limit(registry, cfg):
    ctx = knowledge_ctx(registry, cfg)
    d = apply(ctx, note(text="слово " * 50))
    assert d.log[-1] == f"Журнал: текст укорочен до {KNOWLEDGE_TEXT_MAX}"


def test_scene_mood_logs_are_exact(registry, cfg):
    ctx = knowledge_ctx(registry, cfg)
    assert apply(ctx, mood("romance")).log == ["Настроение сцены: romance"]
    assert apply(ctx, mood("none")).log == ["Настроение сцены снято"]
