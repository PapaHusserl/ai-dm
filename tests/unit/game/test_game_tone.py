# Ожидаемый API (П6б этапа 3, STAGE3-PLAN A9, ТЗ 3): команда /tone через GameApp.handle.
#   /tone -- показать все шкалы (mood, violence, horror, romance, language, hard_limits,
#     soft_limits);
#   /tone <шкала> <значение> -- изменить (значение из списка шкалы; mood -- свободный текст):
#     пишет world.tone, запись хроники kind "tone" (текст содержит шкалу и новое значение)
#     и автосейв;
#     значение вне шкалы / неизвестная шкала -> текст ошибки, состояние не меняется;
#   /tone hard_limits +<x> -- добавить без подтверждения; /tone hard_limits -<x> -- ослабление:
#     не применяется сразу, app.pending == "tone_confirm", меню ["да", "нет"] (app.choose);
#     "да" -> снято, хроника, автосейв; "нет" -> без изменений; pending сбрасывается.
#   Тон входит в system[1] промпта нарратора: после смены новый ход видит новое значение.
import pytest
from game_kit import ReactiveAdapter, make_app
from protocol_kit import make_bundle

from ai_dm.persistence.store import load_slot


def text_of(reply):
    return "\n".join(reply.lines)


def tone_app(registry, tmp_path, **tone):
    bundle = make_bundle(registry)
    for name, value in tone.items():
        setattr(bundle.world.tone, name, value)
    adapter = ReactiveAdapter()
    return make_app(registry, tmp_path, adapter, bundle=bundle), adapter


def tone_entries(app):
    return [e for e in app.bundle.chronicle.entries if e.kind == "tone"]


def test_tone_is_no_longer_a_stub(registry, tmp_path):
    app, _ = tone_app(registry, tmp_path)
    assert "этап" not in text_of(app.handle("/tone"))


def test_tone_shows_all_scales(registry, tmp_path):
    app, _ = tone_app(
        registry, tmp_path, mood="мрачное", violence="жестоко", horror="умеренно",
        romance="чувственно", language="сдержанно", hard_limits=["насилие над детьми"],
        soft_limits=["пытки"],
    )
    text = text_of(app.handle("/tone"))
    words = [
        "мрачное", "жестоко", "умеренно", "чувственно", "сдержанно", "насилие над детьми", "пытки",
    ]
    for word in words:
        assert word in text
    scales = ["mood", "violence", "horror", "romance", "language", "hard_limits", "soft_limits"]
    for scale in scales:
        assert scale in text


def test_tone_show_changes_nothing(registry, tmp_path):
    app, _ = tone_app(registry, tmp_path)
    before = app.bundle.model_dump_json()
    app.handle("/tone")
    assert app.bundle.model_dump_json() == before


def test_tone_changes_violence(registry, tmp_path):
    app, _ = tone_app(registry, tmp_path, violence="реалистично")
    app.handle("/tone violence жестоко")
    assert app.bundle.world.tone.violence == "жестоко"


def test_tone_change_writes_chronicle_entry(registry, tmp_path):
    app, _ = tone_app(registry, tmp_path, violence="реалистично")
    app.handle("/tone violence жестоко")
    entries = tone_entries(app)
    assert len(entries) == 1
    assert "violence" in entries[0].text
    assert "жестоко" in entries[0].text


def test_tone_change_autosaves(registry, tmp_path):
    app, _ = tone_app(registry, tmp_path, violence="реалистично")
    app.handle("/tone violence жестоко")
    saved = load_slot(tmp_path, "w1", "auto")
    assert saved.world.tone.violence == "жестоко"
    assert [e.kind for e in saved.chronicle.entries].count("tone") == 1


def test_tone_mood_is_free_text(registry, tmp_path):
    app, _ = tone_app(registry, tmp_path)
    app.handle("/tone mood тёмная сказка с юмором")
    assert app.bundle.world.tone.mood == "тёмная сказка с юмором"


def test_tone_value_outside_scale_is_error(registry, tmp_path):
    app, _ = tone_app(registry, tmp_path, violence="реалистично")
    before = app.bundle.model_dump_json()
    reply = app.handle("/tone violence ужасно")
    assert app.bundle.world.tone.violence == "реалистично"
    assert app.bundle.model_dump_json() == before
    assert reply.lines


def test_tone_error_lists_allowed_values(registry, tmp_path):
    app, _ = tone_app(registry, tmp_path)
    text = text_of(app.handle("/tone violence ужасно"))
    for value in ("мягко", "реалистично", "жестоко"):
        assert value in text


def test_tone_unknown_scale_is_error(registry, tmp_path):
    app, _ = tone_app(registry, tmp_path)
    before = app.bundle.model_dump_json()
    reply = app.handle("/tone weather дождь")
    assert reply.lines
    assert app.bundle.model_dump_json() == before


