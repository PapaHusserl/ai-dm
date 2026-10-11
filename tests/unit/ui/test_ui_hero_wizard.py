# Б2а (B2-PLAN, A6, «Тесты Б2а»): HeroWizard -- автомат пошагового создания героя без терминала.
# Ожидаемый API (ТРЕБОВАНИЕ к коду Б2а): ai_dm.ui.hero_wizard.HeroWizard(deps, task, width) --
#   start() -> Step, submit(line) -> Step, .sheet, .run_ids, .draft, .pos (индекс в
#   game.hero_steps.STEPS), .state ("step" | "words" | "error_menu" | "model_choice" | "review");
#   константы WIZARD_HINT, AT_START, WORDS_HINT, WIZARD_REVIEW_MENU, BACK_TO_LIST.
#   Слова «назад» / «отмена» -- в любом месте.
# Мастер -- ScriptedAdapter только для шага «описать словами»; живых вызовов нет.
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "game"))

from game_kit import FactorySpy  # noqa: E402
from hero_kit import (  # noqa: E402
    deps,
    first_option_walk,
    lines_before,
    sheet_task,
    vale_pack,
    walk,
    wizard_script,
    wizard_sheet,
)
from master_kit import app_cfg, scripted, tools_step  # noqa: E402

from ai_dm.game.turn import REFUSAL_HINT  # noqa: E402
from ai_dm.rules.builder import (  # noqa: E402
    ABILITY_MESSAGES,
    SKILL_CONFLICT_MESSAGE,
    HeroSheet,
    over_twenty_message,
)
from ai_dm.state.hero import BackgroundSpec  # noqa: E402

SCRIPT = wizard_script()
ALL = [line for _, line in SCRIPT]


def make(registry, cfg, tmp_path=None, steps=None, **kw):
    from ai_dm.ui.hero_wizard import HeroWizard

    adapter = scripted(steps) if steps is not None else None
    hero_deps = deps(adapter, registry, cfg, tmp_path, **kw)
    wizard = HeroWizard(hero_deps, sheet_task(vale_pack(registry)), 80)
    return wizard, adapter


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


def title_of(step):
    menus = [block for block in step.blocks if block.kind == "menu"]
    return menus[0].title


def number_of(step, text):
    # номер пункта меню по началу подписи (порядок пунктов в тестах не зашит)
    for number, item in enumerate(menu_of(step), start=1):
        if item.startswith(text):
            return str(number)
    raise AssertionError(f"нет пункта {text!r} в {menu_of(step)}")


def key_of(wizard):
    from ai_dm.game.hero_steps import STEPS

    return STEPS[wizard.pos].key


def reviewed(registry, cfg, tmp_path=None):
    wizard, _ = make(registry, cfg, tmp_path)
    step = walk(wizard, ALL)
    return wizard, step


# старт и меню

def test_start_shows_hint_and_species_menu(registry, cfg):
    from ai_dm.ui.hero_wizard import WIZARD_HINT

    wizard, _ = make(registry, cfg)
    step = wizard.start()
    assert WIZARD_HINT in texts(step)
    items = menu_of(step)
    assert len(items) == 4
    assert "Человек" in items
    assert step.quit is False


def test_start_makes_no_model_call(registry, cfg):
    wizard, adapter = make(registry, cfg, steps=[])
    wizard.start()
    assert adapter.requests == []


def test_digit_outside_the_menu_is_refused(registry, cfg):
    from ai_dm.ui.hero_session import NO_SUCH

    wizard, _ = make(registry, cfg)
    wizard.start()
    step = wizard.submit("9")
    assert NO_SUCH in texts(step)
    assert key_of(wizard) == "species"
    assert step.quit is False


def test_text_on_a_menu_step_is_refused(registry, cfg):
    from ai_dm.ui.hero_session import NO_SUCH

    wizard, _ = make(registry, cfg)
    wizard.start()
    step = wizard.submit("человек")
    assert NO_SUCH in texts(step)
    assert key_of(wizard) == "species"


def test_zero_is_not_a_menu_item(registry, cfg):
    from ai_dm.ui.hero_session import NO_SUCH

    wizard, _ = make(registry, cfg)
    wizard.start()
    assert NO_SUCH in texts(wizard.submit("0"))


def test_end_of_input_quits_without_sheet(registry, cfg):
    wizard, _ = make(registry, cfg)
    wizard.start()
    step = wizard.submit(None)
    assert step.quit is True
    assert wizard.sheet is None


def test_choice_moves_to_the_next_step_menu(registry, cfg):
    wizard, _ = make(registry, cfg)
    wizard.start()
    step = wizard.submit(ALL[0])
    assert key_of(wizard) == "class"
    assert "Воин" in menu_of(step)
    assert wizard.draft.species_id == "human"


def test_multi_step_title_shows_progress(registry, cfg):
    wizard, _ = make(registry, cfg)
    step = walk(wizard, lines_before(SCRIPT, "class_skills"))
    assert "1 из 2" in title_of(step)
    second = wizard.submit(ALL[len(lines_before(SCRIPT, "class_skills"))])
    assert "2 из 2" in title_of(second)


def test_multi_step_does_not_offer_the_chosen_item_again(registry, cfg):
    wizard, _ = make(registry, cfg)
    step = walk(wizard, lines_before(SCRIPT, "class_skills"))
    first = menu_of(step)
    second = menu_of(wizard.submit("1"))
    assert len(second) == len(first) - 1
    assert first[0] not in second


