# Этап 5, P6: ui.session.turn_events(app, reply, level_before) -> события хода для рисунков:
# "death" (герой умер или меню hero_dead), "victory" (исход боя), "level_up" (уровень вырос).
from types import SimpleNamespace

from ai_dm.ui import session


def make(level=3, pending=None):
    return SimpleNamespace(pending=pending, bundle=SimpleNamespace(level=level))


def reply(**turn):
    base = {"hero_dead": False, "combat_outcome": None}
    return SimpleNamespace(turn=SimpleNamespace(**{**base, **turn}))


def events(app, rep, before=3):
    return session.turn_events(app, rep, before)


def setup(monkeypatch):
    def hero(bundle):
        return SimpleNamespace(sheet=SimpleNamespace(level=bundle.level))

    monkeypatch.setattr(session, "hero_of", hero)


def test_quiet_turn_has_no_events(monkeypatch):
    setup(monkeypatch)
    assert events(make(), reply()) == []


def test_reply_without_turn_has_no_events(monkeypatch):
    setup(monkeypatch)
    assert events(make(), SimpleNamespace(turn=None)) == []


def test_hero_dead_turn_gives_death(monkeypatch):
    setup(monkeypatch)
    assert events(make(), reply(hero_dead=True)) == ["death"]


def test_pending_hero_dead_gives_death_even_without_turn(monkeypatch):
    setup(monkeypatch)
    assert events(make(pending="hero_dead"), SimpleNamespace(turn=None)) == ["death"]


def test_other_pending_gives_no_death(monkeypatch):
    setup(monkeypatch)
    assert events(make(pending="level_choice"), reply()) == []


def test_victory_outcome_gives_victory(monkeypatch):
    setup(monkeypatch)
    assert events(make(), reply(combat_outcome="victory")) == ["victory"]


def test_other_outcome_gives_no_victory(monkeypatch):
    setup(monkeypatch)
    assert events(make(), reply(combat_outcome="fled")) == []


def test_level_growth_gives_level_up(monkeypatch):
    setup(monkeypatch)
    assert events(make(level=4), reply(), before=3) == ["level_up"]


def test_same_level_gives_no_level_up(monkeypatch):
    setup(monkeypatch)
    assert events(make(level=3), reply(), before=3) == []


def test_level_up_works_without_turn(monkeypatch):
    setup(monkeypatch)
    assert events(make(level=4), SimpleNamespace(turn=None), before=3) == ["level_up"]


def test_all_events_come_in_order_death_victory_level_up(monkeypatch):
    setup(monkeypatch)
    rep = reply(hero_dead=True, combat_outcome="victory")
    assert events(make(level=4), rep, before=3) == ["death", "victory", "level_up"]
