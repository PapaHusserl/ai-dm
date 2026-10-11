# Б1б (B1-PLAN, A6, «Тесты Б1б»): HeroSession -- машина состояний создания героя без терминала.
# Ожидаемый API (ТРЕБОВАНИЕ к коду Б1б, A6): ai_dm.ui.hero_session.HeroSession(deps, task, width)
#   start() -> Step, submit(line) -> Step (Step из ui.session; блоки note/menu из ui.screen);
#   .sheet (HeroSheet | None), .run_ids (list[str]); цифра при меню -> пункт, вне меню -- текст.
# Меню ревью: принять / переописать / править; меню 2.2: повторить / сменить модель / выйти.
# Мастер -- ScriptedAdapter, живых вызовов нет.
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "game"))

from game_kit import FactorySpy  # noqa: E402
from hero_kit import deps, sheet_call, sheet_task, vale_pack  # noqa: E402
from master_kit import app_cfg, scripted, text_step, tools_step  # noqa: E402

from ai_dm.game.turn import REFUSAL_HINT  # noqa: E402
from ai_dm.rules.builder import SKILL_CONFLICT_MESSAGE, HeroSheet  # noqa: E402

DESCRIPTION = "воин-сирота ищет сестру"


def make(registry, cfg, tmp_path, steps, **kw):
    from ai_dm.ui.hero_session import HeroSession

    adapter = scripted(steps)
    hero_deps = deps(adapter, registry, cfg, tmp_path, **kw)
    session = HeroSession(hero_deps, sheet_task(vale_pack(registry)), 80)
    return session, adapter


def texts(step):
    parts = []
    for block in step.blocks:
        parts.append(block.text)
        parts.extend(block.items)
    return "\n".join(parts)


def menu_of(step):
    menus = [block for block in step.blocks if block.kind == "menu"]
    assert len(menus) == 1
    return list(menus[0].items)


def bad(call_id):
    return tools_step(sheet_call(call_id, motive=""))


def failing_steps():
    return [bad(f"s-{i}") for i in range(app_cfg().retry.invalid_retries + 1)]


def reviewed(registry, cfg, tmp_path, steps=None, **kw):
    # сессия после описания: ревью листа
    steps = [tools_step(sheet_call())] if steps is None else steps
    session, adapter = make(registry, cfg, tmp_path, steps, **kw)
    step = session.submit(DESCRIPTION)
    return session, adapter, step


def failed(registry, cfg, tmp_path, steps=None, **kw):
    # сессия после сбоя TurnFailed: меню 2.2
    steps = failing_steps() if steps is None else steps
    session, adapter = make(registry, cfg, tmp_path, steps, **kw)
    return session, adapter, session.submit(DESCRIPTION)


def sent(request):
    return json.loads(request.messages[0].content[0].text)


# старт и описание

def test_start_asks_to_describe_the_hero(registry, cfg, tmp_path):
    session, _ = make(registry, cfg, tmp_path, [])
    step = session.start()
    assert "Опишите героя" in texts(step)
    assert step.quit is False


def test_start_makes_no_model_call(registry, cfg, tmp_path):
    session, adapter = make(registry, cfg, tmp_path, [])
    session.start()
    assert adapter.requests == []


def test_description_shows_preview_of_the_sheet(registry, cfg, tmp_path):
    _, _, step = reviewed(registry, cfg, tmp_path)
    assert "Борин" in texts(step)
    assert "Мотив: Найти сестру." in texts(step)


def test_review_menu_has_three_items(registry, cfg, tmp_path):
    _, _, step = reviewed(registry, cfg, tmp_path)
    items = [item.lower() for item in menu_of(step)]
    assert len(items) == 3
    assert "принят" in items[0]
    assert "переопис" in items[1]
    assert "прав" in items[2]


def test_review_does_not_accept_the_sheet_yet(registry, cfg, tmp_path):
    session, _, step = reviewed(registry, cfg, tmp_path)
    assert session.sheet is None
    assert step.quit is False


def test_invalid_first_answer_is_retried_inside_master_session(registry, cfg, tmp_path):
    steps = [bad("s-1"), tools_step(sheet_call("s-2"))]
    session, adapter, step = reviewed(registry, cfg, tmp_path, steps)
    assert len(adapter.requests) == 2
    assert len(menu_of(step)) == 3
    assert "Борин" in texts(step)
    assert {block.kind for block in step.blocks} <= {"note", "raw", "menu"}


