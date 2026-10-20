# 19ф Ф2а/Ф2б (docs/plan-19f.md п.1) на уровне TurnRunner/GameApp:
#   Ф2б -- ход, которым бой закончился, кончается вопросом: приписка CHOICES_ASK, offer_choices,
#   тег choices_retry, меню после end_fight; промежуточные ходы боя без приписки;
#   Ф2а -- рассказ объявил бой без start_combat: тег combat_announced и авто-репорт.
import json

from game_kit import (
    ReactiveAdapter,
    ScriptThenReactive,
    attack_or_move_number,
    drive,
    end_turn_number,
    enemies_surrender,
    make_app,
    make_rig,
    run_records,
    scripted,
    start_combat_call,
    text_step,
    tools_step,
)

from ai_dm.llm.mock import ScriptedAdapter
from ai_dm.llm.types import ChatResponse, Text, ToolCall, Usage
from ai_dm.master.session import CHOICES_ASK
from ai_dm.protocol.schema import tool_set
from ai_dm.ui.screen import screen_blocks
from ai_dm.ui.session import offer_is_stale

NARRATE = {d["name"] for d in tool_set("combat_narrate")}
ENDING = "Последний гоблин падает.\n\nЧто ты делаешь дальше?"
OFFER_INPUT = {"type": "offer_choices", "choices": ["Обыскать зал", "Уйти"]}
ANNOUNCE = "Гоблин выхватывает нож.\n\n*(В этот момент начинается бой!)*"


class EndingAdapter(ReactiveAdapter):
    # ReactiveAdapter, у которого рассказ о бое (combat_narrate) кончается вопросом;
    # на приписку CHOICES_ASK отвечает offer_choices (или текстом при ask_with="text")
    def __init__(self, *, narrate_text=ENDING, ask_with="offer", **kw):
        super().__init__(**kw)
        self.narrate_text = narrate_text
        self.ask_with = ask_with

    def last_text(self, request):
        return "".join(b.text for b in request.messages[-1].content if isinstance(b, Text))

    def complete(self, request):
        if self.last_text(request) == CHOICES_ASK:
            self.requests.append(request.model_copy(deep=True))
            return self.answer_ask(request)
        response = super().complete(request)
        names = {t.name for t in request.tools}
        only_text = all(isinstance(b, Text) for b in response.content)
        if names == NARRATE and only_text and self.narrate_text is not None:
            response.content = [Text(text=self.narrate_text)]
        return response

    def answer_ask(self, request):
        if self.ask_with == "text":
            return ChatResponse(
                content=[Text(text="Не буду.")], stop_reason="end_turn", usage=Usage(),
                request_id="ask-text", model=request.model,
            )
        call = ToolCall(id="ask-offer", name="offer_choices", input=OFFER_INPUT)
        return ChatResponse(
            content=[call], stop_reason="tool_use", usage=Usage(),
            request_id="ask-offer", model=request.model,
        )


def fight_adapter(**kw):
    steps = [tools_step(start_combat_call()), text_step("Гоблины бросаются на вас.")]
    first = ScriptedAdapter(steps, provider="anthropic", model="claude-opus-5-5")
    return ScriptThenReactive(first, EndingAdapter(**kw))


def asks_in(adapter):
    return [
        r for r in adapter.requests
        if any(isinstance(b, Text) and b.text == CHOICES_ASK for b in r.messages[-1].content)
    ]


def start_fight(registry, cfg, tmp_path, **adapter_kw):
    adapter = fight_adapter(**adapter_kw)
    rig = make_rig(registry, cfg, tmp_path, adapter)
    assert rig.runner.play("Бью ногой дверь").committed is True
    return rig, adapter


def test_victory_turn_is_asked_and_offers_choices(registry, cfg, tmp_path):
    rig, adapter = start_fight(registry, cfg, tmp_path)
    results = drive(rig.runner, attack_or_move_number)
    last = results[-1]
    assert last.combat_outcome == "victory"
    assert "choices_retry" in last.report_tags
    assert len(asks_in(adapter)) == 1
    assert rig.runner.bundle.session.offered_choices == ["Обыскать зал", "Уйти"]


