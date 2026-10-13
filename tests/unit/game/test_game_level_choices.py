# Меню выборов при повышении уровня в живой игре (docs/decisions/ranger-2-5-plan.md, разд. 5 п. 9,
# решение 5). Ожидаемое поведение GameApp (контракт меню -- в game_kit.py):
#   после choose("average" | "roll") с HP -- если на новом уровне есть обязательные выборы
#   (rules.progression.required_choices), pending остаётся "level_up", а reply.menu -- id вариантов
#   текущего выбора: стиль -> id черт категории fighting_style ("archery" ...); экспертиза -> id
#   навыков с владением ("survival" ...); подкласс -> id подклассов класса ("hunter",
#   "beast_master"); опция Добычи охотника -> "colossus_slayer" | "horde_breaker".
#   Когда все выборы сделаны (и опыта на следующий уровень нет) pending -> None, выборы
#   применены к листу героя. Герой без выборов на уровне (воин) -- как раньше: menu после HP нет.
from game_kit import ReactiveAdapter, make_app
from protocol_kit import make_bundle

from ai_dm.game.starter import ranger_choices
from ai_dm.rules.builder import build_character
from ai_dm.rules.progression import apply_level_choices, level_up, xp_for_level
from ai_dm.state.hero import LevelChoices


def ranger_bundle(registry, xp, level=1):
    bundle = make_bundle(registry)
    old = bundle.heroes[0]
    hero = build_character(ranger_choices("hero"), registry)
    hero.location_id = old.location_id
    hero.sheet.xp = xp
    if level >= 2:
        level_up(hero, registry, hp_method="average")
        apply_level_choices(
            hero, registry, LevelChoices(level=2, fighting_style="archery", expertise=["survival"])
        )
    bundle.heroes[0] = hero
    return bundle


def finish_spells(app, reply):
    # шаг заклинаний (D1): берём первый вариант меню, пока выборы уровня не кончатся
    while reply.pending == "level_up" and app.bundle.heroes[0].pending_level is not None:
        if "Выборы начаты заново." in reply.lines:
            break
        reply = app.choose(reply.menu[0])
    return reply


def offered(registry, tmp_path, xp, level=1):
    bundle = ranger_bundle(registry, xp, level)
    app = make_app(registry, tmp_path, ReactiveAdapter(), bundle=bundle)
    assert app.handle("Осматриваюсь").pending == "level_up"
    return app


def test_level_up_menu_for_ranger_is_still_hp_first(registry, tmp_path):
    app = offered(registry, tmp_path, xp_for_level(2, registry))
    assert app.handle("Иду").menu == ["average", "roll"]


def test_ranger_level_2_asks_for_fighting_style_after_hp(registry, tmp_path):
    app = offered(registry, tmp_path, xp_for_level(2, registry))
    reply = app.choose("average")
    assert reply.pending == "level_up"
    assert "archery" in reply.menu
    assert "alert" not in reply.menu


def test_ranger_level_2_asks_for_expertise_after_style(registry, tmp_path):
    app = offered(registry, tmp_path, xp_for_level(2, registry))
    app.choose("average")
    reply = app.choose("archery")
    assert reply.pending == "level_up"
    assert "survival" in reply.menu
    assert "athletics" not in reply.menu


def test_ranger_level_2_choices_are_applied_and_pending_is_cleared(registry, tmp_path):
    app = offered(registry, tmp_path, xp_for_level(2, registry))
    app.choose("average")
    app.choose("archery")
    reply = finish_spells(app, app.choose("survival"))
    hero = app.bundle.heroes[0]
    assert reply.pending is None
    assert app.pending is None
    assert hero.sheet.level == 2
    assert "archery" in hero.sheet.feats
    assert hero.sheet.skill_expertise == ["survival"]


def test_turn_is_not_played_while_choices_are_pending(registry, tmp_path):
    adapter = ReactiveAdapter()
    bundle = ranger_bundle(registry, xp_for_level(2, registry))
    app = make_app(registry, tmp_path, adapter, bundle=bundle)
    app.handle("Осматриваюсь")
    app.choose("average")
    asked = len(adapter.requests)
    reply = app.handle("Иду дальше")
    assert reply.pending == "level_up"
    assert reply.turn is None
    assert len(adapter.requests) == asked


def test_ranger_level_3_asks_for_subclass_then_hunters_prey(registry, tmp_path):
    app = offered(registry, tmp_path, xp_for_level(3, registry), level=2)
    reply = app.choose("average")
    assert reply.pending == "level_up"
    assert "hunter" in reply.menu
    assert "beast_master" in reply.menu
    reply = app.choose("hunter")
    assert reply.pending == "level_up"
    assert "colossus_slayer" in reply.menu
    reply = finish_spells(app, app.choose("colossus_slayer"))
    hero = app.bundle.heroes[0]
    assert reply.pending is None
    assert hero.sheet.level == 3
    assert hero.sheet.subclass_id == "hunter"
    assert hero.sheet.feature_choices == {"hunters_prey": ["colossus_slayer"]}