def test_one_description_is_one_run_id(registry, cfg, tmp_path):
    steps = [bad("s-1"), tools_step(sheet_call("s-2"))]
    session, _, _ = reviewed(registry, cfg, tmp_path, steps)
    assert len(session.run_ids) == 1
    assert session.run_ids[0].startswith("hero-")


# принять

def test_accept_gives_sheet_and_quits(registry, cfg, tmp_path):
    session, _, _ = reviewed(registry, cfg, tmp_path)
    step = session.submit("1")
    assert step.quit is True
    assert isinstance(session.sheet, HeroSheet)
    assert session.sheet.choices.name == "Борин"


def test_digit_outside_the_menu_is_refused(registry, cfg, tmp_path):
    session, adapter, _ = reviewed(registry, cfg, tmp_path)
    step = session.submit("9")
    assert "Нет такого варианта" in texts(step)
    assert step.quit is False
    assert session.sheet is None
    assert len(adapter.requests) == 1


# переописать

def test_remark_choice_asks_for_a_remark_without_model_call(registry, cfg, tmp_path):
    session, adapter, _ = reviewed(registry, cfg, tmp_path)
    step = session.submit("2")
    assert texts(step).strip()
    assert step.quit is False
    assert len(adapter.requests) == 1


def test_remark_makes_second_call_with_feedback_and_previous(registry, cfg, tmp_path):
    steps = [tools_step(sheet_call("s-1")), tools_step(sheet_call("s-2", name="Ило"))]
    session, adapter, _ = reviewed(registry, cfg, tmp_path, steps)
    session.submit("2")
    session.submit("пусть будет хромым")
    assert len(adapter.requests) == 2
    data = sent(adapter.requests[1])
    assert data["feedback"] == "пусть будет хромым"
    assert "Борин" in json.dumps(data["previous"], ensure_ascii=False)


def test_first_call_has_no_feedback_and_no_previous(registry, cfg, tmp_path):
    _, adapter, _ = reviewed(registry, cfg, tmp_path)
    data = sent(adapter.requests[0])
    assert data["feedback"] == ""
    assert data["previous"] is None


def test_remark_shows_new_sheet_for_review(registry, cfg, tmp_path):
    steps = [tools_step(sheet_call("s-1")), tools_step(sheet_call("s-2", name="Ило"))]
    session, _, _ = reviewed(registry, cfg, tmp_path, steps)
    session.submit("2")
    step = session.submit("пусть зовут Ило")
    assert "Ило" in texts(step)
    assert len(menu_of(step)) == 3


def test_remark_then_accept_gives_the_new_sheet(registry, cfg, tmp_path):
    steps = [tools_step(sheet_call("s-1")), tools_step(sheet_call("s-2", name="Ило"))]
    session, _, _ = reviewed(registry, cfg, tmp_path, steps)
    session.submit("2")
    session.submit("пусть зовут Ило")
    session.submit("1")
    assert session.sheet.choices.name == "Ило"


def test_run_ids_grow_with_each_model_call(registry, cfg, tmp_path):
    steps = [tools_step(sheet_call("s-1")), tools_step(sheet_call("s-2"))]
    session, _, _ = reviewed(registry, cfg, tmp_path, steps)
    session.submit("2")
    session.submit("иначе")
    assert len(session.run_ids) == 2
    assert len(set(session.run_ids)) == 2


# править

def test_edit_choice_shows_prompt_without_model_call(registry, cfg, tmp_path):
    session, adapter, _ = reviewed(registry, cfg, tmp_path)
    step = session.submit("3")
    assert texts(step).strip()
    assert len(adapter.requests) == 1


def test_edit_fields_lists_fields_with_current_values(registry, cfg, tmp_path):
    session, _, _ = reviewed(registry, cfg, tmp_path)
    session.submit("3")
    text = texts(session.submit("поля"))
    assert "name" in text
    assert "Борин" in text
    assert "motive" in text


def test_edit_valid_field_is_accepted(registry, cfg, tmp_path):
    session, _, _ = reviewed(registry, cfg, tmp_path)
    session.submit("3")
    step = session.submit("name = Ило")
    assert "принято" in texts(step).lower()


