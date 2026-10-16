# ТМ (docs/TM-PLAN.md, §1 п.8): метки gold_repeat и rest_repeat идут Decision.report_tag ->
# TurnResult.report_tags -> авто-репорт GameApp (saves/<world>/issues/<имя>/, meta.json["tags"]).
import json

from game_kit import make_app, make_bundle, scripted, text_step, tools_step


def gold_call(amount, call_id="g1"):
    return {
        "id": call_id, "name": "gold",
        "input": {
            "type": "gold", "direction": "gain", "kind": "explicit", "amount_cp": amount, "cr": "",
        },
    }


def rest_call(call_id="r1"):
    return {"id": call_id, "name": "rest", "input": {"type": "rest", "kind": "long"}}


def issues(tmp_path, world_id="w1"):
    folder = tmp_path / world_id / "issues"
    if not folder.exists():
        return []
    return sorted(folder.iterdir())


def meta_of(path):
    return json.loads((path / "meta.json").read_text(encoding="utf-8"))


def two_gold_turns(registry, tmp_path, **kw):
    steps = [
        tools_step(gold_call(2000)), text_step("Кошель."),
        tools_step(gold_call(2000)), text_step("Опять кошель."),
    ]
    app = make_app(registry, tmp_path, scripted(steps), **kw)
    return app, app.handle("Обыскать тела"), app.handle("Перевязать раны")


def two_rest_turns(registry, tmp_path, **kw):
    steps = [
        tools_step(rest_call()), text_step("Спишь."),
        tools_step(rest_call()), text_step("Снова спишь."),
    ]
    app = make_app(registry, tmp_path, scripted(steps), **kw)
    return app, app.handle("Отдыхаю"), app.handle("Снова отдыхаю")


# gold_repeat

def test_gold_repeat_tag_is_in_reply_turn(registry, tmp_path):
    _, first, second = two_gold_turns(registry, tmp_path, auto_reports=True)
    assert first.turn.report_tags == []
    assert second.turn.report_tags == ["gold_repeat"]


def test_gold_repeat_writes_one_report(registry, tmp_path):
    two_gold_turns(registry, tmp_path, auto_reports=True)
    found = issues(tmp_path)
    assert len(found) == 1
    assert found[0].name.endswith("-t2-gold_repeat")


def test_gold_repeat_report_meta_has_tag(registry, tmp_path):
    two_gold_turns(registry, tmp_path, auto_reports=True)
    assert meta_of(issues(tmp_path)[0])["tags"] == ["gold_repeat"]


def test_first_gold_turn_writes_no_report(registry, tmp_path):
    steps = [tools_step(gold_call(2000)), text_step("Кошель.")]
    app = make_app(registry, tmp_path, scripted(steps), auto_reports=True)
    reply = app.handle("Обыскать тела")
    assert reply.turn.report_tags == []
    assert issues(tmp_path) == []


def test_gold_repeat_with_auto_reports_off_has_tag_but_no_file(registry, tmp_path):
    _, _, second = two_gold_turns(registry, tmp_path, auto_reports=False)
    assert second.turn.report_tags == ["gold_repeat"]
    assert issues(tmp_path) == []


def test_gold_repeat_turn_is_committed(registry, tmp_path):
    app, _, second = two_gold_turns(registry, tmp_path, auto_reports=True)
    assert second.turn.committed is True
    assert app.bundle.session.turn_seq == 2


def test_gold_repeat_does_not_add_money_to_the_hero(registry, tmp_path):
    start = make_bundle(registry).heroes[0].money_cp
    app, _, _ = two_gold_turns(registry, tmp_path, auto_reports=True)
    assert app.bundle.heroes[0].money_cp == start + 2000
    assert [t.money_delta_cp for t in app.bundle.memory.recent_turns] == [2000, 0]


# rest_repeat

def test_rest_repeat_tag_is_in_reply_turn(registry, tmp_path):
    _, first, second = two_rest_turns(registry, tmp_path, auto_reports=True)
    assert first.turn.report_tags == []
    assert second.turn.report_tags == ["rest_repeat"]


def test_rest_repeat_writes_one_report(registry, tmp_path):
    two_rest_turns(registry, tmp_path, auto_reports=True)
    found = issues(tmp_path)
    assert len(found) == 1
    assert found[0].name.endswith("-t2-rest_repeat")


def test_rest_repeat_report_meta_has_tag(registry, tmp_path):
    two_rest_turns(registry, tmp_path, auto_reports=True)
    assert meta_of(issues(tmp_path)[0])["tags"] == ["rest_repeat"]


def test_rest_repeat_with_auto_reports_off_has_tag_but_no_file(registry, tmp_path):
    _, _, second = two_rest_turns(registry, tmp_path, auto_reports=False)
    assert second.turn.report_tags == ["rest_repeat"]
    assert issues(tmp_path) == []


def test_rest_repeat_does_not_move_the_clock(registry, tmp_path):
    app, _, _ = two_rest_turns(registry, tmp_path, auto_reports=True)
    end_s = app.bundle.heroes[0].long_rest_end_s
    assert end_s is not None
    assert app.bundle.world.clock.now_s == end_s


# обе метки в одном ходу -- один каталог

def test_both_tags_in_one_turn_make_one_report(registry, tmp_path):
    steps = [
        tools_step(gold_call(2000), rest_call()), text_step("Кошель и сон."),
        tools_step(gold_call(2000), rest_call()), text_step("Опять."),
    ]
    app = make_app(registry, tmp_path, scripted(steps), auto_reports=True)
    app.handle("Обыскать и отдохнуть")
    second = app.handle("Ещё раз")
    assert set(second.turn.report_tags) == {"gold_repeat", "rest_repeat"}
    assert len(issues(tmp_path)) == 1
    assert set(meta_of(issues(tmp_path)[0])["tags"]) == {"gold_repeat", "rest_repeat"}
