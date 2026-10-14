# Критерий Б1 (B1-PLAN, раздел B, Б1а): герой на лету, ИИ-путь, на мок-модели, без CLI.
# Описание -> невалидный лист (стандартный набор не тот + имя NPC пака) -> отказ инструмента с
# обоими текстами -> валидный лист -> ручная правка с ошибкой (тот же текст, что у модели) ->
# правка имени ->
# мир с пресетом -> один ход -> сейв -> загрузка (герой, набор, motive/means/opportunity целы).
# Журнал: записи hero-... рядом с записями хода; /cost видит создание. Живых вызовов нет.
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unit" / "game"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unit" / "ui"))

from game_kit import SAVED_AT, core_dump, make_app  # noqa: E402
from hero_kit import base_sheet, deps, sheet_call, sheet_task, vale_pack  # noqa: E402
from master_kit import app_cfg, scripted, text_step, tools_step  # noqa: E402
from ui_kit import cli  # noqa: E402

from ai_dm.campaign.presets import apply_preset, load_presets  # noqa: E402
from ai_dm.game.hero_create import (  # noqa: E402
    creation_cost_line,
    edit_sheet,
    propose_hero_sheet,
    read_hero_sheet,
    write_hero_sheet,
)
from ai_dm.game.starter import new_world_from_pack  # noqa: E402
from ai_dm.master.session import TurnFailed  # noqa: E402
from ai_dm.persistence.store import load_slot  # noqa: E402
from ai_dm.rules.builder import SKILL_CONFLICT_MESSAGE, HeroSheet, sheet_check  # noqa: E402

SCORES_WRONG = {"str": 16, "dex": 13, "con": 14, "int": 8, "wis": 10, "cha": 12}
TURN_TEXT = "Огонь в очаге трещит, и трактирщик поднимает глаза."


def error_texts(request):
    blocks = request.messages[-1].content
    return [json.loads(b.content)["message"] for b in blocks if b.is_error]


def propose(registry, cfg, tmp_path, steps, task=None):
    adapter = scripted(steps)
    task = task or sheet_task(vale_pack(registry))
    hero_deps = deps(adapter, registry, cfg, tmp_path)
    sheet = propose_hero_sheet(hero_deps, task, "воин-сирота ищет сестру", "hero-1")
    return adapter, sheet, hero_deps, task


def test_invalid_sheet_is_refused_with_both_texts_then_valid_sheet_is_accepted(
    registry, cfg, tmp_path
):
    steps = [
        tools_step(sheet_call("s-1", ability_scores=SCORES_WRONG, name="Гарт")),
        tools_step(sheet_call("s-2")),
    ]
    adapter, sheet, _, _ = propose(registry, cfg, tmp_path, steps)
    assert len(adapter.requests) == 2
    [text] = error_texts(adapter.requests[1])
    assert "стандартный набор" in text
    assert "'Гарт'" in text
    assert "; " in text
    assert isinstance(sheet, HeroSheet)
    assert sheet.choices.name == "Борин"


def test_manual_edit_error_has_same_text_as_model_error(registry, cfg, tmp_path):
    steps = [
        tools_step(sheet_call("s-1", class_skills=["perception", "acrobatics"])),
        tools_step(sheet_call("s-2")),
    ]
    adapter, sheet, _, task = propose(registry, cfg, tmp_path, steps)
    model_text = error_texts(adapter.requests[1])[0]
    edited = edit_sheet(sheet, "class_skills = perception, acrobatics")
    codes, messages = sheet_check(
        edited, registry, known=task.known, taken_names=task.taken_names
    )
    assert codes == ["class_skills_invalid"]
    assert messages == [SKILL_CONFLICT_MESSAGE]
    assert "; ".join(messages) == model_text


def test_manual_name_edit_is_valid(registry, cfg, tmp_path):
    _, sheet, _, task = propose(registry, cfg, tmp_path, [tools_step(sheet_call())])
    edited = edit_sheet(sheet, "name = Ило")
    assert sheet_check(edited, registry, known=task.known, taken_names=task.taken_names) == (
        [], [],
    )


