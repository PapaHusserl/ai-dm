# Б0-П1 (B0-PLAN A4), Б1а: game.hero_create -- propose_background(deps, task, ...).
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "master"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rules"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from datetime import UTC, datetime  # noqa: E402

from hero_kit import deps  # noqa: E402
from master_kit import app_cfg, scripted, text_step, tools_step  # noqa: E402
from test_builder import fighter_choices  # noqa: E402

from ai_dm.game.hero_create import propose_background  # noqa: E402
from ai_dm.master.session import TurnFailed  # noqa: E402
from ai_dm.protocol.context import BackgroundTask  # noqa: E402
from ai_dm.rules.builder import ValidationErrors, build_character  # noqa: E402
from ai_dm.state.hero import BackgroundSpec, HeroState  # noqa: E402

NOW = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)
CLASS_SKILLS = ["perception", "survival"]


def spec_call(call_id="bg-1", **changes):
    data = {
        "type": "background_spec", "name": "Бывший цирковой акробат",
        "abilities": ["dex", "con", "cha"], "skills": ["acrobatics", "performance"],
        "tool": "thieves_tools", "feat": "alert", "equipment": ["crowbar"], "gold_cp": 1000,
        "description": "Вырос в цирке.",
    }
    data.update(changes)
    return {"id": call_id, "name": "background_spec", "input": data}


def propose(registry, cfg, steps, tmp_path=None, **kw):
    adapter = scripted(steps)
    task = BackgroundTask("fighter", kw.pop("class_skills", CLASS_SKILLS))
    hero_deps = deps(adapter, registry, cfg, tmp_path, **kw)
    spec = propose_background(hero_deps, task, "акробат", "hero-1")
    extra = {"journal": hero_deps.journal, "ledger": hero_deps.ledger}
    return adapter, spec, extra


def test_valid_call_returns_background_spec(registry, cfg):
    _, spec, _ = propose(registry, cfg, [tools_step(spec_call())])
    assert isinstance(spec, BackgroundSpec)
    assert spec.name == "Бывший цирковой акробат"
    assert spec.description == "Вырос в цирке."


def test_request_carries_description_class_and_class_skills(registry, cfg):
    adapter, _, _ = propose(registry, cfg, [tools_step(spec_call())])
    text = adapter.requests[0].messages[0].content[0].text
    assert "акробат" in text
    assert "fighter" in text
    assert "perception" in text


def test_request_asks_only_for_background_spec(registry, cfg):
    adapter, _, _ = propose(registry, cfg, [tools_step(spec_call())])
    assert [t.name for t in adapter.requests[0].tools] == ["background_spec"]


def test_model_argument_selects_the_model(registry, cfg):
    model = app_cfg().alternatives.narrator.model
    adapter, _, _ = propose(registry, cfg, [tools_step(spec_call())], model=model)
    assert adapter.requests[0].model == model


def test_class_skills_default_means_no_conflict_check(registry, cfg):
    steps = [tools_step(spec_call(skills=["perception", "performance"]))]
    hero_deps = deps(scripted(steps), registry, cfg)
    spec = propose_background(hero_deps, BackgroundTask("fighter"), "x", "hero-1")
    assert spec.skills == ["perception", "performance"]


def test_journal_and_ledger_are_filled_under_narrator(registry, cfg, tmp_path):
    _, _, extra = propose(registry, cfg, [tools_step(spec_call())], tmp_path)
    records = extra["journal"].read_records()
    assert [r["role"] for r in records] == ["narrator"]
    assert records[0]["run_id"] == "hero-1"
    assert records[0]["turn_seq"] == 0
    assert [line["role"] for line in extra["ledger"].session_lines] == ["narrator"]


def test_without_journal_and_ledger_it_works(registry, cfg):
    _, spec, _ = propose(registry, cfg, [tools_step(spec_call())])
    assert spec is not None


def test_failure_goes_up_as_turn_failed(registry, cfg):
    with pytest.raises(TurnFailed) as info:
        propose(registry, cfg, [{"stop": "refusal"}])
    assert info.value.reason == "refusal"


def test_network_failure_goes_up_as_fatal(registry, cfg):
    with pytest.raises(TurnFailed) as info:
        propose(registry, cfg, [{"error": "fatal", "message": "сбой"}])
    assert info.value.reason == "fatal"


