# Приёмка этапа 6а (STAGE6A-PLAN, P2, критерий ТЗ 13): ход -> репорт -> `ai-dm --replay-report` даёт
# «Состояние совпало» (код 0): исследование с меткой, боевой ход (с вызовом модели и по номеру),
# откатанный ход (refusal), ход с границей сцены (world + summarizer). Порча репорта -- код 1;
# живой мир не меняется; несовместимые флаги -- код 2. Живых вызовов нет, всё во временных папках.
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unit" / "ui"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unit" / "game"))

from game_kit import (  # noqa: E402
    NOW,
    OPUS,
    SONNET,
    ReactiveAdapter,
    ScriptThenReactive,
    attack_or_move_number,
    end_scene_call,
    player_action_input,
    scripted,
    scripted_from_yaml,
    settings,
    text_step,
    tools_step,
)
from slots_kit import WORLD_TEXT  # noqa: E402
from summarizer_kit import summ_steps  # noqa: E402
from ui_kit import DESCEND, SAVED_AT, TALK, WORLD, build_app, cli, play  # noqa: E402
from world_kit import (  # noqa: E402
    GRAIL,
    bundle_without_candidates,
    end_turn,
    narrator_turns,
    npc_update_call,
    world_step,
)

from ai_dm.game.app import GameApp  # noqa: E402
from ai_dm.game.starter import new_world  # noqa: E402
from ai_dm.llm.replay import ReplayAdapter  # noqa: E402

COMBAT_SCRIPT = "talk_check_fight.yaml"
KICK = "Опрокидываю бочку на ближнего гоблина"
IMPROVISE = {
    "skill": "athletics", "category": "medium", "effect": "prone", "target": "goblin_1",
    "zone": "",
}
UNSUPPORTED = {
    "id": "u-1", "name": "unsupported_action",
    "input": {"type": "unsupported_action", "description": "верхом на медведе"},
}
MATCH = "Состояние совпало."


def reports_of(root, world=WORLD):
    return sorted((Path(root) / world / "issues").glob("*"))


def replay(path):
    return cli(["--replay-report", str(path)], env={})


def snapshot(folder):
    return {
        str(p.relative_to(folder)): p.read_bytes()
        for p in sorted(Path(folder).rglob("*")) if p.is_file()
    }


def explore_report(registry, root, report=True):
    # ход исследования с меткой unsupported_action; авто-репорт включён (как в живой игре)
    steps = [tools_step(UNSUPPORTED), text_step("Медведя здесь нет.")]
    app = build_app(registry, root, scripted(steps), hp=200)
    app.auto_reports = True
    app.handle("Еду на медведе")
    if report:
        app.handle("/report медведь")
    return reports_of(root)[-1]


def fight_app(registry, root):
    adapter = ScriptThenReactive(
        scripted_from_yaml(COMBAT_SCRIPT),
        ReactiveAdapter(classify=[player_action_input([], improvise=IMPROVISE)]),
    )
    return build_app(registry, root, adapter, hp=200)


def start_fight(app):
    play(app, [TALK, "1", DESCEND])


def test_explore_turn_replays_with_same_state(registry, tmp_path):
    path = explore_report(registry, tmp_path / "saves")
    code, out = replay(path)
    assert code == 0
    assert MATCH in out.lines
    assert "Медведя здесь нет." in out.text


def test_auto_report_by_tag_replays_too(registry, tmp_path):
    root = tmp_path / "saves"
    steps = [tools_step(UNSUPPORTED), text_step("Медведя здесь нет.")]
    app = build_app(registry, root, scripted(steps), hp=200)
    app.handle("Еду на медведе")
    path = reports_of(root)[-1]
    assert path.name.endswith("missing-mechanic")
    code, out = replay(path)
    assert code == 0
    assert MATCH in out.lines


def test_fight_start_turn_with_model_call_replays(registry, tmp_path):
    root = tmp_path / "saves"
    app = fight_app(registry, root)
    start_fight(app)
    app.handle(KICK)
    app.handle("/report бой")
    code, out = replay(reports_of(root)[-1])
    assert code == 0
    assert MATCH in out.lines


def test_fight_turn_by_number_with_dice_replays(registry, tmp_path):
    root = tmp_path / "saves"
    app = fight_app(registry, root)
    start_fight(app)
    app.handle(KICK)
    app.handle(str(attack_or_move_number(app.runner)))
    app.handle("/report бросок")
    code, out = replay(reports_of(root)[-1])
    assert code == 0
    assert MATCH in out.lines


def test_several_fight_turns_each_replay_from_their_own_report(registry, tmp_path):
    root = tmp_path / "saves"
    app = fight_app(registry, root)
    start_fight(app)
    app.handle(KICK)
    for number in range(3):
        app.handle(str(attack_or_move_number(app.runner)))
        app.handle(f"/report ход {number}")
    paths = reports_of(root)
    assert len(paths) == 3
    for path in paths:
        code, out = replay(path)
        assert code == 0, out.text
        assert MATCH in out.lines


