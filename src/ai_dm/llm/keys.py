import os
from pathlib import Path

KEY_VARS = {
    "anthropic": "ANTHROPIC_API_KEY", "gemini": "GEMINI_API_KEY", "openai": "OPENAI_API_KEY",
}


def parse_dotenv(text):
    result = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name = name.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] in "\"'" and value.endswith(value[0]):
            value = value[1:-1]
        elif " #" in value:
            value = value.split(" #", 1)[0].strip()
        result[name] = value
    return result


def load_key(provider, *, env=None, dotenv_path=None, var=None):
    # var -- имя переменной хостера (providers.<имя>.key_env); у встроенных берётся из KEY_VARS
    if var is None:
        if provider not in KEY_VARS:
            raise ValueError(f"неизвестный провайдер: {provider}")
        var = KEY_VARS[provider]
    return read_var(var, env=env, dotenv_path=dotenv_path)


def read_var(name, *, env=None, dotenv_path=None):
    if env is None:
        env = os.environ
    if env.get(name):
        return env[name]
    if dotenv_path is not None and Path(dotenv_path).is_file():
        values = parse_dotenv(Path(dotenv_path).read_text(encoding="utf-8"))
        if values.get(name):
            return values[name]
    return None


def write_dotenv_var(path, name, value):
    # меняет первую строку с этим именем, остальное не трогает; нет строки -- дописывает
    path = Path(path)
    lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
    new = f"{name}={value}"
    for index, line in enumerate(lines):
        if line.strip().startswith("#") or "=" not in line:
            continue
        if line.split("=", 1)[0].strip() == name:
            lines[index] = new
            break
    else:
        lines.append(new)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    tmp.chmod(0o600)
    tmp.replace(path)


def redact(text, secrets):
    for secret in secrets:
        if secret:
            text = text.replace(secret, "***")
    return text