def test_edit_done_returns_to_review_with_edited_sheet(registry, cfg, tmp_path):
    session, _, _ = reviewed(registry, cfg, tmp_path)
    session.submit("3")
    session.submit("name = Ило")
    step = session.submit("готово")
    assert len(menu_of(step)) == 3
    assert "Ило" in texts(step)


def test_edit_then_accept_gives_edited_sheet(registry, cfg, tmp_path):
    session, adapter, _ = reviewed(registry, cfg, tmp_path)
    session.submit("3")
    session.submit("name = Ило")
    session.submit("готово")
    session.submit("1")
    assert session.sheet.choices.name == "Ило"
    assert len(adapter.requests) == 1


def test_edit_defect_gives_same_text_as_model_path(registry, cfg, tmp_path):
    session, _, _ = reviewed(registry, cfg, tmp_path)
    session.submit("3")
    step = session.submit("class_skills = perception, acrobatics")
    assert SKILL_CONFLICT_MESSAGE in texts(step)


def test_edit_to_taken_name_is_refused_with_check_hero_text(registry, cfg, tmp_path):
    session, _, _ = reviewed(registry, cfg, tmp_path)
    session.submit("3")
    step = session.submit("name = гракх")
    assert "уже занято (NPC, бог, фракция или герой)" in texts(step)


def test_edit_unknown_field_lists_fields(registry, cfg, tmp_path):
    session, _, _ = reviewed(registry, cfg, tmp_path)
    session.submit("3")
    text = texts(session.submit("нет_такого = 1"))
    assert "motive" in text
    assert "name" in text


def test_edit_does_not_call_the_model(registry, cfg, tmp_path):
    session, adapter, _ = reviewed(registry, cfg, tmp_path)
    session.submit("3")
    session.submit("поля")
    session.submit("name = Ило")
    session.submit("class_skills = perception, acrobatics")
    assert len(adapter.requests) == 1


# сбои: меню 2.2

def test_invalid_failure_gives_error_menu_with_three_items(registry, cfg, tmp_path):
    session, _, step = failed(registry, cfg, tmp_path)
    items = [item.lower() for item in menu_of(step)]
    assert len(items) == 3
    assert "повтор" in items[0]
    assert "модел" in items[1]
    assert "выйти" in items[2]
    assert session.sheet is None
    assert step.quit is False


def test_error_menu_retry_makes_new_run_and_shows_review(registry, cfg, tmp_path):
    steps = [*failing_steps(), tools_step(sheet_call("s-ok"))]
    session, adapter, _ = failed(registry, cfg, tmp_path, steps)
    step = session.submit("1")
    assert "Борин" in texts(step)
    assert len(menu_of(step)) == 3
    assert len(adapter.requests) == app_cfg().retry.invalid_retries + 2


def test_error_menu_retry_uses_a_new_run_id(registry, cfg, tmp_path):
    steps = [*failing_steps(), tools_step(sheet_call("s-ok"))]
    session, _, _ = failed(registry, cfg, tmp_path, steps)
    assert len(session.run_ids) == 1
    session.submit("1")
    assert len(session.run_ids) == 2
    assert len(set(session.run_ids)) == 2


def test_refusal_shows_refusal_hint_and_error_menu(registry, cfg, tmp_path):
    _, _, step = failed(registry, cfg, tmp_path, [{"stop": "refusal"}])
    assert REFUSAL_HINT in texts(step)
    assert len(menu_of(step)) == 3


def test_invalid_failure_does_not_show_refusal_hint(registry, cfg, tmp_path):
    _, _, step = failed(registry, cfg, tmp_path)
    assert REFUSAL_HINT not in texts(step)


def test_error_menu_quit_ends_without_sheet(registry, cfg, tmp_path):
    session, _, _ = failed(registry, cfg, tmp_path)
    step = session.submit("3")
    assert step.quit is True
    assert session.sheet is None


def test_error_menu_digit_outside_is_refused(registry, cfg, tmp_path):
    session, adapter, _ = failed(registry, cfg, tmp_path)
    count = len(adapter.requests)
    step = session.submit("9")
    assert "Нет такого варианта" in texts(step)
    assert step.quit is False
    assert len(adapter.requests) == count


def test_error_menu_switch_model_shows_model_options(registry, cfg, tmp_path):
    session, _, _ = failed(registry, cfg, tmp_path, adapter_factory=FactorySpy())
    step = session.submit("2")
    items = menu_of(step)
    assert len(items) >= 2
    assert all(":" in item for item in items)


