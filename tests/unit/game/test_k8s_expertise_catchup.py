# К8с П1: догон экспертизы при старте и /load (docs/plan-k8s.md, решение 4, Р-К8с-2 = а).
# Ожидание: если pending_level нет и недобор expertise_total - len(skill_expertise) > 0, то
# app.pending == "expertise", menu_for -- освоенные навыки без экспертизы; выбор пишется сразу
# в sheet.skill_expertise (choose(навык)); когда недобора нет -- pending None; ход текстом
# при pending -- «Сначала нужно сделать выбор в меню.»; в сейв pending не пишется.
# Следопыт: Ловкий исследователь (2 ур.) -- 1 навык, Экспертиза (9 ур.) -- ещё 2.
from game_kit import ReactiveAdapter, make_app
from protocol_kit import make_bundle
from ranger_kit import make_class_hero, ranger_at

from ai_dm.persistence.store import save_slot
from ai_dm.state.hero import LevelChoices, PendingLevel

SAVED_AT = "2026-01-01T12:00:00Z"


def ranger_bundle(registry, level=11, expertise=("survival",)):
    bundle = make_bundle(registry)
    hero = ranger_at(registry, level)
    hero.location_id = bundle.heroes[0].location_id
    hero.sheet.skill_expertise = list(expertise)
    bundle.heroes[0] = hero
    return bundle


def loaded(registry, tmp_path, bundle):
    # игра стартует на чистом герое, затем /load слота с нужным бандлом
    save_slot(tmp_path, bundle, "manual-k8s", saved_at=SAVED_AT)
    app = make_app(registry, tmp_path, ReactiveAdapter())
    reply = app.handle("/load k8s")
    return app, reply


def expertise(app):
    return app.bundle.heroes[0].sheet.skill_expertise


def test_load_of_ranger_11_with_one_expertise_asks_for_choice(registry, tmp_path):
    app, _ = loaded(registry, tmp_path, ranger_bundle(registry))
    assert app.pending == "expertise"


def test_expertise_menu_has_proficient_skills_without_survival(registry, tmp_path):
    app, _ = loaded(registry, tmp_path, ranger_bundle(registry))
    menu = app.menu_for("expertise")
    assert "stealth" in menu
    assert "survival" not in menu


def test_expertise_menu_has_only_proficient_skills(registry, tmp_path):
    bundle = ranger_bundle(registry)
    app, _ = loaded(registry, tmp_path, bundle)
    assert set(app.menu_for("expertise")) <= set(bundle.heroes[0].sheet.skill_proficiencies)


def test_load_announces_expertise_choice(registry, tmp_path):
    _, reply = loaded(registry, tmp_path, ranger_bundle(registry))
    assert "Экспертиза: выберите навык для экспертизы." in reply.lines


def test_text_turn_is_refused_while_expertise_is_pending(registry, tmp_path):
    app, _ = loaded(registry, tmp_path, ranger_bundle(registry))
    reply = app.handle("Осматриваюсь")
    assert reply.lines == ["Сначала нужно сделать выбор в меню."]


def test_two_choices_complete_expertise(registry, tmp_path):
    app, _ = loaded(registry, tmp_path, ranger_bundle(registry))
    app.choose("stealth")
    app.choose(app.menu_for("expertise")[0])
    assert len(expertise(app)) == 3
    assert app.pending is None


def test_first_choice_is_written_to_the_sheet_at_once(registry, tmp_path):
    app, _ = loaded(registry, tmp_path, ranger_bundle(registry))
    app.choose("stealth")
    assert expertise(app) == ["survival", "stealth"]
    assert app.pending == "expertise"


def test_last_choice_reports_the_result(registry, tmp_path):
    app, _ = loaded(registry, tmp_path, ranger_bundle(registry))
    app.choose("stealth")
    reply = app.choose("perception")
    assert any(line.startswith("Экспертиза: ") for line in reply.lines)


def test_first_choice_reply_asks_for_the_next_one(registry, tmp_path):
    app, _ = loaded(registry, tmp_path, ranger_bundle(registry))
    reply = app.choose("stealth")
    assert reply.lines == ["Выберите: навык для экспертизы."]


def test_last_choice_reply_lists_all_picks(registry, tmp_path):
    app, _ = loaded(registry, tmp_path, ranger_bundle(registry))
    app.choose("stealth")
    reply = app.choose("perception")
    assert reply.lines == ["Экспертиза: Скрытность, Восприятие."]