def test_text_only_answer_is_not_a_background(registry, cfg):
    budget = app_cfg().retry.invalid_retries
    with pytest.raises(TurnFailed) as info:
        propose(registry, cfg, [text_step("Просто текст.")] * (budget + 1))
    assert info.value.reason == "invalid"


# герой из предыстории модели

def test_hero_is_built_from_model_background(registry, cfg):
    _, spec, _ = propose(registry, cfg, [tools_step(spec_call())])
    choices = fighter_choices(background=spec, background_bonus={"dex": 2, "cha": 1})
    hero = build_character(choices, registry)
    assert isinstance(hero, HeroState)
    assert "alert" in hero.sheet.feats
    assert {"acrobatics", "performance"} <= set(hero.sheet.skill_proficiencies)
    assert "thieves_tools" in hero.sheet.tool_proficiencies
    assert hero.sheet.background.description == "Вырос в цирке."


def test_build_character_rejects_what_handler_would_reject(registry, cfg):
    bad = BackgroundSpec(
        name="x", abilities=["dex", "con", "cha"], skills=["perception", "performance"],
        tool="thieves_tools", feat="alert",
    )
    result = build_character(fighter_choices(background=bad), registry)
    assert isinstance(result, ValidationErrors)
    assert "class_skills_invalid" in result.codes


# Б1а (B1-PLAN A4): propose_hero_sheet, preview_lines, edit_sheet, meta, цена создания

import json  # noqa: E402

from hero_kit import base_sheet, sheet_call, sheet_task, vale_pack  # noqa: E402

from ai_dm.game.commands import money_text  # noqa: E402
from ai_dm.game.hero_create import (  # noqa: E402
    SHEET_FIELDS,
    HeroCreateDeps,
    creation_cost_line,
    edit_sheet,
    preview_lines,
    propose_hero_sheet,
    read_hero_sheet,
    run_creation,
    sheet_fields_lines,
    sheet_path,
    write_hero_sheet,
)
from ai_dm.game.sheet_text import hooks_lines  # noqa: E402
from ai_dm.rules.builder import SKILL_CONFLICT_MESSAGE, HeroSheet, sheet_check  # noqa: E402
from ai_dm.state.triggers import Narrative  # noqa: E402


def propose_sheet(registry, cfg, steps, tmp_path=None, task=None, run_id="hero-1", **kw):
    adapter = scripted(steps)
    task = task or sheet_task(vale_pack(registry))
    hero_deps = deps(adapter, registry, cfg, tmp_path, **kw)
    sheet = propose_hero_sheet(hero_deps, task, "воин-сирота", run_id)
    return adapter, sheet, hero_deps


def error_texts(request):
    blocks = request.messages[-1].content
    return [json.loads(b.content)["message"] for b in blocks if b.is_error]


def test_propose_hero_sheet_returns_hero_sheet(registry, cfg):
    _, sheet, _ = propose_sheet(registry, cfg, [tools_step(sheet_call())])
    assert isinstance(sheet, HeroSheet)
    assert sheet.choices.name == "Борин"
    assert sheet.choices.class_kit == "a"
    assert sheet.motive == "Найти сестру."


def test_propose_hero_sheet_makes_one_call_and_offers_only_the_sheet_tool(registry, cfg):
    adapter, _, _ = propose_sheet(registry, cfg, [tools_step(sheet_call())])
    assert len(adapter.requests) == 1
    assert [t.name for t in adapter.requests[0].tools] == ["hero_sheet"]


def test_propose_hero_sheet_request_carries_description_feedback_and_previous(registry, cfg):
    task = sheet_task(vale_pack(registry), feedback="мрачнее", previous={"name": "Старый"})
    adapter, _, _ = propose_sheet(registry, cfg, [tools_step(sheet_call())], task=task)
    data = json.loads(adapter.requests[0].messages[0].content[0].text)
    assert data == {
        "description": "воин-сирота", "feedback": "мрачнее", "previous": {"name": "Старый"},
    }


def test_propose_hero_sheet_world_in_reference_comes_from_pack(registry, cfg):
    adapter, _, _ = propose_sheet(registry, cfg, [tools_step(sheet_call())])
    world = json.loads(adapter.requests[0].system[1].text)["world"]
    assert world["npc_ids"] == ["grakh", "innkeeper"]
    assert world["taken_names"] == ["Гарт", "Гракх"]


