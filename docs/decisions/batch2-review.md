# Решения по ревью партии 2 (спецификация правок)

Источник: ревью мамы-кабана партии 2. Решения принимает оркестратор в рамках ARCHITECTURE.md.
Все пункты меняют схему сейва/контента — делаются до шага 22 (отпечаток схемы), миграции не нужны.
Исполнители: кабан «state» (S), кабан «content+rules» (C), кабан-доеба (T) — тесты на всё ниже.

## 1. Состояние (`src/ai_dm/state/`) — исполнитель S

1.1. **Нет float в сейве.** `GlobalEvent.mortality_multiplier: int = Field(1, ge=0)`.
     Тест-сторож: в `SaveBundle.model_json_schema()` нет `"type": "number"` (рекурсивно).
1.2. **`GlobalEvent` по ТЗ 4.1.2:**
     - `hazard: EventHazard | None`, `EventHazard {save: Ability, dc_category: DcCategory}`;
     - `started_s: int | None` (вместо `started: str`); `ends_at_s: int | None`; `ends_when: Condition | None`.
     - Перевод дат пака в секунды — при загрузке пака (этап 3), не сейчас.
     - `NPC.birth_date: str` → `birth_s: int | None`.
     - `Ability` = `Literal["str","dex","con","int","wis","cha"]`, `DcCategory` =
       `Literal["very_easy","easy","medium","hard","very_hard","nearly_impossible"]` — объявить в
       `ai_dm/content/models/common.py` (рядом с `ABILITIES`), state импортирует оттуда.
1.3. **Благосклонность по богам:** `HeroState.favor` и `NPC.favor` → `dict[str, int]`, значения −10..10 (валидатор).
1.4. **Связи локаций:** `Connection {to: str, distance_m: int (ge=0)}`; `Location.connections: list[Connection]`.
1.5. **`ActiveEffect`** (`state/creature.py`): `id: str`, `source: str`, `kind: str`,
     `params: dict[str, int | str | bool]`, `expires: Expiry | None`;
     `Expiry {kind: Literal["rounds","end_of_turn","start_of_turn","seconds","concentration"], value: int = 0, owner: str | None}`.
     `CreatureState.active_effects: list[ActiveEffect]`.
1.6. **Состояния с источником:** `CreatureState.conditions: list[AppliedCondition]`,
     `AppliedCondition {id: str, source: str | None, expires: Expiry | None}`.
1.7. **`DeathRecord`** (`state/death.py`): `cause: Literal["goal","hazard","chance","old_age"]`,
     `by: str | None`, `at_s: int`, `location_id: str | None`, `text: str = ""`.
     `HeroState.death`, `NPC.death` → `DeathRecord | None`.
1.8. **`Trigger.state: Literal["active","fired","disabled"] = "active"`**; `cooldown` валидируется через
     `Duration.parse` (`field_validator`).
1.9. `WorldState.settings: dict[str, int | str | bool]`.
1.10. `Equipped.off_hand: str | None = None`.
1.11. `CharacterSheet.spells_prepared: list[str] = []` (в дополнение к `spells_known`).
1.12. `NPC.means`: `min_length=1, max_length=3`.
1.13. `WorldState.npcs|factions|pantheon|locations`: валидатор «ключ словаря == obj.id».
1.14. `Memory.*`: `list[dict]` вместо голого `list`.
1.15. Переименовать класс условия `Any` → `AnyOf`, `All` → `AllOf`, `Not` → `NotOf` (YAML-тип по-прежнему
      `any`/`all`/`not`), чтобы не затенять `typing.Any`.
1.16. Заглушками остаются до своих этапов: `afterlife`, `Chronicle.entries`, `Memory.*`,
      `session.current_scene|current_chapter`, `NPC.combat`. `SessionState.active_combat` и
      `pending_decision` типизируются в партии 5 (шаги 15–21), до шага 22.

## 2. Контент (`src/ai_dm/content/`, `srd/data/`) — исполнитель C

2.1. **Закрытые значения effects** (`content/models/common.py`):
     - `add: Literal["proficiency_bonus","spellcasting_modifier","class_level"] | None` + `class_id: str | None`
       (обязателен при `add == "class_level"`); `check_refs` проверяет `class_id`;
     - `target`, `when`, `mode`, `shape` — `Literal` с перечнем значений, которые читает движок
       (собери из текущего YAML; новое значение = правка Literal);
     - `count` разделить: `targets: int | None` (число целей, Bless), `count` — количество (дротики, выборы).
     - Всё сложнее — только через `handler`.
2.2. `SKILLS` перенести из `rules/derived.py` в `content/models/common.py` (`Skill` Literal); rules импортирует оттуда.
2.3. **Загрузчик:** собирать ошибки всех файлов, а не падать на первом; проверять ссылки
     `EffectSpec.condition` → состояния, навыки в `skill_choices.options` и предысториях → `Skill`,
     `background.feat` → черта категории `origin`.
