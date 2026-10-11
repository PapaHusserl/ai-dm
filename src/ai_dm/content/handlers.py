from collections.abc import Callable

# Реестр именованных обработчиков для умений, которые не выразить элементарными эффектами.
# Загрузчик проверяет, что handler.name из YAML есть в этом словаре.
HANDLERS: dict[str, Callable] = {}


def is_known_handler(name: str) -> bool:
    return name in HANDLERS