def test_propose_hero_sheet_journal_is_narrator_turn_zero_hero_run(registry, cfg, tmp_path):
    _, _, hero_deps = propose_sheet(registry, cfg, [tools_step(sheet_call())], tmp_path)
    records = hero_deps.journal.read_records()
    assert [r["role"] for r in records] == ["narrator"]
    assert records[0]["run_id"] == "hero-1"
    assert records[0]["turn_seq"] == 0
    assert [line["role"] for line in hero_deps.ledger.session_lines] == ["narrator"]


def test_propose_hero_sheet_retry_writes_two_records_under_same_run(registry, cfg, tmp_path):
    steps = [tools_step(sheet_call("s-1", name="Гарт")), tools_step(sheet_call("s-2"))]
    adapter, sheet, hero_deps = propose_sheet(registry, cfg, steps, tmp_path)
    assert len(adapter.requests) == 2
    assert "'Гарт'" in error_texts(adapter.requests[1])[0]
    assert sheet.choices.name == "Борин"
    records = hero_deps.journal.read_records()
    assert [r["run_id"] for r in records] == ["hero-1", "hero-1"]


def test_propose_hero_sheet_model_selects_the_model(registry, cfg):
    model = app_cfg().alternatives.narrator.model
    adapter, _, _ = propose_sheet(registry, cfg, [tools_step(sheet_call())], model=model)
    assert adapter.requests[0].model == model


def test_propose_hero_sheet_refusal_goes_up(registry, cfg):
    with pytest.raises(TurnFailed) as info:
        propose_sheet(registry, cfg, [{"stop": "refusal"}])
    assert info.value.reason == "refusal"


def test_propose_hero_sheet_fatal_goes_up(registry, cfg):
    with pytest.raises(TurnFailed) as info:
        propose_sheet(registry, cfg, [{"error": "fatal", "message": "сбой"}])
    assert info.value.reason == "fatal"


def test_propose_hero_sheet_invalid_goes_up_after_budget(registry, cfg):
    budget = app_cfg().retry.invalid_retries
    steps = [tools_step(sheet_call(f"s-{i}", motive="")) for i in range(budget + 1)]
    with pytest.raises(TurnFailed) as info:
        propose_sheet(registry, cfg, steps)
    assert info.value.reason == "invalid"


def test_run_creation_returns_context_with_sheet(registry, cfg):
    hero_deps = deps(scripted([tools_step(sheet_call())]), registry, cfg)
    ctx = run_creation(hero_deps, sheet_task(vale_pack(registry)), "x", "hero-1")
    assert ctx.sheet is not None
    assert ctx.background is None


def test_run_creation_for_background_task_fills_background(registry, cfg):
    hero_deps = deps(scripted([tools_step(spec_call())]), registry, cfg)
    ctx = run_creation(hero_deps, BackgroundTask("fighter"), "x", "hero-1")
    assert ctx.background is not None
    assert ctx.sheet is None


def test_hero_create_deps_defaults():
    hero_deps = HeroCreateDeps(adapter=1, app_cfg=2, registry=3, cfg=4)
    assert hero_deps.journal is None
    assert hero_deps.ledger is None
    assert hero_deps.now is None
    assert hero_deps.model is None
    assert hero_deps.adapter_factory is None


# предпросмотр

def preview(registry, sheet=None, width=80):
    return preview_lines(sheet or base_sheet(), registry, width)


def test_preview_has_name_species_and_class(registry):
    first = preview(registry)[0]
    assert "Борин" in first
    assert "человек" in first
    assert "воин" in first


def test_preview_has_armor_class(registry):
    assert any("КД 17" in line for line in preview(registry))


def test_preview_has_kit_items(registry):
    text = "\n".join(preview(registry))
    assert registry.get("armor", "chain_mail").name in text
    assert registry.get("weapon", "greatsword").name in text
    assert registry.get("item", "explorers_pack").name in text


def test_preview_has_hooks_and_background_description(registry):
    lines = preview(registry)
    assert "Мотив: Найти сестру." in lines
    assert "Средства: острый ум" in lines
    assert "Возможности: o1 — отомстить" in lines
    assert "Предыстория: Бывший цирковой акробат — Вырос в бродячем цирке." in lines


def test_preview_has_money_with_kit_gold(registry):
    assert any(line.startswith("Деньги: 14 зм") for line in preview(registry))


