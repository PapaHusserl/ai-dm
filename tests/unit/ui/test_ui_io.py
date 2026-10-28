# Ожидаемый API: ai_dm.ui.io -- контракт в ui_kit.py.
# Протоколы ввода-вывода и тестовые реализации: ScriptedInput, CaptureOutput.


def test_protocols_are_declared():
    from typing import Protocol

    from ai_dm.ui.io import InputSource, OutputSink

    assert Protocol in InputSource.__mro__
    assert Protocol in OutputSink.__mro__


def test_capture_output_starts_empty():
    from ai_dm.ui.io import CaptureOutput

    out = CaptureOutput()
    assert out.lines == []
    assert out.text == ""


def test_capture_output_collects_lines_in_order():
    from ai_dm.ui.io import CaptureOutput

    out = CaptureOutput()
    out.write("раз")
    out.write("два")
    assert out.lines == ["раз", "два"]


def test_capture_output_text_joins_lines_with_newline():
    from ai_dm.ui.io import CaptureOutput

    out = CaptureOutput()
    out.write("раз")
    out.write("два")
    assert out.text == "раз\nдва"


def test_stdin_read_secret_uses_getpass_with_prompt(monkeypatch):
    from ai_dm.ui.io import StdinInput

    asked = []
    monkeypatch.setattr("getpass.getpass", lambda prompt="": asked.append(prompt) or "секрет")
    assert StdinInput().read_secret("> ") == "секрет"
    assert asked == ["> "]


def test_stdin_read_secret_end_of_input_is_none(monkeypatch):
    from ai_dm.ui.io import StdinInput

    def eof(prompt=""):
        raise EOFError

    monkeypatch.setattr("getpass.getpass", eof)
    assert StdinInput().read_secret() is None