def test_manual_edit_to_npc_name_is_refused_like_for_model(registry, cfg, tmp_path):
    steps = [tools_step(sheet_call("s-1", name="гракх")), tools_step(sheet_call("s-2"))]
    adapter, sheet, _, task = propose(registry, cfg, tmp_path, steps)
    model_text = error_texts(adapter.requests[1])[0]
    edited = edit_sheet(sheet, "name = гракх")
    _, messages = sheet_check(edited, registry, known=task.known, taken_names=task.taken_names)
    assert "; ".join(messages) == model_text


def test_full_path_creation_world_turn_save_load(registry, cfg, tmp_path):
    steps = [
        tools_step(sheet_call("s-1", ability_scores=SCORES_WRONG, name="Гарт")),
        tools_step(sheet_call("s-2")),
    ]
    _, sheet, hero_deps, task = propose(registry, cfg, tmp_path, steps)
    sheet = edit_sheet(sheet, "name = Ило")
    assert sheet_check(sheet, registry, known=task.known, taken_names=task.taken_names) == ([], [])
    write_hero_sheet(tmp_path, "w1", sheet)
    pack = vale_pack(registry)
    bundle = new_world_from_pack(
        registry, cfg, pack, hero=sheet, seed=7, world_id="w1", saved_at=SAVED_AT,
        preset_id="heroic",
    )
    assert bundle.world.tone == apply_preset(pack.manifest.tone, load_presets()["heroic"])
    app = make_app(registry, tmp_path, scripted([text_step(TURN_TEXT)]), bundle=bundle)
    reply = app.handle("Осматриваюсь")
    assert reply.narration == TURN_TEXT
    assert app.pending is None
    app.save_current("auto")
    loaded = load_slot(tmp_path, "w1", "auto")
    assert core_dump(loaded) == core_dump(app.bundle)
    hero = loaded.heroes[0]
    assert hero.id == "hero"
    assert hero.name == "Ило"
    assert hero.sheet.class_id == "fighter"
    assert hero.location_id == "lame_goose"
    assert {e.item_id for e in hero.inventory} >= {"chain_mail", "greatsword", "explorers_pack"}
    assert hero.equipped.armor == "chain_mail"
    # золото предыстории (1000) и набора «a» воина (400): так считает движок
    assert hero.money_cp == sheet.choices.background.gold_cp + 400
    assert hero.motive == "Найти сестру."
    assert hero.means == ["острый ум"]
    assert [t.id for t in hero.opportunity] == ["o1"]
    assert hero.opportunity[0].then == "отомстить"
    assert loaded.world.tone == bundle.world.tone
    assert read_hero_sheet(tmp_path, "w1") == sheet


def test_journal_has_two_hero_records_and_turn_records(registry, cfg, tmp_path):
    steps = [tools_step(sheet_call("s-1", motive="")), tools_step(sheet_call("s-2"))]
    _, sheet, _, _ = propose(registry, cfg, tmp_path, steps)
    bundle = new_world_from_pack(
        registry, cfg, vale_pack(registry), hero=sheet, seed=7, world_id="w1", saved_at=SAVED_AT
    )
    app = make_app(registry, tmp_path, scripted([text_step(TURN_TEXT)]), bundle=bundle)
    app.handle("Осматриваюсь")
    records = app.journal.read_records()
    hero_records = [r for r in records if r["run_id"].startswith("hero-")]
    turn_records = [r for r in records if not r["run_id"].startswith("hero-")]
    assert len(hero_records) == 2
    assert {r["role"] for r in hero_records} == {"narrator"}
    assert {r["turn_seq"] for r in hero_records} == {0}
    assert len(turn_records) >= 1
    assert creation_cost_line(app.journal, ["hero-1"]).endswith("(2 вызовов)")


