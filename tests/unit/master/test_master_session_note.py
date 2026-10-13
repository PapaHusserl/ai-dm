# Р2 (R2-PLAN, Q1а, В7а): приписка к запросу -- отдельный Text-блок после JSON состояния в
# первом user-сообщении; system и JSON состояния не меняются, кэш-блоки те же.
import json

from master_kit import flag_call, make_ctx, make_session, scripted, text_step, tools_step

from ai_dm.llm.types import Text
from ai_dm.protocol.apply import apply

NOTE = "Системная приписка: проверка."


def play(registry, cfg, tmp_path, steps, note=None, user_input="Иду."):
    adapter = scripted(steps)
    session, _, _, _ = make_session(adapter, tmp_path, note=note)
    session.run(make_ctx(registry, cfg), user_input, apply, "explore")
    return adapter


def test_without_note_request_has_one_text_block(registry, cfg, tmp_path):
    adapter = play(registry, cfg, tmp_path, [text_step()])
    assert len(adapter.requests[0].messages[0].content) == 1


def test_note_none_gives_same_request_as_before(registry, cfg, tmp_path):
    plain = play(registry, cfg, tmp_path / "a", [text_step()])
    again = play(registry, cfg, tmp_path / "b", [text_step()], note=None)
    assert plain.requests[0] == again.requests[0]


def test_note_is_second_text_block_of_first_message(registry, cfg, tmp_path):
    adapter = play(registry, cfg, tmp_path, [text_step()], note=NOTE)
    content = adapter.requests[0].messages[0].content
    assert len(content) == 2
    assert isinstance(content[1], Text)
    assert content[1].text == NOTE


def test_message_cache_flag_is_same_with_and_without_note(registry, cfg, tmp_path):
    plain = play(registry, cfg, tmp_path / "a", [text_step()])
    noted = play(registry, cfg, tmp_path / "b", [text_step()], note=NOTE)
    assert noted.requests[0].messages[0].cache == plain.requests[0].messages[0].cache


def test_state_json_is_same_with_and_without_note(registry, cfg, tmp_path):
    plain = play(registry, cfg, tmp_path / "a", [text_step()])
    noted = play(registry, cfg, tmp_path / "b", [text_step()], note=NOTE)
    assert noted.requests[0].messages[0].content[0] == plain.requests[0].messages[0].content[0]


def test_system_blocks_are_same_with_and_without_note(registry, cfg, tmp_path):
    plain = play(registry, cfg, tmp_path / "a", [text_step()])
    noted = play(registry, cfg, tmp_path / "b", [text_step()], note=NOTE)
    assert noted.requests[0].system == plain.requests[0].system


def test_player_input_in_json_is_player_line_without_note(registry, cfg, tmp_path):
    adapter = play(registry, cfg, tmp_path, [text_step()], note=NOTE, user_input="Иду в лес")
    data = json.loads(adapter.requests[0].messages[0].content[0].text)
    assert data["player_input"] == "Иду в лес"
    assert NOTE not in adapter.requests[0].messages[0].content[0].text


def test_note_stays_in_first_message_of_every_tool_round(registry, cfg, tmp_path):
    steps = [tools_step(flag_call("a", "c1")), tools_step(flag_call("b", "c2")), text_step()]
    adapter = play(registry, cfg, tmp_path, steps, note=NOTE)
    assert len(adapter.requests) == 3
    for request in adapter.requests:
        assert request.messages[0].content[1].text == NOTE


def test_note_is_in_the_first_message_only(registry, cfg, tmp_path):
    steps = [tools_step(flag_call("a", "c1")), text_step()]
    adapter = play(registry, cfg, tmp_path, steps, note=NOTE)
    later = adapter.requests[1].messages[1:]
    texts = [b.text for m in later for b in m.content if isinstance(b, Text)]
    assert NOTE not in texts
