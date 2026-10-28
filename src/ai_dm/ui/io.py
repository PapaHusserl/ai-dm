import getpass
from typing import Protocol


class InputSource(Protocol):
    def read(self, prompt: str = "") -> str | None: ...


class OutputSink(Protocol):
    def write(self, line: str) -> None: ...


class CaptureOutput:
    def __init__(self):
        self.lines = []

    def write(self, line):
        self.lines.append(line)

    @property
    def text(self):
        return "\n".join(self.lines)


class StdinInput:
    def read(self, prompt=""):
        try:
            return input(prompt)
        except EOFError:
            return None

    def read_secret(self, prompt=""):
        # ввод без эха (ключ API)
        try:
            return getpass.getpass(prompt)
        except EOFError:
            return None


class StdoutOutput:
    def write(self, line):
        print(line, flush=True)