def test_cost_command_sees_creation_calls(registry, cfg, tmp_path):
    _, sheet, hero_deps, _ = propose(registry, cfg, tmp_path, [tools_step(sheet_call())])
    bundle = new_world_from_pack(
        registry, cfg, vale_pack(registry), hero=sheet, seed=7, world_id="w1", saved_at=SAVED_AT
    )
    app = make_app(registry, tmp_path, scripted([text_step(TURN_TEXT)]), bundle=bundle)
    app.handle("Осматриваюсь")
    lines = [json.loads(t) for t in app.ledger.path.read_text(encoding="utf-8").splitlines()]
    assert len(hero_deps.ledger.session_lines) == 1
    assert [line["role"] for line in lines] == ["narrator", "narrator"]
    assert lines[0]["call_id"].startswith("hero-1")
    report = app.ledger.report(app.now().date())
    assert list(report.world.by_role) == ["narrator"]
    assert "narrator" in "\n".join(app.handle("/cost").lines)


def test_refusal_at_creation_fails_with_refusal(registry, cfg, tmp_path):
    with pytest.raises(TurnFailed) as info:
        propose(registry, cfg, tmp_path, [{"stop": "refusal"}])
    assert info.value.reason == "refusal"
    assert info.value.report_tags == ["refusal"]


def test_three_invalid_sheets_in_a_row_fail_as_invalid(registry, cfg, tmp_path):
    budget = app_cfg().retry.invalid_retries
    steps = [tools_step(sheet_call(f"s-{i}", motive="")) for i in range(budget + 1)]
    with pytest.raises(TurnFailed) as info:
        propose(registry, cfg, tmp_path, steps)
    assert info.value.reason == "invalid"


def test_two_invalid_then_valid_sheet_still_passes(registry, cfg, tmp_path):
    steps = [
        tools_step(sheet_call("s-1", motive="")), tools_step(sheet_call("s-2", motive="")),
        tools_step(sheet_call("s-3")),
    ]
    adapter, sheet, _, _ = propose(registry, cfg, tmp_path, steps)
    assert len(adapter.requests) == 3
    assert sheet is not None
    assert sheet.motive == "Найти сестру."


def test_creation_without_tool_fails_as_invalid(registry, cfg, tmp_path):
    budget = app_cfg().retry.invalid_retries
    steps = [text_step("Расскажу своими словами.")] * (budget + 1)
    with pytest.raises(TurnFailed) as info:
        propose(registry, cfg, tmp_path, steps)
    assert info.value.reason == "invalid"


def test_canonical_sheet_helper_matches_model_path(registry, cfg, tmp_path):
    _, sheet, _, _ = propose(registry, cfg, tmp_path, [tools_step(sheet_call())])
    expected = base_sheet().choices.model_copy(update={"hero_id": "h1"})
    assert sheet.choices.model_dump() == expected.model_dump()
    assert sheet.opportunity == base_sheet().opportunity


# Б1б: один и тот же мок-скрипт -- простой режим (main + ScriptedInput) и TUI (HeroCreateApp, Pilot)
# дают одного и того же героя (образец test_stage5_tui)

SHEET_SCRIPT = Path(__file__).resolve().parents[1] / "fixtures" / "scripts" / "hero_sheet.yaml"
DESCRIPTION = "воин-сирота ищет сестру"


def hero_dump(bundle):
    return json.dumps(
        [json.loads(h.model_dump_json()) for h in bundle.heroes], sort_keys=True,
        ensure_ascii=False,
    )


def simple_hero(tmp_path):
    root = tmp_path / "simple"
    argv = ["--new", "--world", "w1", "--seed", "7", "--mock", str(SHEET_SCRIPT),
            "--saves", str(root)]
    code, _ = cli(argv, ["4", "1", "1", DESCRIPTION, "1", "/quit"], env={})
    assert code == 0
    return load_slot(root, "w1", "auto"), read_hero_sheet(root, "w1")