def test_tone_scale_without_value_is_error(registry, tmp_path):
    app, _ = tone_app(registry, tmp_path)
    before = app.bundle.model_dump_json()
    app.handle("/tone violence")
    assert app.bundle.model_dump_json() == before


def test_tone_error_writes_no_chronicle(registry, tmp_path):
    app, _ = tone_app(registry, tmp_path)
    app.handle("/tone violence ужасно")
    assert tone_entries(app) == []


def test_tone_other_scales_change(registry, tmp_path):
    app, _ = tone_app(registry, tmp_path)
    app.handle("/tone horror сильно")
    app.handle("/tone romance намёки")
    app.handle("/tone language грубо")
    tone = app.bundle.world.tone
    assert (tone.horror, tone.romance, tone.language) == ("сильно", "намёки", "грубо")
    assert len(tone_entries(app)) == 3


# hard_limits

def test_hard_limits_add_needs_no_confirmation(registry, tmp_path):
    app, _ = tone_app(registry, tmp_path, hard_limits=["насилие над детьми"])
    reply = app.handle("/tone hard_limits +пытки")
    assert app.bundle.world.tone.hard_limits == ["насилие над детьми", "пытки"]
    assert reply.pending is None
    assert len(tone_entries(app)) == 1


def test_hard_limits_removal_waits_for_confirmation(registry, tmp_path):
    app, _ = tone_app(registry, tmp_path, hard_limits=["насилие над детьми"])
    reply = app.handle("/tone hard_limits -насилие над детьми")
    assert app.bundle.world.tone.hard_limits == ["насилие над детьми"]
    assert tone_entries(app) == []
    assert reply.pending == "tone_confirm"
    assert reply.menu == ["да", "нет"]


def test_hard_limits_removal_confirmed(registry, tmp_path):
    app, _ = tone_app(registry, tmp_path, hard_limits=["насилие над детьми", "пытки"])
    app.handle("/tone hard_limits -пытки")
    reply = app.choose("да")
    assert app.bundle.world.tone.hard_limits == ["насилие над детьми"]
    assert app.pending is None
    assert reply.pending is None
    assert len(tone_entries(app)) == 1
    assert "пытки" in tone_entries(app)[0].text


def test_hard_limits_removal_confirmed_autosaves(registry, tmp_path):
    app, _ = tone_app(registry, tmp_path, hard_limits=["пытки"])
    app.handle("/tone hard_limits -пытки")
    app.choose("да")
    assert load_slot(tmp_path, "w1", "auto").world.tone.hard_limits == []


def test_hard_limits_removal_declined(registry, tmp_path):
    app, _ = tone_app(registry, tmp_path, hard_limits=["пытки"])
    app.handle("/tone hard_limits -пытки")
    app.choose("нет")
    assert app.bundle.world.tone.hard_limits == ["пытки"]
    assert app.pending is None
    assert tone_entries(app) == []


def test_hard_limits_removal_of_missing_item_is_error(registry, tmp_path):
    app, _ = tone_app(registry, tmp_path, hard_limits=["пытки"])
    reply = app.handle("/tone hard_limits -яд")
    assert app.pending is None
    assert app.bundle.world.tone.hard_limits == ["пытки"]
    assert reply.lines


def test_soft_limits_removal_needs_no_confirmation(registry, tmp_path):
    app, _ = tone_app(registry, tmp_path, soft_limits=["пытки"])
    app.handle("/tone soft_limits -пытки")
    assert app.bundle.world.tone.soft_limits == []
    assert app.pending is None


# промпт

def tone_in_system(adapter):
    block = adapter.requests[-1].system[1]
    return getattr(block, "text", None) or str(block)


def test_next_turn_prompt_has_new_tone(registry, tmp_path):
    app, adapter = tone_app(registry, tmp_path, violence="мягко")
    app.handle("/tone violence жестоко")
    app.handle("осматриваюсь")
    assert "жестоко" in tone_in_system(adapter)
    assert "мягко" not in tone_in_system(adapter)


# Б0-П0: романтика 1-4

@pytest.mark.parametrize("value", ["чувственно", "откровенно"])
def test_tone_romance_accepts_new_values(registry, tmp_path, value):
    app, _ = tone_app(registry, tmp_path)
    app.handle(f"/tone romance {value}")
    assert app.bundle.world.tone.romance == value


def test_tone_romance_old_value_yes_is_error_with_list(registry, tmp_path):
    app, _ = tone_app(registry, tmp_path)
    text = text_of(app.handle("/tone romance есть"))
    assert app.bundle.world.tone.romance == ""
    for value in ("нет", "намёки", "чувственно", "откровенно"):
        assert value in text
    assert tone_entries(app) == []


def test_tone_show_has_new_romance_value(registry, tmp_path):
    app, _ = tone_app(registry, tmp_path, romance="откровенно")
    assert "откровенно" in text_of(app.handle("/tone"))