def test_preview_for_wizard_has_spell_line(registry):
    from test_builder import wizard_choices

    sheet = base_sheet(choices=wizard_choices(class_kit="a", hero_id="hero"))
    assert any(line.startswith("Заклинания (ячейки") for line in preview(registry, sheet))


def test_preview_for_fighter_has_no_spell_line(registry):
    assert not any(line.startswith("Заклинания") for line in preview(registry))


def test_preview_without_hooks_has_no_hook_lines(registry):
    sheet = base_sheet(motive="", means=[], opportunity=[])
    sheet.choices.background.description = ""
    lines = preview(registry, sheet)
    hook_starts = ("Мотив", "Средства", "Возможности", "Предыстория")
    assert not any(line.startswith(hook_starts) for line in lines)


def test_preview_does_not_change_the_sheet(registry):
    sheet = base_sheet()
    before = sheet.model_dump_json()
    preview(registry, sheet)
    assert sheet.model_dump_json() == before


def test_preview_lines_fit_width(registry):
    assert all(len(line) <= 40 for line in preview(registry, width=40))


# hooks_lines

def test_hooks_lines_of_built_hero(registry):
    from ai_dm.campaign.build import apply_hooks
    from ai_dm.rules.builder import build_character

    sheet = base_sheet()
    hero = build_character(sheet.choices, registry)
    apply_hooks(hero, sheet)
    assert hooks_lines(hero) == [
        "Предыстория: Бывший цирковой акробат — Вырос в бродячем цирке.",
        "Мотив: Найти сестру.",
        "Средства: острый ум",
        "Возможности: o1 — отомстить",
    ]


def test_hooks_lines_empty_for_plain_hero(registry):
    from ai_dm.rules.builder import build_character

    hero = build_character(base_sheet().choices, registry)
    hero.sheet.background.description = ""
    assert hooks_lines(hero) == []


# ручная правка

def edited(line, sheet=None):
    return edit_sheet(sheet or base_sheet(), line)


def test_edit_name(registry):
    result = edited("name = Ило")
    assert isinstance(result, HeroSheet)
    assert result.choices.name == "Ило"


def test_edit_does_not_change_the_original(registry):
    sheet = base_sheet()
    edited("name = Ило", sheet)
    assert sheet.choices.name == "Борин"


def test_edit_keeps_everything_else(registry):
    result = edited("name = Ило")
    expected = base_sheet().model_dump()
    expected["choices"]["name"] = "Ило"
    assert result.model_dump() == expected


def test_edit_ability_score_and_method(registry):
    result = edited("str = 16", edited("method = explicit"))
    assert result.choices.ability_method == "explicit"
    assert result.choices.ability_scores["str"] == 16
    assert result.choices.ability_scores["dex"] == 13


def test_edit_int_score_uses_int_key(registry):
    assert edited("int = 12").choices.ability_scores["int"] == 12


def test_edit_bad_number_gives_text(registry):
    result = edited("str = много")
    assert isinstance(result, str)
    assert "много" in result


def test_edit_bonus(registry):
    result = edited("bonus = dex+2, con+1")
    assert result.choices.background_bonus == {"dex": 2, "con": 1}


def test_edit_bonus_three_ones(registry):
    result = edited("bonus = dex+1, con+1, cha+1")
    assert result.choices.background_bonus == {"dex": 1, "con": 1, "cha": 1}


def test_edit_bonus_bad_format_gives_text(registry):
    assert isinstance(edited("bonus = dex 2"), str)


def test_edit_lists_are_comma_separated(registry):
    result = edited("class_skills = perception, acrobatics")
    assert result.choices.class_skills == ["perception", "acrobatics"]
    masteries = edited("masteries = longsword, dagger").choices.weapon_masteries
    assert masteries == ["longsword", "dagger"]


def test_edit_means(registry):
    assert edited("means = а, б").means == ["а", "б"]


def test_edit_motive(registry):
    assert edited("motive = Отомстить за брата.").motive == "Отомстить за брата."


def test_edit_empty_motive_gives_empty_motive(registry):
    assert edited("motive =").motive == ""


def test_edit_style_and_kit(registry):
    assert edited("style =").choices.fighting_style is None
    assert edited("style = defense").choices.fighting_style == "defense"
    assert edited("kit = b").choices.class_kit == "b"