def test_save_after_first_choice_and_load_asks_for_one_more(registry, tmp_path):
    app, _ = loaded(registry, tmp_path, ranger_bundle(registry))
    app.choose("stealth")
    save_slot(tmp_path, app.bundle, "manual-half", saved_at=SAVED_AT)
    other = make_app(registry, tmp_path, ReactiveAdapter())
    other.handle("/load half")
    assert other.pending == "expertise"
    other.choose(other.menu_for("expertise")[0])
    assert (len(expertise(other)), other.pending) == (3, None)


def test_hero_with_pending_level_gets_level_menu_first(registry, tmp_path):
    bundle = ranger_bundle(registry)
    bundle.heroes[0].pending_level = PendingLevel(
        class_id="ranger", hp_gain=5, draft=LevelChoices(level=12)
    )
    app, _ = loaded(registry, tmp_path, bundle)
    assert app.pending == "level_up"


def test_dead_hero_gets_hero_dead_not_expertise(registry, tmp_path):
    bundle = ranger_bundle(registry)
    bundle.heroes[0].status = "dead"
    app, _ = loaded(registry, tmp_path, bundle)
    assert app.pending == "hero_dead"


def test_ranger_8_gets_no_expertise_menu(registry, tmp_path):
    app, _ = loaded(registry, tmp_path, ranger_bundle(registry, level=8))
    assert app.pending is None


def test_ranger_11_with_full_expertise_gets_no_menu(registry, tmp_path):
    bundle = ranger_bundle(registry, expertise=("survival", "stealth", "perception"))
    app, _ = loaded(registry, tmp_path, bundle)
    assert app.pending is None


def test_start_with_owing_hero_asks_for_expertise(registry, tmp_path):
    app = make_app(registry, tmp_path, ReactiveAdapter(), bundle=ranger_bundle(registry))
    assert app.pending == "expertise"


def test_start_with_pending_level_prefers_level_menu(registry, tmp_path):
    bundle = ranger_bundle(registry)
    bundle.heroes[0].pending_level = PendingLevel(
        class_id="ranger", hp_gain=5, draft=LevelChoices(level=12)
    )
    app = make_app(registry, tmp_path, ReactiveAdapter(), bundle=bundle)
    assert app.pending == "level_up"


def rogue_app(registry, tmp_path, skills):
    scores = {"str": 10, "dex": 16, "con": 14, "int": 10, "wis": 12, "cha": 10}
    bundle = make_bundle(registry)
    hero = make_class_hero("rogue", scores)
    hero.id = "hero"
    hero.location_id = bundle.heroes[0].location_id
    hero.sheet.skill_proficiencies = list(skills)
    bundle.heroes[0] = hero
    return make_app(registry, tmp_path, ReactiveAdapter(), bundle=bundle)


def test_rogue_level_1_without_expertise_gets_menu(registry, tmp_path):
    # Р-К8с-2 = а: меню догона всем с недобором (Томас, плут 1 ур.)
    app = rogue_app(registry, tmp_path, ["stealth", "athletics", "perception"])
    assert app.pending == "expertise"


def test_rogue_expertise_menu_finishes_with_two_choices(registry, tmp_path):
    app = rogue_app(registry, tmp_path, ["stealth", "athletics", "perception"])
    app.choose("stealth")
    app.choose("athletics")
    assert (app.bundle.heroes[0].sheet.skill_expertise, app.pending) == (
        ["stealth", "athletics"], None
    )


def test_rogue_without_proficient_skills_gets_no_menu(registry, tmp_path):
    # «0, если нет навыков на выбор»
    app = rogue_app(registry, tmp_path, [])
    assert app.pending is None


def test_start_announces_expertise_in_startup_lines(registry, tmp_path):
    # решение 17: при запуске та же строка, что и при /load
    app = make_app(registry, tmp_path, ReactiveAdapter(), bundle=ranger_bundle(registry))
    assert "Экспертиза: выберите навык для экспертизы." in app.startup_lines


def test_start_without_owing_has_no_expertise_startup_line(registry, tmp_path):
    bundle = ranger_bundle(registry, expertise=("survival", "stealth", "perception"))
    app = make_app(registry, tmp_path, ReactiveAdapter(), bundle=bundle)
    assert not any("Экспертиза" in line for line in app.startup_lines)


def test_start_with_pending_level_has_no_expertise_startup_line(registry, tmp_path):
    bundle = ranger_bundle(registry)
    bundle.heroes[0].pending_level = PendingLevel(
        class_id="ranger", hp_gain=5, draft=LevelChoices(level=12)
    )
    app = make_app(registry, tmp_path, ReactiveAdapter(), bundle=bundle)
    assert not any("Экспертиза" in line for line in app.startup_lines)
