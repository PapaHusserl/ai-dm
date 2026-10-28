# Проверка установки: uv build, затем uv tool install колеса во временный UV_TOOL_DIR.
# Нужна сеть (зависимости колеса). Запуск: make install-check
import glob
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ONE_WORLD = (
    "import sys; from pathlib import Path; "
    "sys.exit(0 if len(list(Path(sys.argv[1]).iterdir())) == 1 else 1)"
)


def run(cmd, env=None, input=None, cwd=None):
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True, env=env, input=input, text=True, cwd=cwd)


def main():
    root = Path(__file__).resolve().parent.parent
    os.chdir(root)
    for old in glob.glob("dist/*.whl"):
        os.remove(old)
    run(["uv", "build", "--wheel"])
    wheel = sorted(glob.glob("dist/*.whl"))[-1]
    with tempfile.TemporaryDirectory(prefix="ai-dm-install-") as tmp:
        env = dict(os.environ)
        env["UV_TOOL_DIR"] = str(Path(tmp) / "tools")
        env["UV_TOOL_BIN_DIR"] = str(Path(tmp) / "bin")
        spec = f"ai-dm[audio] @ {Path(wheel).resolve().as_uri()}"
        run(["uv", "tool", "install", "--from", spec, "ai-dm"], env=env)
        run([str(Path(tmp) / "bin" / "ai-dm"), "--help"], env=env)
        python = Path(tmp) / "tools" / "ai-dm" / "bin" / "python"
        run([str(python), "-c", "import textual"], env=env)
        run([str(python), "-c", "import miniaudio"], env=env)
        # новый мир на mock без ключа, из чужой папки: мир ляжет в пользовательскую папку данных
        home = Path(tmp) / "home"
        home.mkdir()
        script = Path(tmp) / "one.yaml"
        script.write_text('steps:\n  - text: "Рассказ."\n', encoding="utf-8")
        clean = {"PATH": env["PATH"], "HOME": str(home)}
        game = [str(Path(tmp) / "bin" / "ai-dm"), "--new", "--hero", "arn", "--simple",
                "--mock", str(script)]
        run(game, env=clean, input="Здравствуйте\n", cwd=home)
        saves = home / ".local" / "share" / "ai-dm" / "saves"
        run([str(python), "-c", ONE_WORLD, str(saves)], env=env)
    print("Установка колеса проверена.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
