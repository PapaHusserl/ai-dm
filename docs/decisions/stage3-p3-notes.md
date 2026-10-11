# П3 этапа 3: решения при реализации (кабан-разработчик)
- `world_sim/triggers.check(bundle) -> CheckResult{fired, candidates}`: владельцы по порядку god, faction, npc, hero (по id).
  `TRUE` -> `fire` + `world.fired` (ref `trigger:<owner>:<id>`) + хроника `trigger` + кандидат `act`; `NEEDS_NARRATIVE` ->
  кандидат `verdict` с `residual`. Кандидаты отсортированы: verdict-триггеры, verdict-секреты, act; внутри -- вид владельца, id
  владельца, id триггера. Кандидат -- плоская модель (`owner_kind/owner_id/owner_name/motive/means`), не вложенный `owner`.
- NPC не `alive` (dead/gone/changed) не срабатывает и не даёт кандидатов; герой -- только `status == "active"`;
  бог -- только `status == "alive"`.
- Боги проверяются реже: схема WorldSim получила `god_checked_s: dict[god_id, секунды]` (время последней проверки, со
  срабатыванием или без). Первая проверка сразу, дальше -- не раньше `check_every_days` суток после предыдущей. Отпечаток
  `save_v3.schema.json` надо перегенерировать (Т-18).
- Секрет-кандидат: нераскрытый, `narrative_ok=False`, условие `NEEDS_NARRATIVE`, NPC жив и стоит в локации закрытой сцены
  (`current_scene.location_id`, не `hero.location_id`: при `location_changed` герой уже ушёл).
- `game/boundary.check_triggers` возвращает `CheckResult`; `finish_boundary` его пока не использует (вызов `world` -- П4).
- `reveal_secret`: открыт в explore (без strict), убран из `HIDDEN_TYPES`. FALSE и `NEEDS_NARRATIVE` без `narrative_ok` --
  `rejected` «ещё рано» (не `Invalid`, бюджет невалидных не тратится); уже раскрытый -- `accepted` без изменений; в `result` --
  текст секрета для рассказа.
- `relevant_npcs`: из NPC берутся только `named` и `alive` (как прежний `known_npcs`), затем в локации героя ∪ `key` ∪ с
  `is_ready`-триггером. В состоянии хода добавлено поле `secrets` (нераскрытые секреты живых NPC локации героя, с пометкой
  «скрыто: играй с учётом, не раскрывай»); `scene_npcs` не менялся.
- Ревью П3, R1: нераскрытые секреты живых NPC в локации -- общий хелпер `rules/secrets.hidden_secrets(world, location_id)`.
  Источник локации различается: промпт берёт локацию героя (ход идёт), кандидаты границы -- локацию закрытой сцены
  (`current_scene.location_id`; при `location_changed` герой уже ушёл).
- R2: `relevant_npcs` дополнительно включает именованных живых NPC, чьё `name` (без регистра) встречается в
  `session.offered_choices` или в `player_input`/`narration` всех `recent_turns` бандла.
- R4: секрет с нарративной частью условия до П4 всегда «ещё рано» (`reveal` при `NEEDS_NARRATIVE` без `narrative_ok`); в П4 роль
  `world` выставляет `narrative_ok` вердиктом.
- У `Faction` поля статуса нет, фильтр по статусу не нужен.
- Сторож архитектуры: только `game` импортирует `world_sim`, поэтому хелпер лежит в `rules/secrets.py`, а `relevance` не использует `candidates.current_hero` (свой цикл по героям).