2.4. `Monster.abilities: dict[Ability, int]` (все 6).
2.5. **Заклинания:** `range_kind: Literal["self","touch","ranged"]` + `range_ft: int | None` (для ranged);
     `duration: str` в формате `Duration` (`1m` = 1 минута, `instant`/`instantaneous` → `None`) — поле
     `duration_s: int | None`; усиление — данными: `upcast: {per_slot_level: {dice?: str, count?: int}} | None`,
     рост заговора — `cantrip_scaling: {5: dice, ...} | None`.
2.6. **Классы:** `Spellcasting.progression: Literal["full","half"]`; убрать `HALF_CASTERS` из кода.
     Плут: `weapon_training_properties: list[Literal["finesse","light"]]` — владение воинским оружием с любым
     из свойств (по SRD 5.2); учесть в `attack_bonus`.
2.7. **Ресурсы данными:** `EffectSpec(kind="resource")` получает `pool: str`, `max: int | None`,
     `max_add` (как `add`), `recover: list[{on: Literal["short_rest","long_rest"], amount: int | "all"}]`.
     Second Wind: max 2, short_rest +1, long_rest all. Ключи пулов: `second_wind`, `spell_slot:1`…`spell_slot:9`.
2.8. **Таблицы SRD данными:** `srd/data/tables/{xp,proficiency,dc,cr_xp}.yaml` + модель `Table`;
     `progression.py` и проверки читают таблицы из реестра (вид `table`).
2.9. **Предыстории SRD:** добавить стартовое снаряжение и золото по SRD 5.2 (вариант A — набор предметов,
     вариант B — золото); `BackgroundSpec.equipment: list[str]`, `gold_cp: int`; валидатор проверяет id предметов.
     Предметы, которых нет в минимуме, — добавить простыми записями `items/` (без механики) или опустить с
     пометкой в отчёте.
2.10. **Монстры по SRD 5.2:** Goblin Warrior — +1d4 урона при атаке с преимуществом (скимитар и короткий лук);
      Goblin Boss — сверить действия по SRD 5.2 (в т.ч. Shortbow вместо метательного копья, если так в 5.2),
      мультиатака — полем данных `multiattack: [{action, count}]`. Если не уверен — указать в отчёте.
2.11. Навыки волшебника по SRD 5.2 (добавить Nature, если так в 5.2 — сверить).
2.12. Вид человека: Skillful (1 навык на выбор) и Versatile (черта происхождения на выбор) — механически,
      через `CharacterChoices.species_choices`. Dwarven Toughness, Keen Senses, Darkvision — трек 1.5.

## 3. Правила (`src/ai_dm/rules/`) — исполнитель C

3.1. `builder`:
     - `fighting_style` — только если у класса есть умение `fighting_style` (иначе `fighting_style_invalid`);
     - повторы в `weapon_masteries` и мастерство по оружию без владения → `mastery_weapon_invalid`;
     - пересечение навыка класса с навыком предыстории → `class_skills_invalid`;
     - `abilities_invalid`: значения `explicit` вне 3..20 до бонуса и > 20 после бонуса;
     - `spells: list[str]` в `CharacterChoices`: заклинание в списке класса и круг ≤ доступного
       (код `spells_invalid`); заговоры и заклинания 1 круга по числу из класса (если данных нет — без ограничения
       количества, пометить в отчёте);
     - заводит пулы ресурсов (`second_wind`, `spell_slot:N`) и выдаёт снаряжение/золото предыстории;
     - человеческие Skillful/Versatile через `species_choices` (код `species_choices_invalid`);
     - сообщения ошибок — человекочитаемые по-русски, не `"предыстория: {code}"`.
     - коды `item_unknown`, `equip_invalid` — оставить, задокументировать в контракте.
3.2. `derived`: одна функция `effect_amount(effect, hero, registry)` для КД, инициативы и пр.; ячейки — по
     `Spellcasting.progression`.
3.3. `progression`: таблицы из реестра; `level_up` обновляет пулы ресурсов; docstring — вызывающий проверяет опыт.
3.4. `inventory`:
     - `pick_valuables` тасует только группы ничьих, которые нужны до набора `count`, и только различные id;
       неизвестный id → `InventoryError`;
     - `equip`: двуручное оружие со щитом → ошибка; доспех без владения → ошибка (`InventoryError`);
     - `use_item` остаётся как есть; на шаге 11 переводится на `rules/healing.py` (пометка TODO в коде).

## 4. Документы — оркестратор
- A2/A6 в ARCHITECTURE.md приводятся к фактической раскладке (`state/save.py`, NPC/Location в `world.py`,
  `srd/data` — файл на объект), `distance_m` вместо `distance_km`.

## 5. Разделение файлов между исполнителями (чтобы не конфликтовать)
- S: только `src/ai_dm/state/**`. Импортирует `Ability`, `DcCategory` из `ai_dm.content.models.common`
  (уже объявлены оркестратором), сам `common.py` не трогает.
- C: `src/ai_dm/content/**`, `src/ai_dm/srd/data/**`, `src/ai_dm/rules/**`. Может читать state, но не правит его;
  если для пункта 3.x нужно поле state из раздела 1 — оно появится у S, ориентироваться на имена из раздела 1.
- T: только `tests/**`.