def test_background_menu_has_four_srd_and_describe_in_words(registry, cfg):
    wizard, _ = make(registry, cfg)
    step = walk(wizard, lines_before(SCRIPT, "background"))
    items = menu_of(step)
    assert len(items) == 5
    assert "Солдат" in items


def test_method_menu_has_three_methods(registry, cfg):
    wizard, _ = make(registry, cfg)
    step = walk(wizard, lines_before(SCRIPT, "method"))
    assert len(menu_of(step)) == 3


def test_class_skill_menu_has_no_background_skills(registry, cfg):
    wizard, _ = make(registry, cfg)
    step = walk(wizard, lines_before(SCRIPT, "class_skills"))
    shown = "\n".join(menu_of(step))
    assert "Атлетика" not in shown
    assert "Запугивание" not in shown
    assert "Восприятие" in shown


# полный путь и ревью

def test_full_script_gives_review_with_preview_and_menu(registry, cfg):
    from ai_dm.ui.hero_wizard import WIZARD_REVIEW_MENU

    wizard, step = reviewed(registry, cfg)
    assert wizard.state == "review"
    assert "Борин" in texts(step)
    assert "Мотив: Найти сестру." in texts(step)
    assert menu_of(step) == list(WIZARD_REVIEW_MENU)


def test_review_menu_is_accept_back_to_steps_edit():
    from ai_dm.ui.hero_wizard import WIZARD_REVIEW_MENU

    items = [item.lower() for item in WIZARD_REVIEW_MENU]
    assert len(items) == 3
    assert "принят" in items[0]
    assert "шаг" in items[1]
    assert "прав" in items[2]


def test_review_does_not_accept_the_sheet_yet(registry, cfg):
    wizard, step = reviewed(registry, cfg)
    assert wizard.sheet is None
    assert step.quit is False


def test_accept_gives_the_canonical_sheet_and_quits(registry, cfg):
    wizard, _ = reviewed(registry, cfg)
    step = wizard.submit("1")
    assert step.quit is True
    assert isinstance(wizard.sheet, HeroSheet)
    assert wizard.sheet == wizard_sheet()
    assert "Борин" in texts(step)


def test_to_sheet_of_the_walked_draft_equals_the_canon(registry, cfg):
    from ai_dm.game.hero_steps import to_sheet

    wizard, _ = reviewed(registry, cfg)
    assert to_sheet(wizard.draft, registry) == wizard_sheet()


def test_review_digit_outside_the_menu_is_refused(registry, cfg):
    from ai_dm.ui.hero_session import NO_SUCH

    wizard, _ = reviewed(registry, cfg)
    step = wizard.submit("4")
    assert NO_SUCH in texts(step)
    assert wizard.sheet is None


def test_stepwise_path_makes_no_model_call(registry, cfg, tmp_path):
    wizard, adapter = make(registry, cfg, tmp_path, steps=[])
    walk(wizard, ALL)
    wizard.submit("1")
    assert adapter.requests == []
    assert wizard.run_ids == []


def test_back_to_steps_returns_to_the_last_step_with_hint(registry, cfg):
    wizard, _ = reviewed(registry, cfg)
    step = wizard.submit("2")
    assert key_of(wizard) == "means"
    assert wizard.state == "step"
    assert texts(step).strip()
    assert wizard.sheet is None


def test_back_to_steps_then_back_twice_returns_to_the_name(registry, cfg):
    wizard, _ = reviewed(registry, cfg)
    wizard.submit("2")
    wizard.submit("назад")
    wizard.submit("назад")
    assert key_of(wizard) == "name"


def test_back_to_steps_and_new_means_give_a_new_sheet(registry, cfg):
    wizard, _ = reviewed(registry, cfg)
    wizard.submit("2")
    wizard.submit("лук, смелость")
    wizard.submit("1")
    assert wizard.sheet.means == ["лук", "смелость"]
    assert wizard.sheet.choices.name == "Борин"


def test_back_to_steps_and_same_answers_give_the_same_sheet(registry, cfg):
    wizard, _ = reviewed(registry, cfg)
    wizard.submit("2")
    wizard.submit("назад")
    wizard.submit("назад")
    walk_lines = [ALL[-3], ALL[-2], ALL[-1]]
    for line in walk_lines:
        wizard.submit(line)
    wizard.submit("1")
    assert wizard.sheet == wizard_sheet()


def test_edit_choice_shows_prompt_without_model_call(registry, cfg):
    wizard, _ = reviewed(registry, cfg)
    step = wizard.submit("3")
    assert texts(step).strip()
    assert wizard.sheet is None


def test_edit_defect_gives_the_same_text_as_b1(registry, cfg):
    wizard, _ = reviewed(registry, cfg)
    wizard.submit("3")
    step = wizard.submit("class_skills = athletics, perception")
    assert SKILL_CONFLICT_MESSAGE in texts(step)


def test_edit_done_returns_to_the_wizard_review_menu(registry, cfg):
    from ai_dm.ui.hero_wizard import WIZARD_REVIEW_MENU

    wizard, _ = reviewed(registry, cfg)
    wizard.submit("3")
    wizard.submit("name = Ило")
    step = wizard.submit("готово")
    assert menu_of(step) == list(WIZARD_REVIEW_MENU)
    assert "Ило" in texts(step)


