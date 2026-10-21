# Все русские строки TUI (этап 5, A7). Встроенных английских строк Textual в интерфейсе нет.
TITLE = "ИИ-мастер"
PLACEHOLDER = "Что делает герой? Команды начинаются с «/» (табуляция или → — дополнить)"

KEY_SIDE = "Панель героя"
KEY_QUIT = "Выход"
KEY_NONLETHAL = "Оглушающий"
KEY_MORE = "Ещё"

THINKING = "Мастер думает…"
QUIT_WAITING = "Выход после хода, с сохранением (Ctrl+C ещё раз — без сохранения)"
LIMIT = "лимит {percent}%"

TITLE_HERO = "Герой"
TITLE_COMBAT = "Бой"
TITLE_COMBAT_LOG = "Ход боя"
TITLE_ACTIONS = "Действия"
TITLE_ROLLS = "Броски"
TITLE_GAINS = "Получено"
TITLE_PICTURE = "Рисунок"

ECHO = "▸ Ты: {line}"
ORNAMENT = "✦ ─── ✦"

KEY_CLOSE = "Закрыть"
CLOSE = "Закрыть"
COST_COLUMNS = ("Период", "Роль", "Модель", "Сумма")
PICK_HINT = "(цифра или щелчок мыши)"
CREATE_PLACEHOLDER = "Ответ мастеру или номер пункта меню (Esc — отмена)"
STEPS_PLACEHOLDER = "Номер пункта или значение («назад» — шаг назад, Esc — отмена)"
CREATE_CANCELLING = "Отмена после ответа мастера"
MODAL_TITLES = {
    "/sheet": "Лист героя",
    "/inv": "Инвентарь",
    "/shop": "Торговля",
    "/lore": "Журнал знаний",
    "/spells": "Заклинания",
    "/abilities": "Умения",
    "/cost": "Расход",
    "/model": "Модель",
}
SCENE_LINE = "─── {title} ───"
MODEL_PICK = "Модель рассказчика (цифра, щелчок или Enter, Esc — закрыть без смены):"
MODEL_CURRENT = "{key} (текущая)"
MODEL_CHANGED = "Модель рассказчика: {key}."
LORE_PICK = "Кто и что (стрелки, Esc — закрыть):"
SPELL_PICK ="Заклинание (цифра, щелчок или Enter, Esc — закрыть):"
SPELL_CAST = "Применяю заклинание «{name}»."
SPELL_NO_SLOT = "нет ячейки"
SPELL_BUSY = "сейчас недоступно"
SPELL_NO_DESCRIPTION = "Описания нет."
INV_PICK = "Предмет (Enter — действие по умолчанию, e/l/u/r/d — действие, Esc — закрыть):"
INV_EQUIP = "Надеть"
INV_EQUIP_LEFT = "В левую руку"
INV_UNEQUIP = "Снять"
INV_UNEQUIP_LEFT = "Снять из левой руки"
INV_COMBAT_POTION = "В бою — меню, пункт «Использовать»."
INV_DRINK = "Выпить"
INV_NO_ACTIONS = "Действий нет."
INV_SLOT_WORDS = {"armor": "доспех", "shield": "щит", "main_hand": "правая", "off_hand": "левая"}

NONLETHAL_ON = "Оглушающий: вкл"
NO_TARGET = "Цель: нет в досягаемости"
TARGET_ONE = "Цель: {name} {hp} ({number}/{total}) Tab"
MORE_TITLE = "Ещё…"
MORE_PICK = "Все варианты хода (цифра, щелчок или Enter, Esc — закрыть без хода):"
NO_ROW = "Нет такой строки."
MENU_GONE = "Вариант больше недоступен."
COMBAT_HINT_TUI = (
    "Цифры — строки меню, табуляция — сменить цель, «Ещё…» — остальное. "
    "Можно словами: «стреляю в гоблина и отхожу на уступ» — ход соберётся из нескольких шагов."
)