def test_ranger_level_3_beast_master_needs_only_the_subclass(registry, tmp_path):
    app = offered(registry, tmp_path, xp_for_level(3, registry), level=2)
    app.choose("average")
    reply = finish_spells(app, app.choose("beast_master"))
    assert reply.pending is None
    assert app.bundle.heroes[0].sheet.subclass_id == "beast_master"


def test_beast_master_gets_companion_hint_at_the_end_of_level_up(registry, tmp_path):
    app = offered(registry, tmp_path, xp_for_level(3, registry), level=2)
    app.choose("average")
    reply = finish_spells(app, app.choose("beast_master"))
    assert reply.pending is None
    text = "\n".join(reply.lines)
    assert "Повелитель зверей" in text
    assert "зверь-спутник" in text


def test_hunter_gets_no_companion_hint(registry, tmp_path):
    app = offered(registry, tmp_path, xp_for_level(3, registry), level=2)
    app.choose("average")
    reply = app.choose("hunter")
    reply = finish_spells(app, app.choose(reply.menu[0]))
    assert app.bundle.heroes[0].sheet.subclass_id == "hunter"
    assert "зверь-спутник" not in "\n".join(reply.lines)


def test_beast_master_with_beast_gets_no_hint(registry, tmp_path):
    from ai_dm.state.hero import Companion

    app = offered(registry, tmp_path, xp_for_level(3, registry), level=2)
    app.bundle.heroes[0].companions = [Companion(name="Акела", kind="волк")]
    app.choose("average")
    reply = finish_spells(app, app.choose("beast_master"))
    assert "зверь-спутник" not in "\n".join(reply.lines)


def test_level_up_without_beast_feature_has_only_the_level_line(registry, tmp_path):
    app = offered(registry, tmp_path, xp_for_level(2, registry))
    app.choose("average")
    app.choose("archery")
    reply = finish_spells(app, app.choose("survival"))
    assert "Повелитель зверей" not in "\n".join(reply.lines)


# регрессия: воин без выборов

def test_fighter_level_2_has_no_choice_menu_after_hp(registry, tmp_path):
    bundle = make_bundle(registry)
    bundle.heroes[0].sheet.xp = xp_for_level(2, registry)
    app = make_app(registry, tmp_path, ReactiveAdapter(), bundle=bundle)
    app.handle("Осматриваюсь")
    reply = app.choose("average")
    assert reply.pending is None
    assert reply.menu is None
    assert app.bundle.heroes[0].sheet.level == 2


# К0а: /save посреди выборов уровня штатно (pending_level лежит в сейве), уровень применяется при
# commit

def test_save_in_the_middle_of_level_choices_works(registry, tmp_path):
    app = offered(registry, tmp_path, xp_for_level(2, registry))
    app.choose("average")
    reply = app.handle("/save mid")
    assert reply.lines == ["Сохранено: manual-mid."]
    assert (tmp_path / "w1" / "slots" / "manual-mid").exists()
    assert app.pending == "level_up"


def test_level_is_not_applied_until_the_last_choice(registry, tmp_path):
    app = offered(registry, tmp_path, xp_for_level(2, registry))
    hero = app.bundle.heroes[0]
    hp = hero.creature.hp_max
    app.choose("average")
    assert hero.sheet.level == 1
    assert hero.creature.hp_max == hp
    assert hero.pending_level is not None
    app.choose("archery")
    assert hero.sheet.level == 1
    finish_spells(app, app.choose("survival"))
    assert hero.sheet.level == 2
    assert hero.creature.hp_max > hp
    assert hero.pending_level is None


def test_sheet_shows_old_level_in_the_middle_of_choices(registry, tmp_path):
    app = offered(registry, tmp_path, xp_for_level(2, registry))
    app.choose("average")
    assert "следопыт 1 ур." in app.handle("/sheet").lines[0]


def test_first_line_after_hp_names_the_level_and_the_step(registry, tmp_path):
    app = offered(registry, tmp_path, xp_for_level(2, registry))
    reply = app.choose("average")
    assert reply.lines[0].startswith("Опыта хватает на уровень 2: выберите ")


def test_load_in_the_middle_of_choices_continues_the_menu(registry, tmp_path):
    app = offered(registry, tmp_path, xp_for_level(2, registry))
    app.choose("average")
    app.choose("archery")
    app.handle("/save mid")
    menu = app.menu_for("level_up")
    app.pending = None
    lines = app.load("manual-mid")
    assert app.pending == "level_up"
    assert app.menu_for("level_up") == menu
    assert "survival" in menu
    assert lines[0].startswith("Загружено: manual-mid")