def test_victory_turn_has_offer_choices_in_record(registry, cfg, tmp_path):
    rig, _ = start_fight(registry, cfg, tmp_path)
    last = drive(rig.runner, attack_or_move_number)[-1]
    assert "offer_choices" in last.requests
    assert "offer_choices" in rig.runner.bundle.memory.recent_turns[-1].requests


def test_victory_turn_ask_is_in_the_same_run(registry, cfg, tmp_path):
    rig, _ = start_fight(registry, cfg, tmp_path)
    last = drive(rig.runner, attack_or_move_number)[-1]
    calls = [r["call_id"] for r in run_records(rig.journal, last.run_id)]
    assert len(calls) >= 2
    assert calls[-1] == f"{last.run_id}-{len(calls)}"


def test_intermediate_combat_turns_have_no_ask(registry, cfg, tmp_path):
    rig, adapter = start_fight(registry, cfg, tmp_path)
    results = drive(rig.runner, attack_or_move_number)
    assert len(asks_in(adapter)) == 1
    for result in results[:-1]:
        assert "choices_retry" not in result.report_tags


def test_victory_menu_is_drawn_after_end_fight(registry, tmp_path):
    app = make_app(registry, tmp_path, fight_adapter())
    app.handle("Нападаю")
    for _ in range(60):
        if app.bundle.session.active_combat is None:
            break
        app.handle(str(attack_or_move_number(app.runner)))
    assert app.bundle.session.active_combat is None
    assert offer_is_stale(app) is False
    blocks = screen_blocks(app)
    assert [b.kind for b in blocks] == ["menu"]
    assert list(blocks[0].items) == ["Обыскать зал", "Уйти"]


def test_ended_by_master_turn_is_asked_too(registry, cfg, tmp_path):
    rig, adapter = start_fight(registry, cfg, tmp_path, end_combat=True)
    enemies_surrender(rig.runner)
    result = rig.runner.play(str(end_turn_number(rig.runner)))
    assert result.committed is True
    assert rig.runner.bundle.session.active_combat is None
    assert "choices_retry" in result.report_tags
    assert len(asks_in(adapter)) == 1
    assert rig.runner.bundle.session.offered_choices == ["Обыскать зал", "Уйти"]


def test_text_answer_to_ask_commits_turn_without_menu(registry, cfg, tmp_path):
    rig, adapter = start_fight(registry, cfg, tmp_path, ask_with="text")
    last = drive(rig.runner, attack_or_move_number)[-1]
    assert last.committed is True
    assert last.combat_outcome == "victory"
    assert "offer_choices" not in last.requests
    assert rig.runner.bundle.session.offered_choices == []
    assert len(asks_in(adapter)) == 1


def test_victory_without_question_is_not_asked(registry, cfg, tmp_path):
    rig, adapter = start_fight(registry, cfg, tmp_path, narrate_text="Гоблины мертвы.")
    last = drive(rig.runner, attack_or_move_number)[-1]
    assert last.combat_outcome == "victory"
    assert asks_in(adapter) == []
    assert "choices_retry" not in last.report_tags


# Ф2а на уровне игры

def issues(tmp_path, world_id="w1"):
    folder = tmp_path / world_id / "issues"
    return sorted(folder.iterdir()) if folder.exists() else []


def test_combat_announced_tag_in_turn_result(registry, tmp_path):
    adapter = scripted([text_step(ANNOUNCE)])
    app = make_app(registry, tmp_path, adapter)
    reply = app.handle("Иду")
    assert reply.turn.report_tags == ["combat_announced"]
    assert len(adapter.requests) == 1
    assert app.bundle.session.active_combat is None


def test_combat_announced_writes_auto_report(registry, tmp_path):
    adapter = scripted([text_step(ANNOUNCE)])
    app = make_app(registry, tmp_path, adapter, auto_reports=True)
    app.handle("Иду")
    assert len(issues(tmp_path)) == 1
    assert issues(tmp_path)[0].name.endswith("-combat_announced")
    meta = json.loads((issues(tmp_path)[0] / "meta.json").read_text(encoding="utf-8"))
    assert "combat_announced" in json.dumps(meta, ensure_ascii=False)


def test_combat_announced_report_off_writes_nothing(registry, tmp_path):
    adapter = scripted([text_step(ANNOUNCE)])
    app = make_app(registry, tmp_path, adapter, auto_reports=False)
    app.handle("Иду")
    assert issues(tmp_path) == []