def test_edit_then_accept_gives_the_edited_sheet(registry, cfg):
    wizard, _ = reviewed(registry, cfg)
    wizard.submit("3")
    wizard.submit("name = Ило")
    wizard.submit("готово")
    wizard.submit("1")
    assert wizard.sheet.choices.name == "Ило"


def test_edit_to_taken_name_is_refused_with_check_hero_text(registry, cfg):
    wizard, _ = reviewed(registry, cfg)
    wizard.submit("3")
    step = wizard.submit("name = гракх")
    assert "уже занято (NPC, бог, фракция или герой)" in texts(step)


# навигация

def test_back_at_the_first_step_says_so(registry, cfg):
    from ai_dm.ui.hero_wizard import AT_START

    wizard, _ = make(registry, cfg)
    wizard.start()
    step = wizard.submit("назад")
    assert AT_START in texts(step)
    assert key_of(wizard) == "species"
    assert step.quit is False


def test_back_after_class_shows_class_menu_and_clears_the_class(registry, cfg):
    wizard, _ = make(registry, cfg)
    walk(wizard, ALL[:2])
    assert key_of(wizard) == "background"
    step = wizard.submit("назад")
    assert key_of(wizard) == "class"
    assert "Воин" in menu_of(step)
    assert wizard.draft.class_id == ""
    assert wizard.draft.species_id == "human"


def test_back_is_case_insensitive_and_trimmed(registry, cfg):
    wizard, _ = make(registry, cfg)
    walk(wizard, ALL[:1])
    wizard.submit("  Назад ")
    assert key_of(wizard) == "species"


def test_back_in_the_middle_of_multi_removes_one_item(registry, cfg):
    wizard, _ = make(registry, cfg)
    walk(wizard, lines_before(SCRIPT, "class_skills"))
    wizard.submit("1")
    assert len(wizard.draft.class_skills) == 1
    step = wizard.submit("назад")
    assert key_of(wizard) == "class_skills"
    assert wizard.draft.class_skills == []
    assert "1 из 2" in title_of(step)


def test_back_at_the_start_of_multi_goes_to_the_previous_step(registry, cfg):
    wizard, _ = make(registry, cfg)
    walk(wizard, lines_before(SCRIPT, "class_skills"))
    wizard.submit("назад")
    assert key_of(wizard) == "bonus"


def test_back_over_a_choice_forgets_it_for_good(registry, cfg):
    wizard, _ = make(registry, cfg)
    walk(wizard, lines_before(SCRIPT, "class_skills"))
    wizard.submit("1")
    wizard.submit("1")
    assert len(wizard.draft.class_skills) == 2
    wizard.submit("назад")
    assert len(wizard.draft.class_skills) == 1


def test_cancel_quits_without_sheet(registry, cfg):
    wizard, _ = make(registry, cfg)
    walk(wizard, ALL[:3])
    step = wizard.submit("отмена")
    assert step.quit is True
    assert wizard.sheet is None


def test_cancel_works_on_text_step_and_in_review(registry, cfg):
    wizard, _ = make(registry, cfg)
    walk(wizard, ALL[:-3])
    assert wizard.submit("отмена").quit is True
    other, _ = reviewed(registry, cfg)
    assert other.submit("отмена").quit is True
    assert other.sheet is None


def test_empty_text_repeats_the_hint(registry, cfg):
    wizard, _ = make(registry, cfg)
    walk(wizard, lines_before(SCRIPT, "name"))
    step = wizard.submit("   ")
    assert texts(step).strip()
    assert key_of(wizard) == "name"


# ввод характеристик: тексты валидатора

def to_scores(registry, cfg, method):
    wizard, _ = make(registry, cfg)
    step = walk(wizard, lines_before(SCRIPT, "method") + [method])
    return wizard, step


def test_point_buy_menu_shows_prices_and_remaining_points(registry, cfg):
    wizard, step = to_scores(registry, cfg, "2")
    assert key_of(wizard) == "scores"
    assert "(5 очков)" in "\n".join(menu_of(step))
    assert "27" in title_of(step)
    assert "Сила" in title_of(step)


def test_point_buy_remaining_points_drop_after_a_choice(registry, cfg):
    wizard, step = to_scores(registry, cfg, "2")
    step = wizard.submit(number_of(step, "15"))
    assert "18" in title_of(step)
    assert "Ловкость" in title_of(step)


def test_point_buy_over_budget_gives_validator_text_and_repeats(registry, cfg):
    wizard, step = to_scores(registry, cfg, "2")
    for _ in range(3):
        step = wizard.submit(number_of(step, "15"))
    step = wizard.submit(number_of(step, "15"))
    assert ABILITY_MESSAGES["point_buy_invalid"] in texts(step)
    assert key_of(wizard) == "scores"
    assert len(wizard.draft.scores) == 3


def test_point_buy_after_error_a_cheaper_value_passes(registry, cfg):
    wizard, step = to_scores(registry, cfg, "2")
    for _ in range(3):
        step = wizard.submit(number_of(step, "15"))
    step = wizard.submit(number_of(step, "15"))
    step = wizard.submit(number_of(step, "8"))
    assert ABILITY_MESSAGES["point_buy_invalid"] not in texts(step)
    assert len(wizard.draft.scores) == 4