def test_edit_species_and_class(registry):
    assert edited("species = elf").choices.species_id == "elf"
    assert edited("class = rogue").choices.class_id == "rogue"


def test_edit_spells_prepared_and_gear(registry):
    result = edited("gear = gold", edited("prepared = a", edited("spells = a, b")))
    assert result.choices.spells == ["a", "b"]
    assert result.choices.prepared == ["a"]
    assert result.choices.background_gear == "gold"


def test_edit_species_skill_and_feat(registry):
    result = edited("species_skill = stealth", edited("species_feat = alert"))
    assert result.choices.species_choices == {"skill": "stealth", "feat": "alert"}


def test_edit_species_skill_none_removes_choice(registry):
    assert "skill" not in edited("species_skill = none").choices.species_choices
    assert "feat" not in edited("species_feat =").choices.species_choices


def test_edit_feat_skills_go_under_origin_feat_key(registry):
    result = edited("species_feat_skills = history, arcana, investigation")
    assert result.choices.feat_choices["skilled"] == ["history", "arcana", "investigation"]


def test_edit_feat_skills_of_background_feat(registry):
    sheet = edited("bg_feat = skilled")
    result = edited("feat_skills = history, arcana, investigation", sheet)
    assert result.choices.feat_choices["skilled"] == ["history", "arcana", "investigation"]


def test_edit_background_fields(registry):
    result = edited("bg_name = Бродяга")
    result = edited("bg_abilities = str, dex, con", result)
    result = edited("bg_skills = stealth, survival", result)
    result = edited("bg_tool = dice_set", result)
    result = edited("bg_feat = alert", result)
    result = edited("bg_equipment = crowbar, rope", result)
    result = edited("bg_gold = 500", result)
    result = edited("bg_description = Новая.", result)
    spec = result.choices.background
    assert spec.name == "Бродяга"
    assert spec.abilities == ["str", "dex", "con"]
    assert spec.skills == ["stealth", "survival"]
    assert spec.tool == "dice_set"
    assert spec.feat == "alert"
    assert spec.equipment == ["crowbar", "rope"]
    assert spec.gold_cp == 500
    assert spec.description == "Новая."


def test_edit_bg_gold_bad_number_gives_text(registry):
    assert isinstance(edited("bg_gold = мало"), str)


def test_edit_opportunity_clear(registry):
    assert edited("opportunity =").opportunity == []


def test_edit_opportunity_narrative(registry):
    result = edited("opportunity = o1: герой узнаёт о сестре -> отомстить")
    [trigger] = result.opportunity
    assert trigger.id == "o1"
    assert trigger.if_ == Narrative(text="герой узнаёт о сестре")
    assert trigger.then == "отомстить"
    assert trigger.once is True


def test_edit_opportunity_replaces_old_triggers(registry):
    result = edited("opportunity = o9: условие -> дело")
    assert [t.id for t in result.opportunity] == ["o9"]


def test_edit_opportunity_bad_format_gives_text(registry):
    assert isinstance(edited("opportunity = без стрелки"), str)
    assert isinstance(edited("opportunity = : условие -> дело"), str)
    assert isinstance(edited("opportunity = id: -> дело"), str)


def test_edit_unknown_field_lists_fields(registry):
    result = edited("hp = 100")
    assert isinstance(result, str)
    for key in ("name", "str", "bonus", "motive", "opportunity", "bg_description"):
        assert key in result


def test_edit_line_without_equals_lists_fields(registry):
    result = edited("name Ило")
    assert isinstance(result, str)
    assert "name" in result


def test_edit_field_name_is_case_insensitive_and_trimmed(registry):
    assert edited("  NAME   =   Ило  ").choices.name == "Ило"


def test_edit_value_may_contain_equals_sign(registry):
    assert edited("motive = a = b").motive == "a = b"


def test_edit_bad_field_value_for_choice_gives_pydantic_text(registry):
    result = edited("method = roll")
    assert isinstance(result, str)
    assert "roll" in result


def test_every_field_in_table_can_be_read_for_hints(registry):
    lines = sheet_fields_lines(base_sheet())
    assert [line.split(" = ")[0] for line in lines] == list(SHEET_FIELDS)