def test_aborted_turn_replays_with_same_failure_and_state_before(registry, tmp_path):
    root = tmp_path / "saves"
    app = build_app(registry, root, scripted([{"stop": "refusal"}] * 2), hp=200)
    app.handle("Иду")
    path = reports_of(root)[-1]
    assert not (path / "after").exists()
    code, out = replay(path)
    assert code == 0
    assert MATCH in out.lines


def test_aborted_turn_with_other_failure_in_journal_is_a_difference(registry, tmp_path):
    root = tmp_path / "saves"
    app = build_app(registry, root, scripted([{"stop": "refusal"}] * 2), hp=200)
    app.handle("Иду")
    path = reports_of(root)[-1]
    meta = json.loads((path / "meta.json").read_text(encoding="utf-8"))
    meta["failure_reason"] = "other_reason"
    (path / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    code, out = replay(path)
    assert code == 1
    assert "Состояние не совпало:" in out.lines


def boundary_app(registry, root):
    bundle = new_world(
        registry, settings().rules, hero="arn", seed=3, world_id=WORLD, saved_at=SAVED_AT
    )
    narrator = scripted([tools_step(end_scene_call(summary="Подсказка.")), text_step("Конец.")])
    summarizer = scripted(summ_steps("Выжимка сцены."))
    return GameApp(
        settings(), registry, bundle, narrator, saves_root=root, world_text=WORLD_TEXT,
        model=OPUS, sleeper=lambda s: None, now=lambda: NOW, run_tag="t",
        summarizer_adapter=summarizer, auto_reports=False,
    )


def test_turn_with_scene_boundary_replays(registry, tmp_path):
    root = tmp_path / "saves"
    app = boundary_app(registry, root)
    app.handle("Прощаюсь и ухожу")
    assert app.bundle.memory.scenes
    app.handle("/report граница")
    path = reports_of(root)[-1]
    roles = {
        json.loads(line)["role"]
        for line in (path / "journal" / "calls.jsonl").read_text(encoding="utf-8").splitlines()
    }
    assert {"narrator", "summarizer"} <= roles
    code, out = replay(path)
    assert code == 0
    assert MATCH in out.lines


def world_boundary_app(registry, root):
    # граница сцены с тремя ролями: нарратор, world (другая модель) и summarizer
    bundle = bundle_without_candidates(registry, settings().rules)
    steps = world_step(
        npc_update_call("aldric", GRAIL, status="dead", cause="goal", evidence_ref="r42")
    )
    narrator = scripted(narrator_turns(end_turn(1, flag="grail_seen")))
    return GameApp(
        settings(), registry, bundle, narrator, saves_root=root, sleeper=lambda s: None,
        world_text=bundle.world.lore.world_text,
        now=lambda: NOW, run_tag="t", world_adapter=scripted(steps), world_model=SONNET,
        summarizer_adapter=scripted(summ_steps("Выжимка сцены.")), auto_reports=False,
    )


def test_turn_with_world_and_summarizer_boundary_replays(registry, tmp_path):
    root = tmp_path / "saves"
    app = world_boundary_app(registry, root)
    app.handle("Иду")
    app.handle("/report мир")
    path = reports_of(root, app.bundle.world.world_id)[-1]
    roles = {r["role"] for r in calls_of(path)}
    assert {"narrator", "world", "summarizer"} <= roles
    code, out = replay(path)
    assert code == 0, out.text
    assert MATCH in out.lines


def test_boundary_retry_after_summarizer_failure_replays(registry, tmp_path):
    root = tmp_path / "saves"
    bundle = new_world(
        registry, settings().rules, hero="arn", seed=3, world_id=WORLD, saved_at=SAVED_AT
    )
    narrator = scripted([tools_step(end_scene_call(summary="Подсказка.")), text_step("Конец.")])
    summarizer = scripted([{"error": "fatal", "message": "сбой"}] + summ_steps("Выжимка."))
    app = GameApp(
        settings(), registry, bundle, narrator, saves_root=root, world_text=WORLD_TEXT,
        model=OPUS, sleeper=lambda s: None, now=lambda: NOW, run_tag="t",
        summarizer_adapter=summarizer, auto_reports=False,
    )
    app.handle("Прощаюсь и ухожу")
    assert app.bundle.session.boundary_pending
    app.choose("retry")
    app.handle("/report повтор")
    code, out = replay(reports_of(root)[-1])
    assert code == 0, out.text
    assert MATCH in out.lines


def test_turn_after_transient_error_replays_with_the_retry(registry, tmp_path):
    root = tmp_path / "saves"
    steps = [{"error": "transient", "message": "сеть"}, text_step("Ответ после сбоя.")]
    app = build_app(registry, root, scripted(steps), hp=200)
    app.handle("Иду")
    app.handle("/report сеть")
    path = reports_of(root)[-1]
    assert [r["attempt"] for r in calls_of(path)] == [1, 2]
    code, out = replay(path)
    assert code == 0, out.text
    assert "Ответ после сбоя." in out.text


def test_report_before_any_turn_is_not_replayable_code_2(registry, tmp_path):
    root = tmp_path / "saves"
    app = build_app(registry, root, scripted([text_step("Рассказ.")]), hp=200)
    app.handle("/report ничего не было")
    code, out = replay(reports_of(root)[-1])
    assert code == 2
    assert "не воспроизводится" in out.text


def test_replay_wiring_fixed_now_no_auto_reports_no_stored_model_no_sleep(
    registry, tmp_path, monkeypatch
):
    import ai_dm.ui.cli as cli_module

    path = explore_report(registry, tmp_path / "saves")
    meta = json.loads((path / "meta.json").read_text(encoding="utf-8"))
    seen = {}

    def spy(*args, **kwargs):
        seen.update(kwargs)
        return GameApp(*args, **kwargs)

    roles = []

    def adapter_spy(records, role=None):
        roles.append(role)
        return ReplayAdapter(records, role=role)

    monkeypatch.setattr(cli_module, "GameApp", spy)
    monkeypatch.setattr(cli_module, "ReplayAdapter", adapter_spy)
    code, _ = replay(path)
    assert code == 0
    assert "narrator" in roles
    assert None not in roles
    assert seen["now"]().isoformat() == meta["now"]
    assert seen["auto_reports"] is False
    assert seen["use_stored_model"] is False
    assert seen["sleeper"](30) is None
    assert seen["model"] == meta["model"]


def test_request_model_comes_from_journal_not_from_meta(registry, tmp_path):
    # /model в сессии: в вызовах хода ушла одна модель, в meta -- другая; запрос строится по журналу
    path = explore_report(registry, tmp_path / "saves")
    meta = json.loads((path / "meta.json").read_text(encoding="utf-8"))
    meta["model"] = "claude-other-model"
    (path / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    code, out = replay(path)
    assert code == 0, out.text
    assert MATCH in out.lines


def test_replay_of_tagged_turn_writes_no_new_report_anywhere(registry, tmp_path, monkeypatch):
    import ai_dm.game.app as app_module

    path = explore_report(registry, tmp_path / "saves")
    written = []
    monkeypatch.setattr(app_module, "write_report", lambda *a, **k: written.append(a))
    code, _ = replay(path)
    assert code == 0
    assert written == []


def test_committed_in_replay_but_aborted_in_report_is_a_difference(registry, tmp_path):
    path = explore_report(registry, tmp_path / "saves")
    meta = json.loads((path / "meta.json").read_text(encoding="utf-8"))
    meta["status"] = "aborted"
    meta["failure_reason"] = "refusal"
    (path / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    shutil.rmtree(path / "after")
    code, out = replay(path)
    assert code == 1
    assert "Ход прошёл, а в репорте он откатан." in out.lines


def test_aborted_in_replay_but_committed_in_report_is_a_difference(registry, tmp_path):
    root = tmp_path / "saves"
    app = build_app(registry, root, scripted([{"stop": "refusal"}] * 2), hp=200)
    app.handle("Иду")
    path = reports_of(root)[-1]
    meta = json.loads((path / "meta.json").read_text(encoding="utf-8"))
    meta["status"] = "committed"
    meta["failure_reason"] = None
    (path / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    shutil.copytree(path / "before", path / "after")
    code, out = replay(path)
    assert code == 1
    assert "Ход не прошёл: refusal." in out.lines


def test_aborted_with_other_failure_reason_says_which(registry, tmp_path):
    root = tmp_path / "saves"
    app = build_app(registry, root, scripted([{"stop": "refusal"}] * 2), hp=200)
    app.handle("Иду")
    path = reports_of(root)[-1]
    meta = json.loads((path / "meta.json").read_text(encoding="utf-8"))
    meta["failure_reason"] = "other_reason"
    (path / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    code, out = replay(path)
    assert code == 1
    assert "Сбой 'refusal', в репорте 'other_reason'." in out.lines


# порча репорта

def calls_of(path):
    text = (path / "journal" / "calls.jsonl").read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def write_calls(path, records):
    lines = [json.dumps(r, ensure_ascii=False) + "\n" for r in records]
    (path / "journal" / "calls.jsonl").write_text("".join(lines), encoding="utf-8")


def test_changed_response_in_journal_gives_difference_and_code_1(registry, tmp_path):
    path = explore_report(registry, tmp_path / "saves")
    records = calls_of(path)
    records[-1]["response"]["content"][0]["text"] = "Совсем другой рассказ."
    write_calls(path, records)
    code, out = replay(path)
    assert code == 1
    assert MATCH not in out.lines


def test_removed_record_says_journal_ended_and_code_1(registry, tmp_path):
    path = explore_report(registry, tmp_path / "saves")
    write_calls(path, calls_of(path)[:-1])
    code, out = replay(path)
    assert code == 1
    assert "журнал кончился" in out.text


def test_changed_fingerprint_in_journal_gives_divergence_and_code_1(registry, tmp_path):
    path = explore_report(registry, tmp_path / "saves")
    records = calls_of(path)
    records[0]["request"]["fingerprint"] = "0" * 64
    write_calls(path, records)
    code, out = replay(path)
    assert code == 1
    assert "запрос не совпал" in out.text
    assert MATCH not in out.lines


def test_changed_hero_in_before_changes_request_and_gives_divergence(registry, tmp_path):
    path = explore_report(registry, tmp_path / "saves")
    hero = next((path / "before" / WORLD / "slots" / "auto" / "heroes").glob("*/hero.json"))
    data = json.loads(hero.read_text(encoding="utf-8"))
    data["creature"]["hp_current"] -= 1
    hero.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    code, out = replay(path)
    assert code == 1
    assert MATCH not in out.lines


def test_changed_rng_in_before_gives_difference(registry, tmp_path):
    path = explore_report(registry, tmp_path / "saves")
    world = path / "before" / WORLD / "slots" / "auto" / "world" / "world.json"
    data = json.loads(world.read_text(encoding="utf-8"))
    data["rng"]["state"] += 1
    world.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    code, out = replay(path)
    assert code == 1
    assert MATCH not in out.lines


def test_changed_after_gives_difference(registry, tmp_path):
    path = explore_report(registry, tmp_path / "saves")
    hero = next((path / "after" / WORLD / "slots" / "auto" / "heroes").glob("*/hero.json"))
    data = json.loads(hero.read_text(encoding="utf-8"))
    data["creature"]["hp_current"] -= 1
    hero.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    code, out = replay(path)
    assert code == 1
    assert "Состояние не совпало:" in out.lines
    assert any(line.startswith("heroes[0].creature.hp_current") for line in out.lines)


def test_saved_at_of_snapshots_does_not_matter(registry, tmp_path):
    # saved_at -- время записи репорта; на сравнение не влияет
    path = explore_report(registry, tmp_path / "saves")
    manifest = path / "after" / WORLD / "slots" / "auto" / "manifest.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["saved_at"] = "1999-01-01T00:00:00+00:00"
    manifest.write_text(json.dumps(data), encoding="utf-8")
    code, out = replay(path)
    assert code == 0
    assert MATCH in out.lines


def test_report_without_replayable_flag_is_code_2(registry, tmp_path):
    path = explore_report(registry, tmp_path / "saves")
    meta = json.loads((path / "meta.json").read_text(encoding="utf-8"))
    meta["replayable"] = False
    (path / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    code, out = replay(path)
    assert code == 2
    assert "не воспроизводится" in out.text


def test_missing_report_dir_is_code_2(tmp_path):
    code, out = replay(tmp_path / "нет-такого")
    assert code == 2
    assert "Репорт не прочитан" in out.text


# живой мир не тронут

def test_replay_leaves_live_world_untouched_byte_for_byte(registry, tmp_path):
    root = tmp_path / "saves"
    path = explore_report(registry, root)
    before = snapshot(root)
    for _ in range(2):
        code, _ = replay(path)
        assert code == 0
        assert snapshot(root) == before


def test_replay_of_copied_report_works_without_live_world(registry, tmp_path):
    root = tmp_path / "saves"
    path = explore_report(registry, root)
    elsewhere = tmp_path / "sent" / path.name
    shutil.copytree(path, elsewhere)
    shutil.rmtree(root)
    code, out = replay(elsewhere)
    assert code == 0
    assert MATCH in out.lines


def test_replay_does_not_change_the_report_itself(registry, tmp_path):
    path = explore_report(registry, tmp_path / "saves")
    before = snapshot(path)
    replay(path)
    assert snapshot(path) == before


# несовместимые флаги

def test_incompatible_flags_are_code_2(registry, tmp_path):
    path = explore_report(registry, tmp_path / "saves")
    for extra in (["--new"], ["--world", "x"], ["--replay"], ["--mock", "m.yaml"],
                  ["--mock-world", "m.yaml"], ["--mock-summarizer", "m.yaml"]):
        code, out = cli(["--replay-report", str(path), *extra], env={})
        assert code == 2, extra
        assert "несовместим" in out.text