def test_point_buy_six_values_in_budget_go_on(registry, cfg):
    wizard, step = to_scores(registry, cfg, "2")
    for value in ("15", "15", "15", "8", "8", "8"):
        step = wizard.submit(number_of(step, value))
    assert key_of(wizard) == "bonus_scheme"
    assert wizard.draft.scores == {
        "str": 15, "dex": 15, "con": 15, "int": 8, "wis": 8, "cha": 8,
    }


def test_explicit_over_20_gives_validator_text_and_repeats(registry, cfg):
    wizard, _ = to_scores(registry, cfg, "3")
    step = wizard.submit("21")
    assert ABILITY_MESSAGES["abilities_invalid"] in texts(step)
    assert key_of(wizard) == "scores"
    assert wizard.draft.scores == {}


def test_explicit_below_3_gives_the_same_text(registry, cfg):
    wizard, _ = to_scores(registry, cfg, "3")
    assert ABILITY_MESSAGES["abilities_invalid"] in texts(wizard.submit("2"))


def test_explicit_valid_value_goes_to_the_next_ability(registry, cfg):
    wizard, _ = to_scores(registry, cfg, "3")
    wizard.submit("20")
    assert wizard.draft.scores == {"str": 20}
    assert key_of(wizard) == "scores"


def test_explicit_not_a_number_is_refused_and_repeats(registry, cfg):
    wizard, _ = to_scores(registry, cfg, "3")
    step = wizard.submit("много")
    assert texts(step).strip()
    assert wizard.draft.scores == {}


def test_standard_array_menu_loses_the_used_value(registry, cfg):
    wizard, step = to_scores(registry, cfg, "1")
    first = menu_of(step)
    step = wizard.submit(number_of(step, "15"))
    assert len(menu_of(step)) == len(first) - 1
    assert not any(item.startswith("15") for item in menu_of(step))


def explicit_to_bonus(registry, cfg, str_score):
    wizard, _ = to_scores(registry, cfg, "3")
    for value in (str_score, "10", "10", "10", "10", "10"):
        wizard.submit(value)
    return wizard


def test_bonus_over_20_gives_validator_text_and_goes_back_to_scheme(registry, cfg):
    wizard = explicit_to_bonus(registry, cfg, "19")
    assert key_of(wizard) == "bonus_scheme"
    step = wizard.submit("1")
    assert key_of(wizard) == "bonus"
    step = wizard.submit(number_of(step, "Сила"))
    assert over_twenty_message("str") in texts(step)
    assert key_of(wizard) == "bonus_scheme"
    assert wizard.draft.bonus == {}


def test_bonus_to_20_exactly_is_not_an_error(registry, cfg):
    wizard = explicit_to_bonus(registry, cfg, "19")
    step = wizard.submit("1")
    step = wizard.submit(number_of(step, "Ловкость"))
    assert over_twenty_message("dex") not in texts(step)
    step = wizard.submit(number_of(step, "Сила"))
    assert over_twenty_message("str") not in texts(step)
    assert wizard.draft.bonus == {"dex": 2, "str": 1}


def test_bonus_scheme_one_one_one_needs_no_bonus_questions(registry, cfg):
    wizard = explicit_to_bonus(registry, cfg, "10")
    wizard.submit("2")
    assert key_of(wizard) == "class_skills"
    assert wizard.draft.bonus == {"str": 1, "dex": 1, "con": 1}


# имя, мотив, средства

def to_name(registry, cfg):
    wizard, _ = make(registry, cfg)
    walk(wizard, lines_before(SCRIPT, "name"))
    return wizard


def test_empty_name_is_refused_with_validator_text(registry, cfg):
    wizard = to_name(registry, cfg)
    step = wizard.submit("")
    assert key_of(wizard) == "name"
    assert texts(step).strip()
    assert wizard.draft.name == ""


def test_taken_name_is_refused_with_check_hero_text_in_any_case(registry, cfg):
    wizard = to_name(registry, cfg)
    step = wizard.submit("гракх")
    assert "имя 'гракх' уже занято (NPC, бог, фракция или герой)" in texts(step)
    assert key_of(wizard) == "name"
    assert wizard.draft.name == ""


def test_name_of_a_pack_npc_is_taken(registry, cfg):
    wizard = to_name(registry, cfg)
    assert "уже занято" in texts(wizard.submit("Гарт"))


def test_free_name_goes_on_to_motive(registry, cfg):
    wizard = to_name(registry, cfg)
    wizard.submit("Борин")
    assert key_of(wizard) == "motive"
    assert wizard.draft.name == "Борин"


def test_empty_motive_is_refused(registry, cfg):
    wizard = to_name(registry, cfg)
    wizard.submit("Борин")
    step = wizard.submit("")
    assert key_of(wizard) == "motive"
    assert texts(step).strip()


def test_too_long_motive_is_refused_with_validator_text(registry, cfg):
    from ai_dm.rules.builder import hooks_problems

    wizard = to_name(registry, cfg)
    wizard.submit("Борин")
    step = wizard.submit("м" * 201)
    assert hooks_problems("м" * 201, ["а"])[0][1] in texts(step)
    assert key_of(wizard) == "motive"


