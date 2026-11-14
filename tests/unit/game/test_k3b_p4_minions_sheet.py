# К3б П4, решение 39 (docs/plan-k3b.md): /sheet показывает призванных героя строкой
#   «Призванные: Скелет (HP N/M, до HH:MM); Ястреб (HP N/M)» -- имя из данных монстра, HP текущие/
#   максимум, «до HH:MM» только у существа со сроком (until_s), как «до ...» у эффектов; истёкшие
#   (until_s <= часы мира) не показываются; нет призванных -- нет строки; общей строки срока
#   заклинания в «Эффекты:» («Оживление мёртвых (до ...)») нет.
import pytest
from game_kit import ReactiveAdapter, make_app

from ai_dm.game.scene import hero_of
from ai_dm.game.sheet_text import until_text
from ai_dm.state.hero import Minion

HOUR = 3600


@pytest.fixture
def app(registry, tmp_path):
    return make_app(registry, tmp_path, ReactiveAdapter())


def now(app):
    return app.bundle.world.clock.now_s


def give(app, *minions):
    hero_of(app.bundle).minions = list(minions)


def skeleton(until_s, hp=5):
    return Minion(monster_id="skeleton", spell_id="animate_dead", hp_current=hp, until_s=until_s)


def hawk(hp=1):
    return Minion(monster_id="hawk", spell_id="find_familiar", hp_current=hp, until_s=None)


def summoned_rows(app):
    return [line for line in app.handle("/sheet").lines if line.startswith("Призванные")]


def test_sheet_without_minions_has_no_summoned_row(app):
    assert summoned_rows(app) == []


def test_sheet_shows_skeleton_and_hawk_in_one_row(app):
    until = now(app) + HOUR
    give(app, skeleton(until), hawk())
    expected = f"Призванные: Скелет (HP 5/13, {until_text(until, now(app))}); Ястреб (HP 1/1)"
    assert summoned_rows(app) == [expected]


def test_sheet_hawk_has_no_time(app):
    give(app, hawk())
    assert summoned_rows(app) == ["Призванные: Ястреб (HP 1/1)"]


def test_sheet_hides_an_expired_minion(app):
    give(app, skeleton(now(app) - 1), hawk())
    assert summoned_rows(app) == ["Призванные: Ястреб (HP 1/1)"]


def test_sheet_without_live_minions_has_no_row(app):
    give(app, skeleton(now(app)))
    assert summoned_rows(app) == []


def test_sheet_effects_row_does_not_name_the_conjure_spell(app):
    give(app, skeleton(now(app) + HOUR))
    rows = [line for line in app.handle("/sheet").lines if line.startswith("Эффекты")]
    assert not [line for line in rows if "Оживление мёртвых" in line]