def test_turn_with_started_level_up_names_the_current_step(registry, tmp_path):
    app = offered(registry, tmp_path, xp_for_level(2, registry))
    app.choose("average")
    app.pending = None
    reply = app.handle("Осматриваюсь")
    assert reply.pending == "level_up"
    assert reply.lines[-1] == "Выберите: боевой стиль."
    assert "HP" not in reply.lines[-1]


def test_loaded_menu_can_be_finished(registry, tmp_path):
    app = offered(registry, tmp_path, xp_for_level(2, registry))
    app.choose("average")
    app.handle("/save mid")
    app.load("manual-mid")
    app.choose("archery")
    finish_spells(app, app.choose("survival"))
    hero = app.bundle.heroes[0]
    assert (app.pending, hero.pending_level, hero.sheet.level) == (None, None, 2)
    assert "archery" in hero.sheet.feats


def test_app_with_pending_level_in_bundle_opens_the_menu_at_once(registry, tmp_path):
    first = offered(registry, tmp_path / "a", xp_for_level(2, registry))
    first.choose("average")
    bundle = first.bundle
    second = make_app(registry, tmp_path / "b", ReactiveAdapter(), bundle=bundle)
    assert second.pending == "level_up"
    assert "archery" in second.menu_for("level_up")


def test_app_without_pending_level_starts_without_pending(registry, tmp_path):
    app = make_app(registry, tmp_path, ReactiveAdapter(), bundle=ranger_bundle(registry, 0))
    assert app.pending is None


def test_save_works_after_choices_are_done(registry, tmp_path):
    app = offered(registry, tmp_path, xp_for_level(2, registry))
    app.choose("average")
    app.choose("archery")
    app.choose("survival")
    while app.pending == "level_up":
        app.choose(app.menu_for("level_up")[0])
    reply = app.handle("/save done")
    assert reply.lines == ["Сохранено: manual-done."]


# B2: отказ выбора -- pending остаётся, выборы заново с первого шага

def refuse_once(monkeypatch):
    # первое применение выборов отказывает, дальше работает настоящая функция
    from ai_dm.game import app as app_module
    from ai_dm.rules.builder import ValidationErrors

    real = app_module.commit_level_up
    calls = []

    def fake(hero, registry):
        calls.append(hero.pending_level.draft)
        if len(calls) == 1:
            return ValidationErrors(["bad"], ["Выбор не подошёл."])
        return real(hero, registry)

    monkeypatch.setattr(app_module, "commit_level_up", fake)


def test_refused_choice_keeps_pending_and_restarts_from_first_step(registry, tmp_path, monkeypatch):
    refuse_once(monkeypatch)
    app = offered(registry, tmp_path, xp_for_level(2, registry))
    app.choose("average")
    app.choose("archery")
    reply = finish_spells(app, app.choose("survival"))
    hero = app.bundle.heroes[0]
    assert "Выборы начаты заново." in reply.lines
    assert reply.pending == "level_up"
    assert app.pending == "level_up"
    assert "archery" in reply.menu
    assert hero.sheet.level == 1
    assert hero.pending_level is not None
    assert hero.pending_level.draft.fighting_style is None
    assert "archery" not in hero.sheet.feats
    assert hero.sheet.skill_expertise == []


def test_choices_can_be_redone_after_refusal(registry, tmp_path, monkeypatch):
    refuse_once(monkeypatch)
    app = offered(registry, tmp_path, xp_for_level(2, registry))
    app.choose("average")
    app.choose("archery")
    finish_spells(app, app.choose("survival"))
    app.choose("archery")
    finish_spells(app, app.choose("survival"))
    hero = app.bundle.heroes[0]
    assert app.pending is None
    assert "archery" in hero.sheet.feats
    assert hero.sheet.skill_expertise == ["survival"]


# D1: шаг заклинаний -- добор до prepared_limit, круг не выше доступного, Метка не в счёт

def to_spells_step(app):
    app.choose("average")
    return app.choose("beast_master")


def test_level_3_asks_for_spells_up_to_the_limit(registry, tmp_path):
    app = offered(registry, tmp_path, xp_for_level(3, registry), level=2)
    reply = to_spells_step(app)
    assert reply.pending == "level_up"
    assert "cure_wounds" in reply.menu
    assert "pass_without_trace" not in reply.menu
    assert "hunters_mark" not in reply.menu
    assert "magic_missile" not in reply.menu