def test_motive_of_200_characters_is_accepted(registry, cfg):
    wizard = to_name(registry, cfg)
    wizard.submit("Борин")
    wizard.submit("м" * 200)
    assert key_of(wizard) == "means"


def to_means(registry, cfg):
    wizard = to_name(registry, cfg)
    wizard.submit("Борин")
    wizard.submit("Найти сестру.")
    return wizard


def test_means_are_split_by_commas(registry, cfg):
    wizard = to_means(registry, cfg)
    wizard.submit("лук,  смелость , друзья")
    assert wizard.state == "review"
    assert wizard.draft.means == ["лук", "смелость", "друзья"]


def test_four_means_are_refused_with_validator_text(registry, cfg):
    from ai_dm.rules.builder import hooks_problems

    wizard = to_means(registry, cfg)
    step = wizard.submit("а, б, в, г")
    assert hooks_problems("м", ["а"] * 4)[0][1] in texts(step)
    assert wizard.state == "step"


def test_no_means_are_refused(registry, cfg):
    wizard = to_means(registry, cfg)
    step = wizard.submit(" , ")
    assert texts(step).strip()
    assert wizard.state == "step"


def test_too_long_mean_is_refused(registry, cfg):
    wizard = to_means(registry, cfg)
    step = wizard.submit("с" * 121)
    assert "120" in texts(step)
    assert wizard.state == "step"


# предыстория словами (единственный ИИ-шаг)

DESCRIPTION = "акробат из бродячего цирка"


def spec_call(call_id="bg-1", **changes):
    data = {
        "type": "background_spec", "name": "Бывший цирковой акробат",
        "abilities": ["dex", "con", "cha"], "skills": ["acrobatics", "performance"],
        "tool": "thieves_tools", "feat": "alert", "equipment": ["crowbar"], "gold_cp": 1000,
        "description": "Вырос в цирке.",
    }
    data.update(changes)
    return {"id": call_id, "name": "background_spec", "input": data}


def bad_spec(call_id):
    return tools_step(spec_call(call_id, skills=["acrobatics"]))


def failing_steps():
    return [bad_spec(f"b-{i}") for i in range(app_cfg().retry.invalid_retries + 1)]


def to_words(registry, cfg, tmp_path, steps, **kw):
    wizard, adapter = make(registry, cfg, tmp_path, steps=steps, **kw)
    walk(wizard, ALL[:2])
    return wizard, adapter, wizard.submit(number_of_background_words(wizard))


def number_of_background_words(wizard):
    return "5"


def described(registry, cfg, tmp_path, steps=None, **kw):
    steps = [tools_step(spec_call())] if steps is None else steps
    wizard, adapter, _ = to_words(registry, cfg, tmp_path, steps, **kw)
    return wizard, adapter, wizard.submit(DESCRIPTION)


def failed(registry, cfg, tmp_path, steps=None, **kw):
    steps = failing_steps() if steps is None else steps
    return described(registry, cfg, tmp_path, steps, **kw)


def test_words_choice_asks_for_a_description_without_model_call(registry, cfg, tmp_path):
    from ai_dm.ui.hero_wizard import WORDS_HINT

    wizard, adapter, step = to_words(registry, cfg, tmp_path, [])
    assert WORDS_HINT in texts(step)
    assert wizard.state == "words"
    assert adapter.requests == []


def test_empty_words_repeat_the_hint_without_model_call(registry, cfg, tmp_path):
    from ai_dm.ui.hero_wizard import WORDS_HINT

    wizard, adapter, _ = to_words(registry, cfg, tmp_path, [])
    step = wizard.submit("  ")
    assert WORDS_HINT in texts(step)
    assert adapter.requests == []


def test_words_give_background_spec_in_the_draft(registry, cfg, tmp_path):
    wizard, _, _ = described(registry, cfg, tmp_path)
    assert isinstance(wizard.draft.background, BackgroundSpec)
    assert wizard.draft.background.name == "Бывший цирковой акробат"


def test_words_show_the_background_summary_as_raw_block(registry, cfg, tmp_path):
    _, _, step = described(registry, cfg, tmp_path)
    raws = [block for block in step.blocks if block.kind == "raw"]
    assert raws
    assert "Бывший цирковой акробат" in "\n".join("\n".join(b.items) for b in raws)


def test_words_go_on_to_the_next_step(registry, cfg, tmp_path):
    wizard, _, _ = described(registry, cfg, tmp_path)
    assert key_of(wizard) == "method"
    assert wizard.state == "step"


def test_words_request_carries_description_and_class(registry, cfg, tmp_path):
    _, adapter, _ = described(registry, cfg, tmp_path)
    text = adapter.requests[0].messages[0].content[0].text
    assert DESCRIPTION in text
    assert "fighter" in text
    assert [t.name for t in adapter.requests[0].tools] == ["background_spec"]


def test_words_make_one_run_id_with_hero_prefix(registry, cfg, tmp_path):
    wizard, _, _ = described(registry, cfg, tmp_path)
    assert len(wizard.run_ids) == 1
    assert wizard.run_ids[0].startswith("hero-")
    assert wizard.run_ids[0].endswith("-1")