def tui_sheet(registry, cfg, tmp_path):
    import asyncio

    from ai_dm.llm.mock import ScriptedAdapter, load_script
    from ai_dm.ui.hero_session import HeroSession
    from ai_dm.ui.tui.create import HeroCreateApp

    adapter = ScriptedAdapter(load_script(SHEET_SCRIPT))
    session = HeroSession(
        deps(adapter, registry, cfg, tmp_path / "tui"), sheet_task(vale_pack(registry)), 80
    )
    app = HeroCreateApp(session)

    async def scenario():
        async with app.run_test(size=(140, 40)) as pilot:
            await pilot.pause()
            for line in (DESCRIPTION, "1"):
                app.query_one("#input").value = line
                await pilot.press("enter")
                await app.workers.wait_for_complete()
                await pilot.pause()

    asyncio.run(scenario())
    return app.return_value


def test_tui_and_simple_creation_give_the_same_sheet(registry, cfg, tmp_path):
    _, simple_sheet = simple_hero(tmp_path)
    sheet = tui_sheet(registry, cfg, tmp_path)
    assert isinstance(sheet, HeroSheet)
    assert sheet == simple_sheet


def test_tui_and_simple_creation_give_the_same_hero(registry, cfg, tmp_path):
    simple, _ = simple_hero(tmp_path)
    sheet = tui_sheet(registry, cfg, tmp_path)
    bundle = new_world_from_pack(
        registry, cfg, vale_pack(registry), hero=sheet, seed=7, world_id="w1", saved_at=SAVED_AT
    )
    assert hero_dump(bundle) == hero_dump(simple)


# Критерий Б3 (B3-PLAN, раздел B; груминг «Готово», п. 7 + догруминг): import пака из выжимки
# на мок-модели. (1) невалидный pack (битая ссылка, затем конфликт 5.3) -> отказ строками ->
# валидный -> файлы в campaigns/<id>/ -> load_pack без ошибок, collect_conflicts пуст -> новый
# мир с героем на лету -> ход -> сейв/загрузка; повторный import в тот же id -- отказ, файлы
# целы; 3 невалидных -- меню 2.2, на диске ничего; refusal -- подсказка и меню. (2) три
# невалидные предыстории подряд с разными нарушениями -> invalid; две + валидная -> проходит.
# (3) пресет grim: абзац пресета в кэшируемом блоке system, два хода -- префикс байт-в-байт.
# Живых вызовов нет.
import yaml  # noqa: E402
from import_kit import (  # noqa: E402
    PACK_ID,
    bad_pack_call,
    conflict_pack_call,
    import_deps,
    import_task,
    pack_call,
    staged,
    summary_text,
)
from test_stage6b_background import spec_call  # noqa: E402

from ai_dm.campaign.loader import load_pack  # noqa: E402
from ai_dm.campaign.uniqueness import collect_conflicts  # noqa: E402
from ai_dm.core.rng import Rng  # noqa: E402
from ai_dm.game.hero_create import propose_background  # noqa: E402
from ai_dm.game.pack_import import finish_import, run_import  # noqa: E402
from ai_dm.game.turn import REFUSAL_HINT  # noqa: E402
from ai_dm.master.prompt import PromptBuilder  # noqa: E402
from ai_dm.protocol.context import BackgroundTask, TurnContext  # noqa: E402
from ai_dm.rules.builder import background_check  # noqa: E402
from ai_dm.state.world import WorldState  # noqa: E402

SCRIPTS = Path(__file__).resolve().parents[1] / "fixtures" / "scripts"
IMPORT_SCRIPT = SCRIPTS / "import_pack.yaml"


def run_staged_import(registry, cfg, tmp_path, steps):
    campaigns, folder = staged(tmp_path)
    adapter = scripted(steps)
    import_deps_ = import_deps(adapter, registry, cfg, folder)
    ctx = run_import(import_deps_, import_task(), summary_text(), "import-1", folder)
    return adapter, ctx, campaigns, folder


def write_steps(path, steps):
    path.write_text(yaml.safe_dump({"steps": steps}, allow_unicode=True), encoding="utf-8")
    return path