def test_every_field_can_be_read_for_srd_background_with_dash_for_bg_fields(registry):
    from test_builder import fighter_choices

    lines = sheet_fields_lines(base_sheet(choices=fighter_choices()))
    assert [line.split(" = ")[0] for line in lines] == list(SHEET_FIELDS)
    bg = [line for line in lines if line.startswith("bg_")]
    assert bg
    assert all(line.endswith(" = —") for line in bg)
    assert "name = Арн" in lines


def test_sheet_fields_lines_show_current_values(registry):
    lines = sheet_fields_lines(base_sheet())
    assert "name = Борин" in lines
    assert "str = 15" in lines
    assert "int = 8" in lines
    assert "bonus = dex+2, con+1" in lines
    assert "class_skills = perception, survival" in lines
    assert "style = defense" in lines
    assert "kit = a" in lines
    assert "motive = Найти сестру." in lines
    assert "means = острый ум" in lines
    assert "bg_tool = thieves_tools" in lines
    assert "bg_gold = 1000" in lines
    assert "opportunity = o1 -> отомстить (правка заменяет весь список)" in lines


# правка и путь модели дают те же тексты (критерий Б1)

def test_manual_skill_conflict_gives_same_text_as_model_path(registry, cfg):
    changes = {"class_skills": ["perception", "acrobatics"]}
    steps = [tools_step(sheet_call("s-1", **changes)), tools_step(sheet_call("s-2"))]
    adapter, _, _ = propose_sheet(registry, cfg, steps)
    model_text = error_texts(adapter.requests[1])[0]
    manual = edited("class_skills = perception, acrobatics")
    codes, messages = sheet_check(manual, registry)
    assert codes == ["class_skills_invalid"]
    assert messages == [SKILL_CONFLICT_MESSAGE]
    assert "; ".join(messages) == model_text


def test_manual_empty_motive_gives_same_text_as_model_path(registry, cfg):
    steps = [tools_step(sheet_call("s-1", motive="")), tools_step(sheet_call("s-2"))]
    adapter, _, _ = propose_sheet(registry, cfg, steps)
    _, messages = sheet_check(edited("motive ="), registry)
    assert "; ".join(messages) == error_texts(adapter.requests[1])[0]


def test_manual_taken_name_gives_same_text_as_model_path(registry, cfg):
    steps = [tools_step(sheet_call("s-1", name="Гарт")), tools_step(sheet_call("s-2"))]
    task = sheet_task(vale_pack(registry))
    adapter, _, _ = propose_sheet(registry, cfg, steps, task=task)
    _, messages = sheet_check(edited("name = Гарт"), registry, taken_names=task.taken_names)
    assert "; ".join(messages) == error_texts(adapter.requests[1])[0]


def test_manual_two_defects_give_same_joined_text_as_model_path(registry, cfg):
    scores = {"str": 16, "dex": 13, "con": 14, "int": 8, "wis": 10, "cha": 12}
    steps = [
        tools_step(sheet_call("s-1", ability_scores=scores, motive="")),
        tools_step(sheet_call("s-2")),
    ]
    adapter, _, _ = propose_sheet(registry, cfg, steps)
    manual = edited("motive =", edited("str = 16"))
    _, messages = sheet_check(manual, registry)
    assert len(messages) == 2
    assert "; ".join(messages) == error_texts(adapter.requests[1])[0]


def test_manual_valid_edit_passes_sheet_check(registry):
    assert sheet_check(edited("name = Ило"), registry) == ([], [])


# meta

def test_sheet_path_is_in_meta(tmp_path):
    assert sheet_path(tmp_path, "w1") == tmp_path / "w1" / "meta" / "hero_sheet.json"


def test_write_then_read_hero_sheet_round_trip(tmp_path):
    sheet = base_sheet()
    write_hero_sheet(tmp_path, "w1", sheet)
    assert read_hero_sheet(tmp_path, "w1") == sheet


def test_written_hero_sheet_is_readable_json_in_russian(tmp_path):
    write_hero_sheet(tmp_path, "w1", base_sheet())
    text = sheet_path(tmp_path, "w1").read_text(encoding="utf-8")
    assert "Найти сестру." in text
    assert json.loads(text)["choices"]["name"] == "Борин"


def test_read_hero_sheet_without_file_is_none(tmp_path):
    assert read_hero_sheet(tmp_path, "w1") is None


