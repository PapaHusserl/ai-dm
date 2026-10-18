# Ж3 (docs/plan-zh3.md, п. 3): мок-прогон журнала знаний на ScriptedAdapter, без сети.
# Ход A: рассказчик пишет knowledge_note told (от Гракха об Олдрике), пытается записать
#   нераскрытый секрет (отказ spoiler) и ставит scene_mood romance; движок сам пишет место и
#   знакомство с Гракхом. Ход B: set_flag + reveal_secret -- секрет попадает в журнал движком;
#   в запросе хода B журнал виден рассказчику (без записей о знакомстве и месте). Ход C:
#   scene_mood none. Ходы D/E: scene_mood и конец сцены. /lore показывает всё; сейв/загрузка
#   журнал не теряют и не дублируют.
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unit" / "game"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unit" / "protocol"))

from game_kit import (  # noqa: E402
    end_scene_call,
    flag_call,
    make_app,
    scripted,
    text_step,
    tools_step,
)
from protocol_kit import make_bundle  # noqa: E402

from ai_dm.audio.catalog import load_audio  # noqa: E402
from ai_dm.audio.select import pick_theme  # noqa: E402
from ai_dm.game.lore_text import LORE_EMPTY  # noqa: E402
from ai_dm.game.scene import hero_of  # noqa: E402
from ai_dm.state.triggers import Secret  # noqa: E402
from ai_dm.ui.screen import sound_state  # noqa: E402

SECRET = "сестра Олдрика обращена вампиром и прячется в склепе"
NOTE = "Хранит ключ от склепа"


def call(name, call_id, **fields):
    return {"id": call_id, "name": name, "input": {"type": name, **fields}}


def note_call(call_id, text, kind="npc", ref="aldric", source="told", from_ref="grakh"):
    return call(
        "knowledge_note", call_id, kind=kind, ref=ref, text=text, source=source, from_ref=from_ref
    )


def mood_call(call_id, mood):
    return call("scene_mood", call_id, mood=mood)


def reveal_call(call_id="rv-1"):
    return call("reveal_secret", call_id, npc_id="aldric", secret_id="sister")


def make_story_app(registry, tmp_path):
    bundle = make_bundle(registry)
    aldric = bundle.world.npcs["aldric"]
    aldric.location_id = "vale"
    aldric.secrets.append(
        Secret.model_validate({"id": "sister", "text": SECRET, "reveal_if": {"flag": "found"}})
    )
    steps = [
        # ход A
        tools_step(
            note_call("n1", NOTE),
            note_call("n2", SECRET, source="deduced", from_ref=""),
            mood_call("m1", "romance"),
        ),
        text_step("Гракх кивает и говорит об ключе."),
        # ход B
        tools_step(flag_call("found", "f1"), reveal_call()),
        text_step("Олдрик опускает глаза: сестра обращена."),
        # ход C
        tools_step(mood_call("m2", "none")),
        text_step("Вечер тих."),
        # ход D: романтика и конец сцены
        tools_step(mood_call("m3", "romance")),
        text_step("Огонь в очаге."),
        tools_step(end_scene_call("es1", "Разговор окончен")),
        text_step("Все расходятся."),
        # ход E
        text_step("Наутро всё по-новому."),
    ]
    return make_app(registry, tmp_path, scripted(steps), bundle=bundle)


class Story:
    def __init__(self, registry, tmp_path):
        self.app = make_story_app(registry, tmp_path)
        self.snap = {}

    def journal(self):
        return list(hero_of(self.app.bundle).knowledge)

    def mood(self):
        return self.app.bundle.session.current_scene.scene_mood

    def play(self, key, line):
        result = self.app.handle(line).turn
        self.snap[key] = {
            "result": result, "journal": self.journal(), "mood": self.mood(),
            "requests": len(self.app.adapter.requests),
        }
        return result


@pytest.fixture(scope="module")
def story(registry, tmp_path_factory):
    run = Story(registry, tmp_path_factory.mktemp("zh3"))
    run.play("A", "Здороваюсь с Гракхом")
    run.play("B", "Расспрашиваю Олдрика")
    run.play("C", "Прощаюсь")
    run.play("D", "Сижу у огня")
    run.play("D2", "Расходимся")
    run.play("E", "Жду утра")
    return run


def texts(snap):
    return [e.text for e in snap["journal"]]


# ход A

def test_all_turns_committed(story):
    assert all(s["result"].committed for s in story.snap.values())


def test_turn_a_told_note_is_in_journal(story):
    [told] = [e for e in story.snap["A"]["journal"] if e.source == "told"]
    assert (told.kind, told.ref, told.text, told.from_ref) == ("npc", "aldric", NOTE, "grakh")


def test_turn_a_spoiler_attempt_is_rejected_and_not_written(story):
    assert SECRET not in texts(story.snap["A"])
    assert "spoiler" in story.snap["A"]["result"].report_tags


def test_turn_a_spoiler_is_in_outcomes_as_rejected(story):
    outcomes = story.snap["A"]["result"].outcomes
    assert any(o.startswith("knowledge_note: отклонено") for o in outcomes)


def test_turn_a_engine_wrote_place_and_meeting(story):
    got = texts(story.snap["A"])
    assert "Место: Вейл" in got
    assert "Знакомство: Гракх" in got