def test_words_call_is_journaled_as_narrator_with_turn_seq_zero(registry, cfg, tmp_path):
    wizard, _, _ = described(registry, cfg, tmp_path)
    records = [
        r for r in wizard.deps.journal.read_records() if r["run_id"] == wizard.run_ids[0]
    ]
    assert records
    assert {r["role"] for r in records} == {"narrator"}
    assert {r["turn_seq"] for r in records} == {0}


def test_class_skills_after_words_exclude_the_spec_skills(registry, cfg, tmp_path):
    wizard, _, _ = described(registry, cfg, tmp_path)
    step = walk_to_key(wizard, "class_skills")
    shown = "\n".join(menu_of(step))
    assert "Акробатика" not in shown
    assert "Выступление" not in shown


def walk_to_key(wizard, key):
    # доходит «всегда первым пунктом» до шага key и возвращает его Step
    from ai_dm.game.hero_steps import STEPS

    step = None
    for _ in range(100):
        if STEPS[wizard.pos].key == key:
            return step
        explicit = wizard.draft.ability_method == "explicit"
        step = wizard.submit("10" if explicit and key == "scores" else "1")
    raise AssertionError(key)


def test_words_path_reaches_a_valid_review(registry, cfg, tmp_path):
    wizard, _, _ = described(registry, cfg, tmp_path)
    first_option_walk(wizard, started=True)
    wizard.submit("1")
    assert isinstance(wizard.sheet.choices.background, BackgroundSpec)
    assert wizard.run_ids == wizard.run_ids[:1]


def test_invalid_spec_shows_error_menu_with_pick_from_list(registry, cfg, tmp_path):
    from ai_dm.ui.hero_wizard import BACK_TO_LIST

    wizard, _, step = failed(registry, cfg, tmp_path)
    items = menu_of(step)
    assert len(items) == 3
    assert "повтор" in items[0].lower()
    assert "модел" in items[1].lower()
    assert items[2] == BACK_TO_LIST
    assert "Выбрать из списка" in BACK_TO_LIST
    assert wizard.state == "error_menu"


def test_leave_returns_to_the_background_list(registry, cfg, tmp_path):
    wizard, _, _ = failed(registry, cfg, tmp_path)
    step = wizard.submit("3")
    assert len(menu_of(step)) == 5
    assert "Солдат" in menu_of(step)
    assert key_of(wizard) == "background"
    assert wizard.state == "step"
    assert step.quit is False


def test_srd_background_is_available_after_leave(registry, cfg, tmp_path):
    wizard, _, _ = failed(registry, cfg, tmp_path)
    wizard.submit("3")
    wizard.submit(ALL[2])
    assert wizard.draft.background == "soldier"
    assert key_of(wizard) == "method"


def test_retry_makes_a_new_run_with_the_same_description(registry, cfg, tmp_path):
    steps = [*failing_steps(), tools_step(spec_call("b-ok"))]
    wizard, adapter, _ = failed(registry, cfg, tmp_path, steps)
    assert len(wizard.run_ids) == 1
    step = wizard.submit("1")
    assert len(wizard.run_ids) == 2
    assert len(set(wizard.run_ids)) == 2
    assert DESCRIPTION in adapter.requests[-1].messages[0].content[0].text
    assert isinstance(wizard.draft.background, BackgroundSpec)
    assert "Бывший цирковой акробат" in texts(step)


def test_refusal_shows_refusal_hint_and_error_menu(registry, cfg, tmp_path):
    wizard, _, step = failed(registry, cfg, tmp_path, [{"stop": "refusal"}])
    assert REFUSAL_HINT in texts(step)
    assert len(menu_of(step)) == 3


def test_invalid_failure_does_not_show_refusal_hint(registry, cfg, tmp_path):
    _, _, step = failed(registry, cfg, tmp_path)
    assert REFUSAL_HINT not in texts(step)


def test_model_switch_calls_factory_and_returns_to_error_menu(registry, cfg, tmp_path):
    spy = FactorySpy()
    wizard, _, first = failed(registry, cfg, tmp_path, adapter_factory=spy)
    options = menu_of(wizard.submit("2"))
    assert wizard.state == "model_choice"
    step = wizard.submit("1")
    provider, _, model = options[0].partition(":")
    assert spy.calls == [(provider, model)]
    assert menu_of(step) == menu_of(first)
    assert wizard.state == "error_menu"


def test_retry_after_model_switch_uses_the_new_adapter(registry, cfg, tmp_path):
    fresh = scripted([tools_step(spec_call("b-new"))])
    wizard, _, _ = failed(registry, cfg, tmp_path, adapter_factory=lambda p, m: fresh)
    wizard.submit("2")
    wizard.submit("1")
    wizard.submit("1")
    assert len(fresh.requests) == 1
    assert isinstance(wizard.draft.background, BackgroundSpec)


def test_error_menu_digit_outside_is_refused_without_model_call(registry, cfg, tmp_path):
    from ai_dm.ui.hero_session import NO_SUCH

    wizard, adapter, _ = failed(registry, cfg, tmp_path)
    count = len(adapter.requests)
    step = wizard.submit("9")
    assert NO_SUCH in texts(step)
    assert len(adapter.requests) == count
    assert wizard.state == "error_menu"


def test_cancel_in_error_menu_quits_without_sheet(registry, cfg, tmp_path):
    wizard, _, _ = failed(registry, cfg, tmp_path)
    step = wizard.submit("отмена")
    assert step.quit is True
    assert wizard.sheet is None