def test_write_hero_sheet_overwrites(tmp_path):
    write_hero_sheet(tmp_path, "w1", base_sheet())
    write_hero_sheet(tmp_path, "w1", edited("name = Ило"))
    assert read_hero_sheet(tmp_path, "w1").choices.name == "Ило"


def test_hero_sheets_of_two_worlds_are_separate(tmp_path):
    write_hero_sheet(tmp_path, "w1", base_sheet())
    assert read_hero_sheet(tmp_path, "w2") is None


# цена создания

def test_creation_cost_line_counts_only_given_runs(registry, cfg, tmp_path):
    steps = [tools_step(sheet_call("s-1", motive="")), tools_step(sheet_call("s-2"))]
    _, _, hero_deps = propose_sheet(registry, cfg, steps, tmp_path)
    journal = hero_deps.journal
    records = journal.read_records()
    total = sum(r["cost_nano"] for r in records)
    line = creation_cost_line(journal, ["hero-1"])
    assert line == f"Создание героя: {money_text(total)} (2 вызовов)"


def test_creation_cost_line_ignores_other_runs(registry, cfg, tmp_path):
    steps = [tools_step(sheet_call())]
    _, _, hero_deps = propose_sheet(registry, cfg, steps, tmp_path)
    other = deps(scripted([tools_step(sheet_call())]), registry, cfg, tmp_path)
    propose_hero_sheet(other, sheet_task(vale_pack(registry)), "x", "run-turn-1")
    line = creation_cost_line(hero_deps.journal, ["hero-1"])
    assert line.endswith("(1 вызовов)")


def test_creation_cost_line_sums_several_hero_runs(registry, cfg, tmp_path):
    adapter = scripted([tools_step(sheet_call("a")), tools_step(sheet_call("b"))])
    hero_deps = deps(adapter, registry, cfg, tmp_path)
    task = sheet_task(vale_pack(registry))
    propose_hero_sheet(hero_deps, task, "x", "hero-1")
    propose_hero_sheet(hero_deps, task, "x", "hero-2")
    one = creation_cost_line(hero_deps.journal, ["hero-1"])
    both = creation_cost_line(hero_deps.journal, ["hero-1", "hero-2"])
    assert one.endswith("(1 вызовов)")
    assert both.endswith("(2 вызовов)")


def test_creation_cost_line_without_runs_is_zero(registry, cfg, tmp_path):
    _, _, hero_deps = propose_sheet(registry, cfg, [tools_step(sheet_call())], tmp_path)
    line = creation_cost_line(hero_deps.journal, [])
    assert line == f"Создание героя: {money_text(0)} (0 вызовов)"


# Б1а: добавки по разбору мутантов

def test_run_creation_keeps_cfg_of_deps(registry, cfg):
    hero_deps = deps(scripted([tools_step(sheet_call())]), registry, cfg)
    ctx = run_creation(hero_deps, sheet_task(vale_pack(registry)), "x", "hero-1")
    assert ctx.cfg is cfg
    assert ctx.registry is registry


def test_run_creation_journal_uses_now_of_deps(registry, cfg, tmp_path):
    from master_kit import NOW as KIT_NOW

    hero_deps = deps(scripted([tools_step(sheet_call())]), registry, cfg, tmp_path)
    run_creation(hero_deps, sheet_task(vale_pack(registry)), "x", "hero-1")
    assert hero_deps.journal.read_records()[0]["ts"] == NOW.isoformat()
    assert NOW != KIT_NOW


def test_sheet_fields_lines_without_species_feat_show_dash_for_its_picks(registry):
    sheet = base_sheet()
    choices = sheet.choices.model_copy(update={"species_choices": {"skill": "stealth"}})
    lines = sheet_fields_lines(sheet.model_copy(update={"choices": choices}))
    assert "species_feat_skills = —" in lines
    assert "species_skill = stealth" in lines


def test_edit_unknown_field_message_starts_with_hint_and_joins_fields_with_commas(registry):
    result = edited("hp = 100")
    assert result.startswith("Неизвестное поле. Поля: name, species, class, method, str, ")
    assert result.endswith(", opportunity")


def test_written_hero_sheet_keeps_trigger_condition_under_if_key(tmp_path):
    write_hero_sheet(tmp_path, "w1", base_sheet())
    data = json.loads(sheet_path(tmp_path, "w1").read_text(encoding="utf-8"))
    assert data["opportunity"][0]["if"] == {"type": "narrative", "text": "герой узнаёт о сестре"}
    assert "if_" not in data["opportunity"][0]


