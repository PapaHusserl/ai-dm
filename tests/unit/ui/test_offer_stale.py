# AD1, W3 + Q3: цифра подставляет вариант из offered_choices только если последний ход рассказчика
# сам вызвал offer_choices (иначе список устарел: game его не сбрасывает). Одинаково в простом
# режиме и в PlaySession (TUI берёт ту же ai_dm.ui.session.offer_is_stale).
from ui_kit import play, text_app, text_step

from ai_dm.game.scene import hero_of
from ai_dm.state.scene import TurnRecord

OFFER = {
    "tool_calls": [
        {"id": "c1", "name": "offer_choices",
         "input": {"type": "offer_choices", "choices": ["Спросить про подвал", "Заказать эль"]}},
    ]
}


def make_session(app):
    from ai_dm.ui.session import PlaySession

    return PlaySession(app)


def last_input(app):
    return app.bundle.memory.recent_turns[-1].player_input


def record(requests):
    return TurnRecord(turn_seq=1, at_s=0, player_input="x", narration="y", requests=requests)


# offer_is_stale

def test_offer_is_stale_without_turns(registry, tmp_path):
    from ai_dm.ui.session import offer_is_stale

    app = text_app(registry, tmp_path, [text_step()])
    assert offer_is_stale(app) is True


def test_offer_is_fresh_when_last_turn_offered(registry, tmp_path):
    from ai_dm.ui.session import offer_is_stale

    app = text_app(registry, tmp_path, [text_step()])
    app.bundle.memory.recent_turns.append(record(["offer_choices"]))
    assert offer_is_stale(app) is False


def test_offer_is_stale_when_last_turn_did_not_offer(registry, tmp_path):
    from ai_dm.ui.session import offer_is_stale

    app = text_app(registry, tmp_path, [text_step()])
    app.bundle.memory.recent_turns.append(record(["offer_choices"]))
    app.bundle.memory.recent_turns.append(record(["skill_check"]))
    assert offer_is_stale(app) is True


def test_offer_is_not_stale_while_menu_is_pending(registry, tmp_path):
    from ai_dm.ui.session import offer_is_stale

    app = text_app(registry, tmp_path, [text_step()])
    app.pending = "hero_dead"
    assert offer_is_stale(app) is False


# PlaySession

def test_fresh_offer_digit_picks_variant(registry, tmp_path):
    app = text_app(registry, tmp_path, [OFFER, text_step("Рассказ."), text_step()])
    session = make_session(app)
    session.submit("Иду")
    session.submit("2")
    assert last_input(app) == "Заказать эль"


def test_stale_offer_digit_goes_as_text(registry, tmp_path):
    app = text_app(registry, tmp_path, [OFFER, text_step("Рассказ."), text_step(), text_step()])
    session = make_session(app)
    session.submit("Иду")
    session.submit("Просто иду дальше")
    assert app.bundle.session.offered_choices
    session.submit("1")
    assert last_input(app) == "1"


def test_stale_offer_digit_goes_as_text_in_simple_mode(registry, tmp_path):
    app = text_app(registry, tmp_path, [OFFER, text_step("Рассказ."), text_step(), text_step()])
    play(app, ["Иду", "Просто иду дальше", "1"])
    assert last_input(app) == "1"


def test_fresh_offer_digit_picks_variant_in_simple_mode(registry, tmp_path):
    app = text_app(registry, tmp_path, [OFFER, text_step("Рассказ."), text_step()])
    play(app, ["Иду", "1"])
    assert last_input(app) == "Спросить про подвал"


def test_stale_offer_from_loaded_state_goes_as_text(registry, tmp_path):
    app = text_app(registry, tmp_path, [text_step()])
    app.bundle.session.offered_choices = ["Старый вариант"]
    make_session(app).submit("1")
    assert last_input(app) == "1"


def test_stale_offer_does_not_change_hero(registry, tmp_path):
    app = text_app(registry, tmp_path, [text_step()])
    level = hero_of(app.bundle).sheet.level
    app.bundle.session.offered_choices = ["Старый вариант"]
    make_session(app).submit("1")
    assert hero_of(app.bundle).sheet.level == level