def test_end_of_input_in_error_menu_quits(registry, cfg, tmp_path):
    wizard, _, _ = failed(registry, cfg, tmp_path)
    assert wizard.submit(None).quit is True


def test_back_from_words_state_returns_to_the_background_menu(registry, cfg, tmp_path):
    wizard, _, _ = to_words(registry, cfg, tmp_path, [])
    step = wizard.submit("назад")
    assert wizard.state == "step"
    assert key_of(wizard) == "background"
    assert len(menu_of(step)) == 5


# заклинатели

def class_number(registry, class_id):
    from ai_dm.rules.hero_options import class_options

    return [c.id for c in class_options(registry)].index(class_id) + 1


def caster(registry, cfg, class_id, method=1):
    wizard, _ = make(registry, cfg)
    step = first_option_walk(wizard, cls=class_number(registry, class_id), method=method)
    return wizard, step


def test_wizard_chooses_all_content_cantrips_and_spells_and_4_prepared(registry, cfg):
    # лимиты волшебника 3/6/4, в контенте 1 заговор и 5 заклинаний 1 круга
    wizard, _ = caster(registry, cfg, "wizard")
    assert wizard.draft.cantrips == ["fire_bolt"]
    assert len(wizard.draft.spells) == 5
    assert len(wizard.draft.prepared) == 4
    assert set(wizard.draft.prepared) <= set(wizard.draft.spells)


def test_cleric_has_no_cantrips_in_content_and_chooses_both_spells(registry, cfg):
    # закрепляет дыру контента (у жреца нет заговоров и всего 2 заклинания): BACKLOG 16,
    # пополнение заклинаний -- отдельная партия; после неё ожидания перевернуть
    wizard, _ = caster(registry, cfg, "cleric")
    assert wizard.draft.cantrips == []
    assert sorted(wizard.draft.spells) == ["bless", "cure_wounds"]
    assert sorted(wizard.draft.prepared) == ["bless", "cure_wounds"]


def test_ranger_has_no_cantrip_step(registry, cfg):
    wizard, _ = caster(registry, cfg, "ranger")
    assert wizard.draft.cantrips == []
    assert len(wizard.draft.spells) == 2
    assert len(wizard.draft.prepared) == 2


def test_wizard_review_shows_spell_slots_line(registry, cfg):
    _, step = caster(registry, cfg, "wizard")
    assert "Заклинания (ячейки" in texts(step)


def test_wizard_accepted_sheet_has_spells_within_limits(registry, cfg):
    wizard, _ = caster(registry, cfg, "wizard")
    wizard.submit("1")
    choices = wizard.sheet.choices
    assert len(choices.spells) == 6
    assert len(choices.prepared) == 4
    assert set(choices.prepared) <= set(choices.spells)


def test_spell_menus_do_not_mix_cantrips_and_first_circle(registry, cfg):
    wizard, _ = make(registry, cfg)
    walk(wizard, ["1", str(class_number(registry, "wizard")), "1"])
    cantrips = menu_of(walk_to_key(wizard, "cantrips"))
    wizard.submit("1")
    wizard.submit("1")
    spells = menu_of(wizard.submit("1"))
    assert key_of(wizard) == "spells"
    assert cantrips
    assert spells
    assert not set(cantrips) & set(spells)


# добивка по выжившим мутантам mutmut (Б2а)

def test_method_menu_texts_are_exact(registry, cfg):
    wizard, _ = make(registry, cfg)
    step = walk(wizard, lines_before(SCRIPT, "method"))
    assert menu_of(step) == [
        "Стандартный набор (15,14,13,12,10,8)", "Покупка очков (27)", "Свободный ввод (3..20)",
    ]
    assert title_of(step) == "Метод характеристик:"


def test_menu_title_of_multi_step_is_exact(registry, cfg):
    wizard, _ = make(registry, cfg)
    step = walk(wizard, lines_before(SCRIPT, "class_skills"))
    assert title_of(step) == "Навыки класса (1 из 2):"


def test_text_step_shows_title_with_colon_as_note(registry, cfg):
    wizard, _ = make(registry, cfg)
    step = walk(wizard, lines_before(SCRIPT, "name"))
    assert [b.text for b in step.blocks if b.kind == "note"] == ["Имя героя:"]


def test_empty_line_on_name_step_only_repeats_the_hint(registry, cfg):
    wizard, _ = make(registry, cfg)
    walk(wizard, lines_before(SCRIPT, "name"))
    step = wizard.submit("")
    assert texts(step) == "Имя героя:"


def test_second_background_call_has_run_id_number_2(registry, cfg, tmp_path):
    steps = [*failing_steps(), tools_step(spec_call("b-ok"))]
    wizard, _, _ = failed(registry, cfg, tmp_path, steps)
    wizard.submit("1")
    assert wizard.run_ids[0].endswith("-1")
    assert wizard.run_ids[1].endswith("-2")


def test_back_after_words_returns_to_the_background_step_without_spec(registry, cfg, tmp_path):
    wizard, _, _ = described(registry, cfg, tmp_path)
    assert key_of(wizard) == "method"
    step = wizard.submit("назад")
    assert key_of(wizard) == "background"
    assert wizard.draft.background is None
    assert len(menu_of(step)) == 5


