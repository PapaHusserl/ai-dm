# К3 П2 (docs/plan-k3.md, «Тесты» П2 «ритуал», правка по ревью «ритуал bad_circle»):
#   cast_problem(hero, spell, circle, free, registry, checks, ritual=True) -> ritual_problem:
#   * не ритуал (Spell.ritual = false) -> not_ritual;
#   * подготовленное с пометкой «ритуал» -- можно всем классам; неподготовленное -- только из книги
#     волшебника (Адепт ритуалов), у жреца -> not_prepared;
#   * ритуал только базовым кругом заклинания: другой круг -> bad_circle (отступление кабана П2,
#     «Умолчания» читали circle = spell.level как присвоение; принято папой);
#   * отлучение жреца (forbidden-проверка) и здесь закрывает заклинание.
#   В бою ритуал и 10-минутное применение не предлагаются -- test_actions_cast.py.
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "content"))

from test_builder import wizard_choices  # noqa: E402
from test_class_kits import minimal_choices  # noqa: E402

from ai_dm.rules.builder import build_character  # noqa: E402
from ai_dm.rules.cast_checks import CastCheck, default_cast_check_registry  # noqa: E402
from ai_dm.rules.spellcasting import cast_problem  # noqa: E402

CHECKS = default_cast_check_registry()
BOOK = ["alarm", "magic_missile", "detect_magic"]


def wizard(registry, prepared=("magic_missile",)):
    hero = build_character(wizard_choices(spells=BOOK, prepared=list(prepared)), registry)
    return hero


def cleric(registry, prepared=()):
    hero = build_character(minimal_choices("cleric", "a"), registry)
    hero.sheet.prepared_of()[:] = list(prepared)
    return hero


def ritual(hero, registry, spell_id, circle=None):
    spell = registry.get("spell", spell_id)
    return cast_problem(
        hero, spell, spell.level if circle is None else circle, False, registry, CHECKS,
        ritual=True,
    )


def code(problem):
    return None if problem is None else problem[0]


class Forbidding:
    # проверка заклинания «запрещено»: как отлучение жреца
    def check(self, hero, spell_id, registry):
        return [CastCheck(kind="forbidden", reason="отлучение")]


def test_wizard_casts_a_book_ritual_without_preparing_it(registry):
    hero = wizard(registry)
    assert "alarm" not in hero.sheet.prepared_of()
    assert ritual(hero, registry, "alarm") is None


def test_wizard_casts_a_prepared_ritual(registry):
    assert ritual(wizard(registry, ["detect_magic"]), registry, "detect_magic") is None


def test_ritual_spell_outside_the_book_and_not_prepared_is_not_prepared(registry):
    hero = wizard(registry)
    assert code(ritual(hero, registry, "identify")) == "not_prepared"


def test_cleric_cannot_cast_an_unprepared_ritual(registry):
    hero = cleric(registry)
    assert code(ritual(hero, registry, "detect_magic")) == "not_prepared"


def test_cleric_casts_a_prepared_ritual(registry):
    hero = cleric(registry, ["detect_magic"])
    assert ritual(hero, registry, "detect_magic") is None


def test_non_ritual_spell_is_not_ritual(registry):
    hero = wizard(registry)
    assert code(ritual(hero, registry, "magic_missile")) == "not_ritual"


def test_cantrip_is_not_ritual(registry):
    assert code(ritual(wizard(registry), registry, "fire_bolt")) == "not_ritual"


def test_ritual_with_a_higher_circle_is_bad_circle(registry):
    hero = wizard(registry)
    assert code(ritual(hero, registry, "alarm", circle=2)) == "bad_circle"


def test_ritual_with_a_lower_circle_is_bad_circle(registry):
    hero = wizard(registry, ["detect_magic"])
    assert code(ritual(hero, registry, "detect_magic", circle=0)) == "bad_circle"


def test_ritual_does_not_need_a_slot(registry):
    hero = wizard(registry)
    hero.creature.resources["spell_slot:1"].current = 0
    assert ritual(hero, registry, "alarm") is None


def test_forbidden_check_blocks_the_ritual_too(registry):
    hero = cleric(registry, ["detect_magic"])
    spell = registry.get("spell", "detect_magic")
    problem = cast_problem(hero, spell, 1, False, registry, Forbidding(), ritual=True)
    assert code(problem) == "forbidden"


def test_ritual_asks_the_cast_checks_about_this_hero_and_spell(registry):
    calls = []

    class Recording:
        def check(self, hero, spell_id, reg):
            calls.append((hero, spell_id, reg))
            return []

    hero = wizard(registry)
    spell = registry.get("spell", "alarm")
    assert cast_problem(hero, spell, 1, False, registry, Recording(), ritual=True) is None
    assert len(calls) == 1
    assert calls[0][0] is hero
    assert calls[0][1] == "alarm"
    assert calls[0][2] is registry


def test_same_spell_without_ritual_still_needs_preparation(registry):
    hero = wizard(registry)
    spell = registry.get("spell", "alarm")
    assert code(cast_problem(hero, spell, 1, False, registry, CHECKS)) == "not_prepared"