def cli_import(tmp_path, script=IMPORT_SCRIPT, lines=()):
    summary = tmp_path / "summary.txt"
    summary.write_text(summary_text(), encoding="utf-8")
    campaigns = tmp_path / "campaigns"
    campaigns.mkdir(exist_ok=True)
    argv = ["--import", str(summary), "--campaign", PACK_ID, "--mock", str(script),
            "--saves", str(tmp_path / "saves")]
    code, out = cli(argv, list(lines), env={}, campaigns_dir=campaigns)
    return code, out, campaigns


def pack_bytes(folder):
    return {
        str(p.relative_to(folder)): p.read_bytes()
        for p in sorted(folder.rglob("*")) if p.is_file() and ".import" not in p.parts
    }


def test_import_refuses_broken_link_then_conflict_then_accepts_valid_pack(
    registry, cfg, tmp_path
):
    steps = [
        tools_step(bad_pack_call("i-1")), tools_step(conflict_pack_call("i-2")),
        tools_step(pack_call("i-3")),
    ]
    adapter, ctx, campaigns, folder = run_staged_import(registry, cfg, tmp_path, steps)
    assert len(adapter.requests) == 3
    [first] = error_texts(adapter.requests[1])
    assert "start.hero_location" in first
    assert "ghost" in first
    assert "\n" in first
    [second] = error_texts(adapter.requests[2])
    assert second.startswith("npcs.yaml: npc ")
    assert ctx.files is not None
    finish_import(folder, campaigns, PACK_ID)
    pack = load_pack(campaigns / PACK_ID, registry)
    world = WorldState(world_id="check", rng=Rng(0).state)
    assert collect_conflicts(world, [], pack)[1] == []


def test_import_refusal_lines_name_campaign_id_not_temp_path(registry, cfg, tmp_path):
    steps = [tools_step(bad_pack_call("i-1")), tools_step(pack_call("i-2"))]
    adapter, _, _, folder = run_staged_import(registry, cfg, tmp_path, steps)
    [text] = error_texts(adapter.requests[1])
    assert str(folder) not in text
    assert text.startswith(f"{PACK_ID}/")


def test_import_then_world_with_hero_on_the_fly_turn_save_load(registry, cfg, tmp_path):
    code, _, campaigns = cli_import(tmp_path)
    assert code == 0
    pack = load_pack(campaigns / PACK_ID, registry)
    world = WorldState(world_id="check", rng=Rng(0).state)
    assert collect_conflicts(world, [], pack)[1] == []
    bundle = new_world_from_pack(
        registry, cfg, pack, hero=base_sheet(), seed=7, world_id="w1", saved_at=SAVED_AT,
        preset_id="heroic",
    )
    assert bundle.world.campaign_id == PACK_ID
    assert bundle.heroes[0].location_id == "inn"
    app = make_app(registry, tmp_path / "saves", scripted([text_step(TURN_TEXT)]), bundle=bundle)
    assert app.handle("Осматриваюсь").narration == TURN_TEXT
    app.save_current("auto")
    loaded = load_slot(tmp_path / "saves", "w1", "auto")
    assert core_dump(loaded) == core_dump(app.bundle)
    assert loaded.heroes[0].name == "Борин"
    assert loaded.world.campaign_id == PACK_ID
    assert sorted(loaded.world.npcs) == ["guard", "mara"]


def test_repeat_import_into_same_id_is_refused_and_files_stay(tmp_path):
    cli_import(tmp_path)
    folder = tmp_path / "campaigns" / PACK_ID
    before = pack_bytes(folder)
    code, out, _ = cli_import(tmp_path)
    assert code == 1
    assert "уже есть" in out.text
    assert pack_bytes(folder) == before


def test_three_invalid_packs_in_a_row_give_menu_and_nothing_on_disk(tmp_path):
    steps = [{"tool_calls": [bad_pack_call(f"b-{i}")]} for i in range(3)]
    script = write_steps(tmp_path / "bad.yaml", steps)
    code, out, campaigns = cli_import(tmp_path, script=script, lines=["3"])
    assert code == 1
    assert "Повторить" in out.text
    assert "Сменить модель" in out.text
    assert list(campaigns.iterdir()) == []


