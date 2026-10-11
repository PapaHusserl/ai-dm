# Ручной живой вызов (не pytest, в тестах не запускается): один короткий вызов narrator-роли
# с одним strict-инструментом. Нужен ключ в окружении или в .env.
# Запуск: uv run python devtools/live_smoke.py anthropic
#         uv run python devtools/live_smoke.py gemini --model gemini-3.8-flash
import argparse
import sys

from ai_dm.config.app import load_settings
from ai_dm.llm.cost import cost_nano
from ai_dm.llm.errors import LlmError
from ai_dm.llm.factory import make_adapter
from ai_dm.llm.types import ChatRequest, Message, SystemBlock, Text, ToolSpec
from ai_dm.protocol.schema import tool_set


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="live_smoke")
    parser.add_argument("provider", choices=("anthropic", "gemini"))
    parser.add_argument("--model", default=None)
    parser.add_argument("--dotenv", default=".env")
    args = parser.parse_args(argv)

    cfg = load_settings().app
    role = cfg.roles.narrator
    if args.provider == "gemini":
        role = cfg.profiles["gemini"].narrator
    model = args.model or role.model
    tool = next(t for t in tool_set("explore") if t["strict"])
    request = ChatRequest(
        role="narrator",
        model=model,
        system=[SystemBlock(text="Ты мастер игры. Если нужна проверка, вызови инструмент.")],
        tools=[ToolSpec.model_validate(tool)],
        messages=[Message(role="user", content=[
            Text(text="Герой пытается убедить стражника пропустить его. Вызови инструмент."),
        ])],
        max_tokens=1000,
        effort=role.effort if model == role.model else None,
    )
    try:
        adapter = make_adapter(args.provider, model, cfg, dotenv_path=args.dotenv)
        response = adapter.complete(request)
    except LlmError as error:
        print(f"ошибка {type(error).__name__}: {error}")
        return 1
    print("stop_reason:", response.stop_reason)
    print("request_id:", response.request_id)
    print("usage:", response.usage.model_dump())
    price = cfg.prices.get(model)
    if price is None:
        print("стоимость: нет цены модели в конфиге")
    else:
        print("стоимость, нано-$:", cost_nano(response.usage, price))
    for block in response.content:
        print(block.type, block.model_dump(mode="json"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
