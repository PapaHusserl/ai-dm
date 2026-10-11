# Подбор сида для честной победы (test_stage2_done.py): Арн с родными HP (12) побеждает в бою
# «гоблины подвала» через main() -- тот же путь, что в тесте: ScriptThenReactive + HonestInput.
# Не тест (имя без test_), pytest его не собирает. Запуск:
#   uv run python tests/scenarios/find_honest_seed.py 1 200
# Печатает сиды диапазона [от, до), на которых бой выигран и открыто меню повышения уровня.
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unit" / "ui"))

from ui_kit import (  # noqa: E402
    DESCEND,
    TALK,
    FightInput,
    PlainOutput,
    ReactiveAdapter,
    ScriptThenReactive,
    scripted_from_yaml,
)

from ai_dm.ui.cli import main  # noqa: E402

SCRIPT = Path(__file__).resolve().parents[1] / "fixtures" / "scripts" / "talk_check_fight.yaml"


class StopWhenDead(FightInput):
    def read(self, prompt=""):
        if any(line.startswith("HP 0/") for line in self.out.lines[-3:]):
            return None
        return super().read(prompt)


def wins(seed):
    out = PlainOutput()
    with tempfile.TemporaryDirectory() as root:
        argv = ["--new", "--hero", "arn", "--seed", str(seed), "--mock", str(SCRIPT),
                "--saves", root]
        stdin = StopWhenDead(out, [TALK, "1", DESCEND], limit=60)

        def factory(path):
            script = scripted_from_yaml("talk_check_fight.yaml")
            return ScriptThenReactive(script, ReactiveAdapter())

        main(argv, stdin=stdin, stdout=out, env={}, mock_factory=factory)
    won = any("победа" in line.lower() for line in out.lines)
    return won and any("средн" in line.lower() for line in out.lines)


if __name__ == "__main__":
    for seed in range(int(sys.argv[1]), int(sys.argv[2])):
        if wins(seed):
            print(seed)