def test_error_menu_switch_model_calls_factory_and_returns_to_error_menu(
    registry, cfg, tmp_path
):
    spy = FactorySpy()
    session, _, first = failed(registry, cfg, tmp_path, adapter_factory=spy)
    options = menu_of(session.submit("2"))
    step = session.submit("1")
    provider, _, model = options[0].partition(":")
    assert spy.calls == [(provider, model)]
    assert menu_of(step) == menu_of(first)


def test_switch_model_with_factory_error_shows_it_and_stays_on_error_menu(
    registry, cfg, tmp_path
):
    spy = FactorySpy(error=ValueError("ключ не найден"))
    session, _, first = failed(registry, cfg, tmp_path, adapter_factory=spy)
    session.submit("2")
    step = session.submit("1")
    assert "ключ не найден" in texts(step)
    assert menu_of(step) == menu_of(first)


def test_retry_after_model_switch_uses_the_new_adapter(registry, cfg, tmp_path):
    fresh = scripted([tools_step(sheet_call("s-new", name="Ило"))])
    session, _, _ = failed(registry, cfg, tmp_path, adapter_factory=lambda p, m: fresh)
    session.submit("2")
    session.submit("1")
    step = session.submit("1")
    assert len(fresh.requests) == 1
    assert "Ило" in texts(step)


def test_text_step_without_tool_is_not_an_accepted_sheet(registry, cfg, tmp_path):
    steps = [text_step("Расскажу своими словами.")] * (app_cfg().retry.invalid_retries + 1)
    session, _, step = failed(registry, cfg, tmp_path, steps)
    assert session.sheet is None
    assert len(menu_of(step)) == 3


# края ввода

def test_end_of_input_quits_without_sheet(registry, cfg, tmp_path):
    session, _ = make(registry, cfg, tmp_path, [])
    step = session.submit(None)
    assert step.quit is True
    assert session.sheet is None


def test_empty_description_repeats_hint_without_model_call(registry, cfg, tmp_path):
    session, adapter = make(registry, cfg, tmp_path, [])
    step = session.submit("   ")
    assert "Опишите героя" in texts(step)
    assert adapter.requests == []


def test_empty_remark_asks_again_without_model_call(registry, cfg, tmp_path):
    session, adapter, _ = reviewed(registry, cfg, tmp_path)
    session.submit("2")
    step = session.submit("")
    assert texts(step).strip()
    assert len(adapter.requests) == 1


def test_remark_state_does_not_treat_digit_as_menu(registry, cfg, tmp_path):
    steps = [tools_step(sheet_call("s-1")), tools_step(sheet_call("s-2"))]
    session, adapter, _ = reviewed(registry, cfg, tmp_path, steps)
    session.submit("2")
    session.submit("1")
    assert len(adapter.requests) == 2
    assert sent(adapter.requests[1])["feedback"] == "1"


def test_model_choice_digit_outside_is_refused(registry, cfg, tmp_path):
    spy = FactorySpy()
    session, _, _ = failed(registry, cfg, tmp_path, adapter_factory=spy)
    session.submit("2")
    step = session.submit("99")
    assert "Нет такого варианта" in texts(step)
    assert spy.calls == []


def test_end_of_input_in_error_menu_quits(registry, cfg, tmp_path):
    session, _, _ = failed(registry, cfg, tmp_path)
    assert session.submit(None).quit is True


def test_edit_state_ignores_menu_digits(registry, cfg, tmp_path):
    session, _, _ = reviewed(registry, cfg, tmp_path)
    session.submit("3")
    step = session.submit("1")
    assert step.quit is False
    assert session.sheet is None


# общий помощник model_options (game.app): тот же список у GameApp и у HeroSession

def test_model_options_helper_matches_config_without_duplicates():
    from ai_dm.game.app import model_options

    cfg_app = app_cfg()
    options = model_options(cfg_app)
    assert len(options) == len(set(options))
    assert f"{cfg_app.roles.narrator.provider}:{cfg_app.roles.narrator.model}" == options[0]
    assert (
        f"{cfg_app.alternatives.narrator.provider}:{cfg_app.alternatives.narrator.model}"
        in options
    )
    for profile in cfg_app.profiles.values():
        assert f"{profile.narrator.provider}:{profile.narrator.model}" in options