def test_turn_a_no_meeting_with_unmentioned_npc(story):
    assert "Знакомство: Олдрик" not in texts(story.snap["A"])


def test_turn_a_mood_romance_is_set(story):
    assert story.snap["A"]["mood"] == "romance"


def test_turn_a_presence_log_not_in_lines(story):
    assert all("Журнал: " not in line for line in story.snap["A"]["result"].lines)


# ход B

def test_turn_b_secret_is_written_by_engine(story):
    [deduced] = [e for e in story.snap["B"]["journal"] if e.source == "deduced"]
    assert (deduced.kind, deduced.ref, deduced.text) == ("npc", "aldric", SECRET)


def test_turn_b_meets_aldric_by_name_in_narration(story):
    assert "Знакомство: Олдрик" in texts(story.snap["B"])


def test_turn_b_mood_stays_romance(story):
    assert story.snap["B"]["mood"] == "romance"


def knowledge_block(request):
    return json.loads(request.messages[0].content[0].text).get("knowledge")


def test_turn_b_prompt_shows_told_note_to_narrator(story):
    requests = story.app.adapter.requests
    first_b = requests[story.snap["A"]["requests"]]
    assert knowledge_block(first_b) == {"npc": {"aldric": [f"{NOTE} (told: grakh)"]}}


def test_turn_b_prompt_hides_engine_entries(story):
    requests = story.app.adapter.requests
    first_b = requests[story.snap["A"]["requests"]]
    assert "Знакомство" not in json.dumps(knowledge_block(first_b), ensure_ascii=False)
    assert "Место:" not in json.dumps(knowledge_block(first_b), ensure_ascii=False)


def test_turn_c_prompt_shows_revealed_secret(story):
    requests = story.app.adapter.requests
    first_c = requests[story.snap["B"]["requests"]]
    lines = knowledge_block(first_c)["npc"]["aldric"]
    assert f"{SECRET} (deduced)" in lines


def test_first_prompt_has_no_knowledge_block(story):
    assert knowledge_block(story.app.adapter.requests[0]) is None


# ход C-E: настроение

def test_turn_c_mood_none_clears_mood(story):
    assert story.snap["C"]["mood"] == ""


def test_turn_d_mood_romance_set_again(story):
    assert story.snap["D"]["mood"] == "romance"


def test_end_scene_turn_closes_scene(story):
    assert story.snap["D2"]["result"].committed is True


def test_new_scene_has_no_mood(story):
    assert story.snap["E"]["mood"] == ""


# /lore

def test_lore_overview_lists_met_and_noted_entities(story):
    lines = story.app.handle("/lore").lines
    assert "Люди:" in lines
    assert any(line.startswith("  Олдрик — ") for line in lines)
    assert any(line.startswith("  Гракх — ") for line in lines)
    assert "Места:" in lines


def test_lore_entity_shows_told_note_with_teller_name(story):
    text = "\n".join(story.app.handle("/lore олдрик").lines)
    assert NOTE in text
    assert "рассказали: Гракх" in text
    assert SECRET in text


def test_lore_entity_includes_engine_entries(story):
    text = "\n".join(story.app.handle("/lore олдрик").lines)
    assert "Знакомство: Олдрик" in text


def test_lore_costs_no_model_request(story):
    before = len(story.app.adapter.requests)
    story.app.handle("/lore")
    assert len(story.app.adapter.requests) == before


# музыка

def test_sound_state_carries_scene_mood(registry, tmp_path):
    run = Story(registry, tmp_path)
    run.play("A", "Здороваюсь с Гракхом")
    assert sound_state(run.app).scene_mood == "romance"


def test_romance_scene_picks_romance_theme_from_real_index(registry, tmp_path):
    run = Story(registry, tmp_path)
    run.play("A", "Здороваюсь с Гракхом")
    assert pick_theme(load_audio().index, sound_state(run.app)) == "romance"


def test_cleared_mood_picks_non_romance_theme(registry, tmp_path):
    run = Story(registry, tmp_path)
    run.play("A", "Здороваюсь с Гракхом")
    run.play("B", "Расспрашиваю Олдрика")
    run.play("C", "Прощаюсь")
    assert pick_theme(load_audio().index, sound_state(run.app)) != "romance"


# сейв и загрузка

def test_save_and_load_keep_journal_and_mood(registry, tmp_path):
    run = Story(registry, tmp_path)
    run.play("A", "Здороваюсь с Гракхом")
    before = [e.model_dump() for e in run.journal()]
    run.app.save_current("auto")
    run.app.bundle.heroes[0].knowledge = []
    run.app.bundle.session.current_scene.scene_mood = ""
    lines = run.app.load("auto")
    assert lines[0] == "Загружено: auto.", lines
    assert [e.model_dump() for e in run.journal()] == before
    assert run.mood() == "romance"


def test_load_does_not_duplicate_entries(registry, tmp_path):
    run = Story(registry, tmp_path)
    run.play("A", "Здороваюсь с Гракхом")
    run.app.save_current("auto")
    count = len(run.journal())
    run.app.load("auto")
    run.app.load("auto")
    assert len(run.journal()) == count


def test_new_world_lore_is_empty(registry, tmp_path):
    app = make_app(registry, tmp_path, scripted([]))
    assert app.handle("/lore").lines == [LORE_EMPTY]