def test_hooks_lines_join_several_opportunities_with_semicolon(registry):
    from hero_kit import narrative_trigger

    from ai_dm.campaign.build import apply_hooks
    from ai_dm.rules.builder import build_character

    sheet = base_sheet(opportunity=[
        narrative_trigger("o1", then="первое"), narrative_trigger("o2", then="второе"),
    ])
    hero = build_character(sheet.choices, registry)
    apply_hooks(hero, sheet)
    assert "Возможности: o1 — первое; o2 — второе" in hooks_lines(hero)


def test_preview_equipment_line_is_exact(registry):
    assert "Экипировка: доспех: Кольчуга; в руках: Двуручный меч" in preview(registry)


def test_preview_equipment_rows_wrap_at_narrow_width_with_label_first(registry):
    lines = preview(registry, width=30)
    start = lines.index("Экипировка: доспех: Кольчуга")
    assert lines[start + 1].strip() == "в руках: Двуручный меч"


def test_preview_spell_line_has_slots_and_comma_separated_names(registry):
    from test_builder import wizard_choices

    choices = wizard_choices(
        class_kit="a", hero_id="hero", spells=["fire_bolt", "magic_missile"],
        prepared=["magic_missile"],
    )
    lines = preview(registry, base_sheet(choices=choices))
    [line] = [x for x in lines if x.startswith("Заклинания (ячейки")]
    names = [registry.get("spell", s).name for s in ("fire_bolt", "magic_missile")]
    prefix = "Заклинания (ячейки 1 круг: ●● (2/2)): "
    assert line.startswith(prefix)
    assert sorted(line[len(prefix):].split(", ")) == sorted(names)


def test_edit_bonus_without_number_gives_format_text(registry):
    for line in ("bonus = dex+", "bonus = dex+x", "bonus = dex 2"):
        result = edited(line)
        assert isinstance(result, str), line
        assert "бонус: формат" in result


def test_edit_species_feat_skills_without_species_feat_gives_text(registry):
    sheet = edited("species_feat =")
    result = edited("species_feat_skills = a, b, c", sheet)
    assert result == "у вида нет выбора черты (species_feat)"


def test_edit_same_feat_twice_puts_species_picks_under_second_key(registry):
    sheet = edited("bg_feat = skilled")
    sheet = edited("feat_skills = history, arcana, investigation", sheet)
    result = edited("species_feat_skills = medicine, religion, nature", sheet)
    assert result.choices.feat_choices == {
        "skilled": ["history", "arcana", "investigation"],
        "skilled#2": ["medicine", "religion", "nature"],
    }


def test_edit_opportunity_with_arrow_but_no_colon_gives_format_text(registry):
    result = edited("opportunity = o1 условие -> дело")
    assert isinstance(result, str)
    assert "формат" in result


def test_edit_opportunity_with_colon_but_no_arrow_gives_format_text(registry):
    result = edited("opportunity = o1: условие без стрелки")
    assert isinstance(result, str)
    assert "формат" in result


def test_edit_opportunity_trims_spaces_around_parts(registry):
    [trigger] = edited("opportunity =  o2 :  условие  ->  дело  ").opportunity
    assert (trigger.id, trigger.then) == ("o2", "дело")
    assert trigger.if_ == Narrative(text="условие")


def test_edit_bg_field_of_catalog_background_names_the_reason(registry):
    from test_builder import fighter_choices

    result = edit_sheet(base_sheet(choices=fighter_choices()), "bg_name = X")
    assert "bg_*" in result


def test_sheet_fields_lines_join_several_opportunities_and_show_empty_style(registry):
    from hero_kit import narrative_trigger

    sheet = base_sheet(opportunity=[
        narrative_trigger("o1", then="первое"), narrative_trigger("o2", then="второе"),
    ])
    choices = sheet.choices.model_copy(update={"fighting_style": None})
    lines = sheet_fields_lines(sheet.model_copy(update={"choices": choices}))
    assert "opportunity = o1 -> первое; o2 -> второе (правка заменяет весь список)" in lines
    assert "style = " in lines


def test_edit_empty_feat_skills_removes_the_picks(registry):
    result = edited("species_feat_skills =")
    assert "skilled" not in result.choices.feat_choices