def forced_check(monkeypatch, codes, messages):
    # финальный sheet_check находит дефект один раз (страховка, на пути меню недостижима)
    import ai_dm.ui.hero_wizard as module

    real = module.sheet_check
    calls = []

    def fake(sheet, registry, **kw):
        calls.append(kw)
        if len(calls) == 1:
            return codes, messages
        return real(sheet, registry, **kw)

    monkeypatch.setattr(module, "sheet_check", fake)
    return calls


def test_final_check_defect_returns_to_the_step_of_the_first_code(registry, cfg, monkeypatch):
    forced_check(monkeypatch, ["motive_empty", "hero_name_taken"], ["m1", "m2"])
    wizard, _ = make(registry, cfg)
    step = walk(wizard, ALL)
    assert "m1; m2" in texts(step)
    assert wizard.state == "step"
    assert key_of(wizard) == "motive"
    assert wizard.draft.motive == ""
    assert wizard.draft.name == "Борин"
    assert "Мотив" in texts(step)


def test_final_check_defect_drops_history_of_the_step_and_after(registry, cfg, monkeypatch):
    forced_check(monkeypatch, ["hero_name_taken"], ["занято"])
    wizard, _ = make(registry, cfg)
    walk(wizard, ALL)
    assert key_of(wizard) == "name"
    wizard.submit("назад")
    assert key_of(wizard) == "gear"


def test_final_check_gets_pack_known_ids_and_taken_names(registry, cfg, monkeypatch):
    calls = forced_check(monkeypatch, ["hero_name_taken"], ["занято"])
    wizard, _ = make(registry, cfg)
    walk(wizard, ALL)
    assert calls[0]["known"] is wizard.task.known
    assert calls[0]["taken_names"] == wizard.task.taken_names


def test_final_check_defect_without_known_code_goes_to_the_first_step(registry, cfg, monkeypatch):
    forced_check(monkeypatch, ["strange"], ["странно"])
    wizard, _ = make(registry, cfg)
    walk(wizard, ALL)
    assert key_of(wizard) == "species"
    assert wizard.draft.species_id == ""


def test_final_check_defect_on_unneeded_step_goes_to_the_next_needed_one(
    registry, cfg, monkeypatch
):
    forced_check(monkeypatch, ["spells_invalid"], ["заклинания"])
    wizard, _ = make(registry, cfg)
    walk(wizard, ALL)
    assert key_of(wizard) == "species_skill"
    assert wizard.draft.species_skill == ""


# правки по ревью Б2а (b2-a-review.md: п.1, Р1-Р2, п.7)

def test_empty_menu_on_pick_step_refuses_any_text_and_records_nothing(registry, cfg, monkeypatch):
    import ai_dm.ui.hero_wizard as module
    from ai_dm.ui.hero_session import NO_SUCH

    wizard, _ = make(registry, cfg)
    wizard.start()
    monkeypatch.setattr(module, "step_options", lambda draft, registry, pos: [])
    step = wizard.submit("человек")
    assert NO_SUCH in texts(step)
    assert wizard.draft.species_id == ""
    assert key_of(wizard) == "species"


def test_empty_menu_on_multi_step_records_nothing(registry, cfg, monkeypatch):
    import ai_dm.ui.hero_wizard as module
    from ai_dm.ui.hero_session import NO_SUCH

    wizard, _ = make(registry, cfg)
    walk(wizard, lines_before(SCRIPT, "class_skills"))
    monkeypatch.setattr(module, "step_options", lambda draft, registry, pos: [])
    assert NO_SUCH in texts(wizard.submit("1"))
    assert wizard.draft.class_skills == []


def test_text_step_still_takes_a_line_as_is(registry, cfg):
    wizard, _ = make(registry, cfg)
    walk(wizard, lines_before(SCRIPT, "name"))
    wizard.submit("Борин")
    assert wizard.draft.name == "Борин"


def test_cancel_in_edit_mode_returns_to_review_without_losing_the_sheet(registry, cfg):
    from ai_dm.ui.hero_wizard import WIZARD_REVIEW_MENU

    wizard, _ = reviewed(registry, cfg)
    wizard.submit("3")
    step = wizard.submit("отмена")
    assert step.quit is False
    assert wizard.sheet is None
    assert wizard.state == "review"
    assert menu_of(step) == list(WIZARD_REVIEW_MENU)
    assert wizard.submit("1").quit is True
    assert wizard.sheet == wizard_sheet()


def test_cancel_in_edit_mode_drops_unfinished_edits_only(registry, cfg):
    wizard, _ = reviewed(registry, cfg)
    wizard.submit("3")
    wizard.submit("name = Ило")
    wizard.submit("отмена")
    wizard.submit("1")
    assert wizard.sheet.choices.name == "Ило"


def test_cancel_in_review_menu_still_quits_without_sheet(registry, cfg):
    wizard, _ = reviewed(registry, cfg)
    assert wizard.submit("отмена").quit is True
    assert wizard.sheet is None


def test_back_in_error_menu_is_not_refused_as_no_such_item(registry, cfg, tmp_path):
    from ai_dm.ui.hero_session import NO_SUCH

    wizard, _, _ = failed(registry, cfg, tmp_path)
    step = wizard.submit("назад")
    assert NO_SUCH not in texts(step)
    assert key_of(wizard) == "background"
    assert wizard.state == "step"
    assert len(menu_of(step)) == 5