def test_spells_are_added_one_by_one_until_the_limit(registry, tmp_path):
    app = offered(registry, tmp_path, xp_for_level(3, registry), level=2)
    reply = to_spells_step(app)
    picked = []
    for spell in ("cure_wounds", "fog_cloud", "goodberry"):
        assert reply.pending == "level_up"
        assert spell in reply.menu
        reply = app.choose(spell)
        picked.append(spell)
        assert spell not in (reply.menu or [])
    assert reply.pending == "level_up"
    reply = app.choose("speak_with_animals")
    hero = app.bundle.heroes[0]
    assert reply.pending is None
    assert set(picked + ["speak_with_animals"]) <= set(hero.sheet.prepared_of())
    assert len([s for s in hero.sheet.prepared_of() if s != "hunters_mark"]) == 4


def test_spells_step_counts_already_prepared_spells(registry, tmp_path):
    bundle = ranger_bundle(registry, xp_for_level(3, registry), level=2)
    bundle.heroes[0].sheet.prepared_of()[:] = ["cure_wounds", "fog_cloud", "goodberry"]
    app = make_app(registry, tmp_path, ReactiveAdapter(), bundle=bundle)
    app.handle("Осматриваюсь")
    reply = to_spells_step(app)
    assert "cure_wounds" not in reply.menu
    reply = app.choose("speak_with_animals")
    assert reply.pending is None
    assert len(app.bundle.heroes[0].sheet.prepared_of()) == 4


def test_level_5_spells_step_offers_second_circle(registry, tmp_path):
    bundle = ranger_bundle(registry, xp_for_level(5, registry), level=2)
    bundle.heroes[0].sheet.primary.level = 4
    bundle.heroes[0].sheet.primary.subclass_id = "beast_master"
    bundle.heroes[0].sheet.prepared_of()[:] = [
        "cure_wounds", "fog_cloud", "goodberry", "alarm", "longstrider",
    ]
    app = make_app(registry, tmp_path, ReactiveAdapter(), bundle=bundle)
    app.handle("Осматриваюсь")
    reply = app.choose("average")
    assert "pass_without_trace" in reply.menu


# К0а: шаги меню -- подсказка следующего шага и запись повышения характеристик в черновик

def ranger_at_level_3_menu(registry, tmp_path):
    bundle = ranger_bundle(registry, xp_for_level(4, registry), level=2)
    bundle.heroes[0].sheet.primary.level = 3
    bundle.heroes[0].sheet.level_history = ["ranger"] * 3
    bundle.heroes[0].sheet.primary.subclass_id = "beast_master"
    bundle.heroes[0].sheet.prepared_of()[:] = ["cure_wounds", "fog_cloud", "goodberry", "alarm"]
    app = make_app(registry, tmp_path, ReactiveAdapter(), bundle=bundle)
    app.handle("Осматриваюсь")
    app.choose("average")
    return app


def test_next_step_line_names_the_step(registry, tmp_path):
    app = offered(registry, tmp_path, xp_for_level(2, registry))
    app.choose("average")
    assert app.choose("archery").lines == ["Выберите: навык для экспертизы."]


def test_asi_plus_two_is_written_to_the_draft(registry, tmp_path):
    app = ranger_at_level_3_menu(registry, tmp_path)
    assert "dex+2" in app.menu_for("level_up")
    app.choose("dex+2")
    assert app.bundle.heroes[0].pending_level.draft.asi == {"dex": 2}


def test_asi_two_abilities_is_written_to_the_draft(registry, tmp_path):
    app = ranger_at_level_3_menu(registry, tmp_path)
    app.choose("dex+wis")
    assert app.bundle.heroes[0].pending_level.draft.asi == {"dex": 1, "wis": 1}


def test_asi_plus_two_is_applied_at_the_end(registry, tmp_path):
    app = ranger_at_level_3_menu(registry, tmp_path)
    hero = app.bundle.heroes[0]
    dex = hero.sheet.abilities["dex"]
    finish_spells(app, app.choose("dex+2"))
    assert (hero.sheet.level, hero.sheet.abilities["dex"]) == (4, dex + 2)


def test_asi_two_abilities_is_applied_at_the_end(registry, tmp_path):
    app = ranger_at_level_3_menu(registry, tmp_path)
    hero = app.bundle.heroes[0]
    dex, wis = hero.sheet.abilities["dex"], hero.sheet.abilities["wis"]
    finish_spells(app, app.choose("dex+wis"))
    assert (hero.sheet.abilities["dex"], hero.sheet.abilities["wis"]) == (dex + 1, wis + 1)


def test_save_current_auto_writes_the_auto_slot(registry, tmp_path):
    app = offered(registry, tmp_path, xp_for_level(2, registry))
    app.save_current("auto")
    assert (tmp_path / "w1" / "slots" / "auto").exists()


def test_tone_confirm_menu_is_yes_no(registry, tmp_path):
    app = make_app(registry, tmp_path, ReactiveAdapter(), bundle=ranger_bundle(registry, 0))
    assert app.menu_for("tone_confirm") == ["да", "нет"]