def test_session_model_menu_equals_helper_options(registry, cfg, tmp_path):
    from ai_dm.game.app import model_options

    session, _, _ = failed(registry, cfg, tmp_path, adapter_factory=FactorySpy())
    assert menu_of(session.submit("2")) == model_options(app_cfg())


def test_check_model_refuses_model_without_price_or_window():
    from ai_dm.game.app import check_model

    adapter, error = check_model(app_cfg(), FactorySpy(), "anthropic", "no-such-model")
    assert adapter is None
    assert "no-such-model" in error


def test_check_model_returns_adapter_from_factory():
    from ai_dm.game.app import check_model, model_options

    spy = FactorySpy()
    provider, _, model = model_options(app_cfg())[0].partition(":")
    adapter, error = check_model(app_cfg(), spy, provider, model)
    assert error is None
    assert adapter is spy.made[0]
    assert spy.calls == [(provider, model)]


# русский язык строк модуля (В-3: строки остаются в ui/hero_session.py)

def module_strings():
    import ai_dm.ui.hero_session as module

    found = {}
    for name, value in vars(module).items():
        if not name.isupper() or name == "REFUSAL_HINT":
            # REFUSAL_HINT -- строка слоя game (в ней слово tone), здесь только импортирована
            continue
        if isinstance(value, str):
            found[name] = [value]
        elif isinstance(value, list) and all(isinstance(x, str) for x in value):
            found[name] = value
    return found


def latin_words(text):
    import re

    return re.findall(r"[A-Za-z]+", text)


def test_module_has_user_strings():
    assert len(module_strings()) >= 8


def test_module_strings_are_russian():
    for name, values in module_strings().items():
        for value in values:
            assert any("а" <= ch.lower() <= "я" for ch in value), name


def test_module_strings_have_no_latin_words():
    for name, values in module_strings().items():
        for value in values:
            assert latin_words(value.replace("{name}", "").replace("{key}", "")) == [], name


def test_session_texts_have_no_latin_words_outside_sheet(registry, cfg, tmp_path):
    session, _, step = reviewed(registry, cfg, tmp_path)
    shown = [b.text for b in step.blocks if b.kind != "raw"] + menu_of(step)
    shown += [texts(session.start()), texts(session.submit("9")), texts(session.submit("2"))]
    assert latin_words("\n".join(shown)) == []


# добивка по выжившим мутантам mutmut (Б1б)

def test_empty_remark_repeats_remark_hint_not_describe_hint(registry, cfg, tmp_path):
    from ai_dm.ui.hero_session import DESCRIBE_HINT, REMARK_HINT

    session, _, _ = reviewed(registry, cfg, tmp_path)
    session.submit("2")
    text = texts(session.submit(""))
    assert REMARK_HINT in text
    assert DESCRIBE_HINT not in text


def test_remark_call_carries_the_original_description(registry, cfg, tmp_path):
    steps = [tools_step(sheet_call("s-1")), tools_step(sheet_call("s-2"))]
    session, adapter, _ = reviewed(registry, cfg, tmp_path, steps)
    session.submit("2")
    session.submit("иначе")
    assert sent(adapter.requests[1])["description"] == DESCRIPTION


def test_retry_from_error_menu_carries_the_description(registry, cfg, tmp_path):
    steps = [*failing_steps(), tools_step(sheet_call("s-ok"))]
    session, adapter, _ = failed(registry, cfg, tmp_path, steps)
    session.submit("1")
    assert sent(adapter.requests[-1])["description"] == DESCRIPTION


def test_previous_is_valid_hero_sheet_request_and_json_serializable(registry, cfg, tmp_path):
    from ai_dm.protocol.requests import HeroSheetRequest

    steps = [tools_step(sheet_call("s-1")), tools_step(sheet_call("s-2"))]
    session, adapter, _ = reviewed(registry, cfg, tmp_path, steps)
    session.submit("2")
    session.submit("иначе")
    previous = sent(adapter.requests[1])["previous"]
    request = HeroSheetRequest.model_validate(previous)
    assert request.name == "Борин"
    assert previous["opportunity"][0]["kind"] == "narrative"
    assert previous == sheet_call()["input"]


def test_previous_after_manual_edit_carries_the_edit(registry, cfg, tmp_path):
    steps = [tools_step(sheet_call("s-1")), tools_step(sheet_call("s-2"))]
    session, adapter, _ = reviewed(registry, cfg, tmp_path, steps)
    session.submit("3")
    session.submit("name = Ило")
    session.submit("готово")
    session.submit("2")
    session.submit("иначе")
    assert sent(adapter.requests[1])["previous"]["name"] == "Ило"