def test_import_refusal_gives_hint_and_menu(tmp_path):
    script = write_steps(tmp_path / "ref.yaml", [{"stop": "refusal"}])
    code, out, campaigns = cli_import(tmp_path, script=script, lines=["3"])
    assert code == 1
    assert REFUSAL_HINT in " ".join(out.text.split())
    assert "Выйти" in out.text
    assert list(campaigns.iterdir()) == []


# (2) три разных нарушения предыстории подряд

BG_BUDGET = {"equipment": [], "gold_cp": 6000}
BG_CLASS_SKILL = {"skills": ["perception", "performance"]}
BG_FEAT = {"feat": "defense"}


def background_run(registry, cfg, tmp_path, steps):
    adapter = scripted(steps)
    hero_deps = deps(adapter, registry, cfg, tmp_path)
    task = BackgroundTask("fighter", ["perception", "survival"])
    return adapter, lambda: propose_background(hero_deps, task, "Акробат", "hero-1")


def test_three_different_invalid_backgrounds_in_a_row_fail_as_invalid(registry, cfg, tmp_path):
    steps = [
        tools_step(spec_call("bg-1", **BG_BUDGET)),
        tools_step(spec_call("bg-2", **BG_CLASS_SKILL)),
        tools_step(spec_call("bg-3", **BG_FEAT)),
    ]
    adapter, call = background_run(registry, cfg, tmp_path, steps)
    with pytest.raises(TurnFailed) as info:
        call()
    assert info.value.reason == "invalid"
    assert len(adapter.requests) == 3
    assert "50 зм" in error_texts(adapter.requests[1])[0]
    assert "навык класса уже даёт предыстория" in error_texts(adapter.requests[2])[0]


def test_two_different_invalid_backgrounds_then_valid_one_passes(registry, cfg, tmp_path):
    steps = [
        tools_step(spec_call("bg-1", **BG_BUDGET)),
        tools_step(spec_call("bg-2", **BG_FEAT)),
        tools_step(spec_call("bg-3")),
    ]
    adapter, call = background_run(registry, cfg, tmp_path, steps)
    spec = call()
    assert len(adapter.requests) == 3
    assert "origin" in error_texts(adapter.requests[2])[0]
    assert background_check(spec, registry, ["perception", "survival"]) == ([], [])


# (3) пресет grim: абзац пресета в кэшируемом блоке system, префикс стабилен между ходами

def grim_world(registry, cfg):
    return new_world_from_pack(
        registry, cfg, vale_pack(registry), hero=base_sheet(), seed=7, world_id="w1",
        saved_at=SAVED_AT, preset_id="grim",
    )


def test_grim_preset_paragraph_is_in_cached_world_block(registry, cfg):
    bundle = grim_world(registry, cfg)
    ctx = TurnContext(bundle, registry, cfg)
    request = PromptBuilder(app_cfg()).build(ctx, "Осматриваюсь", "explore")
    preset = load_presets()["grim"]
    block = request.system[1]
    assert block.cache is True
    tone = json.loads(block.text)["tone"]
    assert tone["notes"] == preset.tone.notes
    assert preset.tone.notes
    assert tone["violence"] == "жестоко"
    assert tone["romance"] == "откровенно"
    assert tone["horror"] == "сильно"


def test_grim_world_prefix_is_byte_identical_between_two_turns(registry, cfg, tmp_path):
    adapter = scripted([text_step(TURN_TEXT), text_step("Тихо.")])
    app = make_app(registry, tmp_path, adapter, bundle=grim_world(registry, cfg))
    app.handle("Осматриваюсь")
    app.handle("Жду")
    assert len(adapter.requests) == 2
    one, two = adapter.requests
    assert one.model_dump_json(include={"tools", "system"}) == two.model_dump_json(
        include={"tools", "system"}
    )
    assert one.messages != two.messages
    assert json.loads(two.system[1].text)["tone"]["romance"] == "откровенно"
