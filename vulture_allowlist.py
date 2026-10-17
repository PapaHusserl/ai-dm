# vulture allowlist: только глушение шума; кандидатов сюда не вносить без решения пользователя.
# Поля pydantic-моделей: читаются через YAML / model_dump, vulture их не видит.
quest_minor_percent  # unused variable (src/ai_dm/config/settings.py:51)
quest_medium_percent  # unused variable (src/ai_dm/config/settings.py:52)
quest_major_percent  # unused variable (src/ai_dm/config/settings.py:53)
license  # unused variable (src/ai_dm/content/models/common.py:110)
versatile_dice  # unused variable (src/ai_dm/content/models/items.py:16)
strength_min  # unused variable (src/ai_dm/content/models/items.py:28)
reach_ft  # unused variable (src/ai_dm/content/models/monsters.py:15)
hp_dice  # unused variable (src/ai_dm/content/models/monsters.py:30)
size  # unused variable (src/ai_dm/content/models/monsters.py:31)
size  # unused variable (src/ai_dm/content/models/species.py:6)
per_slot_level  # unused variable (src/ai_dm/content/models/spells.py:19)
school  # unused variable (src/ai_dm/content/models/spells.py:24)
upcast  # unused variable (src/ai_dm/content/models/spells.py:33)
epoch_note  # unused variable (src/ai_dm/core/clock.py:50)
strict  # unused variable (src/ai_dm/llm/types.py:22)
signal_to_master  # unused variable (src/ai_dm/protocol/decision.py:10)
budget_override_reason  # unused variable (src/ai_dm/state/combat.py:104)
subject  # unused variable (src/ai_dm/state/combat.py:124)
attacker  # unused variable (src/ai_dm/state/combat.py:125)
tool_proficiencies  # unused variable (src/ai_dm/state/hero.py:31)
fate  # unused variable (src/ai_dm/state/hero.py:90)
afterlife  # unused variable (src/ai_dm/state/hero.py:105)
legacy_links  # unused variable (src/ai_dm/state/hero.py:106)
game_summary_chapter  # unused variable (src/ai_dm/state/memory.py:57)
schema_version  # unused variable (src/ai_dm/state/save.py:11)
engine_version  # unused variable (src/ai_dm/state/save.py:12)
touched_main  # unused variable (src/ai_dm/state/scene.py:23)
hero_initiated_combat  # unused variable (src/ai_dm/state/scene.py:24)
pending_decision  # unused variable (src/ai_dm/state/session.py:36)
mood  # unused variable (src/ai_dm/state/world.py:17)
violence  # unused variable (src/ai_dm/state/world.py:18)
horror  # unused variable (src/ai_dm/state/world.py:19)
romance  # unused variable (src/ai_dm/state/world.py:20)
hard_limits  # unused variable (src/ai_dm/state/world.py:22)
soft_limits  # unused variable (src/ai_dm/state/world.py:23)
dc_category  # unused variable (src/ai_dm/state/world.py:31)
pleased_by  # unused variable (src/ai_dm/state/world.py:106)
angered_by  # unused variable (src/ai_dm/state/world.py:107)
realm  # unused variable (src/ai_dm/state/world.py:111)
campaign_version  # unused variable (src/ai_dm/state/world.py:220)
# Задел v11 (Ж0, решение пользователя 2026-10-17): убрать строку, когда поле начнут читать.
family  # unused variable (src/ai_dm/state/hero.py:211, world.py:100) -- Ж1+
knowledge  # unused variable (src/ai_dm/state/hero.py:213) -- Ж3
KNOWLEDGE_KINDS  # unused variable (src/ai_dm/state/knowledge.py:4) -- Ж3
KNOWLEDGE_SOURCES  # unused variable (src/ai_dm/state/knowledge.py:5) -- Ж3
from_ref  # unused variable (src/ai_dm/state/knowledge.py:18) -- Ж3
GOAL_KINDS  # unused variable (src/ai_dm/state/relations.py:12) -- Ж0 подшаг 2
ref_kind  # unused variable (src/ai_dm/state/relations.py:47) -- Ж1+
scene_mood  # unused variable (src/ai_dm/state/scene.py:32) -- Ж3
known_name  # unused variable (src/ai_dm/state/world.py:99) -- Ж1
services  # unused variable (src/ai_dm/state/world.py:104) -- У0
pending_acts  # unused variable (src/ai_dm/state/world.py:225) -- BACKLOG 46
# API Textual: вызывается фреймворком (src/ai_dm/ui/tui/__init__.py).
ENABLE_COMMAND_PALETTE  # unused variable
compose  # unused method
on_mount  # unused method
on_input_submitted  # unused method
disabled  # unused attribute
# P2: то же (имена глобальные, vulture по файлу не сужает), поля и обработчики App/виджетов Textual (src/ai_dm/ui/tui/{app,widgets}.py).
CSS_PATH  # unused variable
BINDINGS  # unused variable
on_resize  # unused method
action_toggle_side  # unused method
action_quit_game  # unused method
border_title  # unused attribute (Textual: атрибут только присваивается)
# P3: обработчики и атрибуты Textual (src/ai_dm/ui/tui/{app,widgets,modals}.py).
on_choices_picked  # unused method
on_button_pressed  # unused method
action_close  # unused method
action_cancel  # unused method
on_click  # unused method (обработчик, зовёт фреймворк)
closing  # unused attribute (публичный флаг для тестов: test_commands_both_modes, test_tui_entry_points)
# Меню боя «сначала цель» (согласие пользователя 2026-10-06): клавиши и сообщения Textual (ui/tui/{app,modals}.py).
action_next_target  # unused method
action_prev_target  # unused method
action_toggle_nonlethal  # unused method
action_menu_back  # unused method
on_combat_menu_picked  # unused method
on_combat_menu_target_picked  # unused method
on_option_list_option_selected  # unused method
# Кастомные предметы, партия А: поля читаются в партиях Б/В (убрать, когда начнут читаться).
created_s  # unused variable
# AD1 (согласие проектировщика 2026-10-08, Q2 и ревью): заделы, протоколы, поля конфига, kit-ы тестов.
Controller  # unused class (combat/controllers.py, протокол контроллеров)
ScriptedController  # unused class (combat/controllers.py)
ModelAdapter  # unused class (llm/adapter.py, протокол адаптера)
spread_morale  # unused variable (поле конфига [parley])
change_deity  # unused function (rules/divine.py, блок Ж2)
level_for_xp  # unused function (rules/progression.py, блок К0)
proficiency_bonus  # unused function (rules/progression.py, блок К0)
ranger_choices  # unused function (game/starter.py, пресет Грея для kit-ов тестов)
new_world  # unused function (game/starter.py, мир Вейла для kit-ов тестов)
VISIBLE_TYPES  # unused variable (protocol/requests.py: реестр типов, на нём держатся тесты схемы вместе с ALL_TYPES/NPC_ONLY_TYPES)
# AD1: API Textual (ui/tui/{modals,widgets}.py).
highlighted  # unused attribute
on_option_list_option_highlighted  # unused method
action_complete  # unused method
# постоянно: поля схемы инструмента hero_sheet (AbilityScores), читаются через model_dump
con  # unused variable (protocol/requests.py)
str_  # unused variable (protocol/requests.py)
int_  # unused variable (protocol/requests.py)
wis  # unused variable (protocol/requests.py)
cha  # unused variable (protocol/requests.py)
# К0а (решение проектировщика 2026-10-11): поля сейва v9 под К1/К5 -- снять, когда появятся читатели
until_s  # unused variable (state/creature.py: Concentration, TempForm)
temp_hp_granted  # unused variable (state/creature.py)
temp_form  # unused variable (state/creature.py)