def test_run_ids_are_numbered_from_one_in_order(registry, cfg, tmp_path):
    steps = [tools_step(sheet_call("s-1")), tools_step(sheet_call("s-2"))]
    session, _, _ = reviewed(registry, cfg, tmp_path, steps)
    session.submit("2")
    session.submit("иначе")
    assert session.run_ids[0].endswith("-1")
    assert session.run_ids[1].endswith("-2")


def test_invalid_failure_note_is_not_none_and_not_empty(registry, cfg, tmp_path):
    _, _, step = failed(registry, cfg, tmp_path)
    note = step.blocks[0].text
    assert note.strip()
    assert note != "None"


def test_menu_titles_come_from_module_constants(registry, cfg, tmp_path):
    from ai_dm.ui.hero_session import ERROR_TITLE, MODEL_TITLE, REVIEW_TITLE

    session, _, review = reviewed(registry, cfg, tmp_path)
    assert [b.title for b in review.blocks if b.kind == "menu"] == [REVIEW_TITLE]
    session, _, error = failed(registry, cfg, tmp_path, adapter_factory=FactorySpy())
    assert [b.title for b in error.blocks if b.kind == "menu"] == [ERROR_TITLE]
    models = session.submit("2")
    assert [b.title for b in models.blocks if b.kind == "menu"] == [MODEL_TITLE]
    after = session.submit("1")
    assert [b.title for b in after.blocks if b.kind == "menu"] == [ERROR_TITLE]


def test_review_menu_refuses_digit_beyond_its_three_items(registry, cfg, tmp_path):
    session, adapter, _ = reviewed(registry, cfg, tmp_path)
    step = session.submit("4")
    assert "Нет такого варианта" in texts(step)
    assert session.sheet is None


def test_error_menu_refuses_digit_beyond_its_three_items(registry, cfg, tmp_path):
    session, adapter, _ = failed(registry, cfg, tmp_path, adapter_factory=FactorySpy())
    count = len(adapter.requests)
    step = session.submit("4")
    assert "Нет такого варианта" in texts(step)
    assert len(adapter.requests) == count


def test_accept_note_names_the_hero(registry, cfg, tmp_path):
    session, _, _ = reviewed(registry, cfg, tmp_path)
    assert "Борин" in texts(session.submit("1"))


def test_model_switch_sets_deps_model_and_notes_the_key(registry, cfg, tmp_path):
    session, _, _ = failed(registry, cfg, tmp_path, adapter_factory=FactorySpy())
    options = menu_of(session.submit("2"))
    step = session.submit("2")
    key = options[1]
    assert f"Модель рассказчика: {key}." in texts(step)
    assert session.deps.model == key.partition(":")[2]


def test_edit_fields_step_is_one_raw_block(registry, cfg, tmp_path):
    session, _, _ = reviewed(registry, cfg, tmp_path)
    session.submit("3")
    step = session.submit("поля")
    assert [b.kind for b in step.blocks] == ["raw"]
    assert any(item.startswith("name = ") for item in step.blocks[0].items)


def test_edit_with_several_defects_joins_texts_with_semicolon(registry, cfg, tmp_path):
    session, _, _ = reviewed(registry, cfg, tmp_path)
    session.submit("3")
    text = texts(session.submit("class = wizard"))
    assert "навыки класса: неверное число или не из списка; неверное число мастерств оружия" in text
    assert "у класса нет боевого стиля" in text


# добивка по выжившим мутантам mutmut (Б2а)

def test_propose_passes_its_run_id_to_the_journal(registry, cfg, tmp_path):
    session, _, _ = reviewed(registry, cfg, tmp_path)
    records = session.deps.journal.read_records()
    assert records
    assert {r["run_id"] for r in records} == {session.run_ids[0]}


def test_model_choice_accepts_the_last_option(registry, cfg, tmp_path):
    from ai_dm.game.app import model_options

    spy = FactorySpy()
    session, _, _ = failed(registry, cfg, tmp_path, adapter_factory=spy)
    options = model_options(app_cfg())
    session.submit("2")
    step = session.submit(str(len(options)))
    assert "Нет такого варианта" not in texts(step)
    provider, _, model = options[-1].partition(":")
    assert spy.calls == [(provider, model)]
