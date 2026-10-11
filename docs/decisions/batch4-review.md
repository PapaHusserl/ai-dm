# Решения по ревью партии 4 (спецификация правок)

Источник: ревью мамы-кабана партии 4. Решения — оркестратор в рамках ARCHITECTURE.md.
Исполнители: кабан (K) — `src/**`, `docs/**` кроме TZ; кабан-доеба (T) — `tests/**`. Параллельно.

## Блокирующие

**B1. `world_id` безопасен.** `layout.check_world_id(world_id)`: непустой, только `[\w-]` (юникодные буквы,
цифры, `_`, `-`), не начинается с `.`, без `/`, `\`, `..`; иначе `ValueError`. Вызывается из `slot_dir`
(значит — во всех входах store/backup). Абсолютный путь невозможен.
`slot_dir` проверяет и `world_id`, и имя слота.

**B2. Мир — по каталогу.** `write_slot(root, world_id, bundle, slot, *, saved_at)` — `world_id` явным аргументом;
`load_slot` при `bundle.world.world_id != world_id` или `manifest.world_id != world_id` → `ValueError`
(до бэкапа и до записи); миграция перезаписывает именно загружаемый каталог.

**B3. Уникальность героев в сейве.** `write_slot` до записи проверяет уникальность `hero.id` и имён каталогов
`hero_dir_name`; повтор → `ValueError`, слот не тронут.

**B4. Ротация без моделей.** `move_slot` правит `manifest.json` как сырой JSON (`raw["slot"] = new_name`),
без `Manifest.model_validate_json`. Принцип (записать в ARCHITECTURE A3): persistence никогда не читает
файлы старой версии текущими моделями — только сырой dict до миграции.

**B5. Мусор в каталогах.** При чтении `heroes/` и `slots/` учитываются только каталоги, имя которых не
начинается с `.` (`.DS_Store`, `.tmp-*`, `.old-*` игнорируются).

**B6. Нарратив с логикой.** `Evaluation` получает `residual: Condition | None` — остаток дерева условия:
выполненные структурные листья выброшены (TRUE-ветки `all` убираются, `any` с TRUE → вся ветка TRUE),
нарративные листья и `not`/`all`/`any` над ними сохранены. При `truth == NEEDS_NARRATIVE` residual — непустое
дерево (оно уходит модели `world`), при TRUE/FALSE — `None`. `narrative: list[str]` остаётся (плоский список
текстов для промпта). Тест «not: тот же narrative» заменяется: `{not: {narrative: X}}` → residual `NotOf(Narrative(X))`.

## Желательные (делаются в этой же партии)

**D1.** `load_slot` до бэкапа проверяет, что цепочка миграций полна (`MigrationMissing` без бэкапа, файлы не тронуты);
коллизия имени бэкапа → суффикс `-2`, `-3`…
**D2. Восстановление.** `recover_slots(root, world_id)` вызывается в начале `list_slots` и `load_slot`:
- `.old-*` есть, а слота с именем из его `manifest.slot` (сырой JSON) нет → вернуть на место; иначе удалить;
- `.tmp-*` с `manifest.json` (запись полная) → поставить на место, если слота нет; иначе удалить;
- `.tmp-*` без `manifest.json` → удалить.
Порядок: сначала `.tmp-*` (полный — новая запись, ставится на место), затем `.old-*` (удаляется, если слот уже есть).
Durability при отключении питания (fsync, F_FULLFSYNC) — вне этапа 1 (записать в BACKLOG одной строкой).
**D3.** `load_slot` после валидации ставит `bundle.manifest.slot = slot` (истина — каталог). Удаление `auto-<keep>`
при ротации — через `os.replace` в `.old-<uuid>`, затем rmtree.
**D4.** (T) тест на падение второго `os.replace` (откат old→final).
**D5.** (T) тесты m0001 сравнивают с литералами, не с `Memory()`/`Tone()`. (K) m0001 — `setdefault` вместо перезаписи.
**D6.** Порядок «типизация боевой сессии после отпечатка» записан здесь осознанно: **партия 5 обязана**
типизировать `SessionState.active_combat` (`CombatState | None`) и `pending_decision` (`DecisionPoint | None`) и
перегенерировать `tests/schema/save_v1.schema.json` без подъёма версии. (T) сторож: в `SessionState` нет полей
типа голый `dict` — `xfail(strict=True)` до партии 5 только для `active_combat`/`pending_decision`/`current_scene`/
`current_chapter`. Чек-лист релиза этапа 1 — пункт в BACKLOG: «в SaveBundle.session нет голых dict».
**D7.** `event_active` учитывает время: `(started_s is None or started_s <= now_s) and (ends_at_s is None or now_s < ends_at_s)`,
`now_s = world.clock.now_s`. `validate_refs` **не** проверяет `event_active` (события возникают позже по TZ 4.1.2).
**D8.** `validate_refs(cond, world, registry=None)`: при переданном реестре `hero_has` проверяется по предметам
(weapon/armor/item).
**D9.** `flag`: совпадение только при `isinstance(v, bool) and v == condition.value`; не-bool → FALSE.
**D10.** `secrets.reveal(..., narrative_confirmed: bool = False)`: при NEEDS_NARRATIVE и `narrative_confirmed=True`
раскрывает. `Rejected` переносится в нейтральный `rules/results.py` (mortality_guard и secrets импортируют оттуда;
реэкспорт из mortality_guard сохранить).
**D11.** Контракт событий для партии 5 (записать в ARCHITECTURE шаги 13/21): `location_visited {id}`,
`combat_ended {id}`, `item_gained {hero, item}` — ровно эти ключи. `hero_died → hero_dead:<id>` — принято.
**D12.** Имена слотов — только строчные (`manual-A` → `ValueError`); `make_backup(root, world_id, slot, old_version, ts=None)`
(без `folder`); `evaluate(..., hero=None)` допустим — условия о герое (`hero_has`, `hero_at`, `hero_dead`, `favor`) → FALSE.

## Тесты (T)
По B1–B6, D1–D12: world_id с `..`/`/`/абсолютный/пустой/`.x` → ValueError во всех входах; переименованный каталог
мира + v0 → ValueError, ничего не записано; два героя с одним ordinal+именем / одним id → ValueError, слот цел;
ротация с v0-фикстурой в `auto` и в `auto-1`; `.DS_Store` в `heroes/` и `slots/`; residual для not/all/any над
нарративом и смешанных деревьев; MigrationMissing дважды подряд с одним ts → 0 бэкапов; коллизия бэкапа → `-2`;
recover_slots (три сценария); `manifest.slot` после загрузки = каталог; второй os.replace падает → откат;
m0001 с литералами и setdefault; xfail-сторож SessionState; event_active по времени; validate_refs с registry;
flag с int-значениями; reveal с narrative_confirmed; `Rejected` из `rules.results`; заглавные в слоте; evaluate с hero=None.
