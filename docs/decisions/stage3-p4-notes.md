# П4 этапа 3: решения при реализации (кабан-разработчик)
- Набор инструментов `world` (8): `world_verdict`, `world_notice`, `skill_check`, `saving_throw`, `set_flag`, `npc_create`,
  `location_create`, `npc_update`. `favor_change`, `event_start/event_end`, `warn_danger` из закрытого списка плана в набор
  пока не входят: их обработчики появляются в П5/П6 (в `HIDDEN_TYPES` они остаются), тогда же добавляются в `MODE_TOOLS["world"]`.
  Strict: `world_verdict`, `world_notice`, `skill_check`, `saving_throw`, `set_flag`; без strict -- `npc_create`, `location_create`,
  `npc_update` (как в explore).
- Схемы нарратора не менялись: закадровые версии запросов (`actor` у проверок, `location_id` и `then_ref` у `npc_update`) --
  отдельные модели `WORLD_MODELS` в `protocol/requests.py`; `REQUEST_MODELS`/`ALL_TYPES` (28) нетронуты. `parse_request(data, mode)`,
  `tool_defs(exposed, mode)`; `WORLD_HANDLERS` в `protocol/apply.py`, обработчики -- `protocol/handlers/offscreen.py`.
- `then_ref` обязателен только у `npc_update` и должен быть ref любого кандидата вызова (act или verdict): `then` подтверждённого
  вердиктом триггера world исполняет в том же вызове. Иначе `Invalid(invalid_then_ref)`.
- `world_verdict`: `Invalid(invalid_verdict_refs)` при лишних/пропущенных/повторных ref; повторный вызов после принятого --
  `Invalid(verdict_done)`. Обязательность при verdict-кандидатах -- через `MasterSession.required_tool("world")`. Применение
  вердиктов (fire, `world.fired`, хроника `trigger`, `narrative_ok`) -- в `world_sim/verdicts.apply_verdicts` после вызова, не в обработчике
  (protocol не знает world_sim).
- Закадровая проверка NPC (`actor`): d20 без бонуса (у NPC нет листа характеристик), СЛ по категории; состояние -- `NPC.creature` или временное.
  Мёртвый/неизвестный NPC -- Invalid.
- `world_notice`: все заметки в `world.notices` (`deliver_at_s = now + delay`: none 0, day 86400, week 604800); `hidden` дополнительно
  пишет хронику `kind: event`. Доставка (`visible|rumor`) -- прежний `deliver_notices` на границе.
- Потолок `world.max_calls_per_day` (`[world]` в `app_defaults.toml`, `AppConfig.world`): при достижении из кандидатов остаются только
  `act` (их `then` всё равно исполняются вызовом); без `act` вызова нет. Счёт дня -- `sim.world_calls_today` + новое поле
  `sim.world_calls_day` (день `now_s // 86400`, -1 = счёта нет); пишется только когда вызов состоялся. Отпечаток `save_v3.schema.json`
  надо перегенерировать (вместе с `god_checked_s` из П3).
- Вход вызова: `master/world.py: WorldPromptBuilder` (`system[0]` -- `prompts/world_rules.md`, `system[1]` -- tone, lore, truths, пантеон;
  `messages[0]` -- JSON: время/сезон/праздник, закрытая сцена, герой, кандидаты, релевантные NPC и их локации, `location_ids`,
  активные события, `dangers`). «Известность героя» из плана в схеме не существует -- не передаётся. Модель запроса -- `roles.world`
  (или профиль по модели адаптера). `master` не импортирует `world_sim`: кандидаты приходят объектами из `game`.
- `WorldSession.run` работает на копии границы, rng берёт из бандла и возвращает обратно. Журнал: `role: world`, `run_id = bnd-<stamp>-<n>`
  (`TurnRunner.next_boundary_id`), `turn_status` ставит `TurnRunner.take_boundary` по `BoundaryResult.world_run_id`.
- `finish_boundary(bundle, cfg, registry, world=None, run_id=None)`: `world=None` -- вызова нет (старые вызовы без изменений).
  `TurnRunner(world_adapter=None)` -- адаптер нарратора (контракт `world_kit`); в CLI адаптер world всегда свой.
- Пустой финал роли `world` после раунда инструментов -- нормальный конец (рассказа она не пишет).
- Replay по ролям: `ReplayAdapter(records, role=None)`; CLI: `--replay` создаёт два адаптера (narrator, world). Новый флаг `--mock-world PATH`;
  `--mock` без него -- world идёт через мок рассказчика. Профиль world для CLI -- `pick_world` (тот же провайдер, что у рассказчика).
- `devtools/world_run.py` лежит в `src/ai_dm/devtools/` (рядом с `sim_combat.py`): `run_world(...)`, `main(argv)`. «Нарратор» без модели:
  `clock.advance(DAY)` + `close_boundary("end_scene")` + `finish_boundary`. Дневной тик (смертность, сезон) -- П5; до неё сид на хронику не влияет.
- Журнал: `report_tags` записей world пустой (запись пишется до исполнения запросов, как у нарратора).

## Ревью П4
- B1: у броска хранится бросавший (`ctx.roll_actors`); смерть/уход за кадром принимается только с `evidence_ref` броска этого же NPC.
- B2: `then_ref` на verdict-кандидата -- только после `world_verdict` с `holds=true` по нему (`verdict_not_confirmed`).
- D3: в режиме world `actor` у проверок обязателен (`actor_required`), бросков героя за кадром нет.
- D4: без отдельного адаптера world модель = `profiles[провайдер адаптера].world` (нет профиля, например мок, -- `roles.world`);
  `/model narrator` при смене провайдера пересоздаёт адаптер world на профиль нового провайдера (если world был настоящим).
- D5: `then_ref` необязателен у `set_flag` и `world_notice` (отдельные модели `WorldSetFlag`, `WorldNotice.then_ref`); указан на verdict --
  правило B2. Принятый риск: без `then_ref` модель может творить свободные закадровые события, не привязанные к кандидату.
- D6: `apply_verdicts` пропускает кандидата, чей триггер/секрет исчез. D7: запись хроники -- `state/memory.add_entry`
  (`world_sim.chronicle` её реэкспортирует).
- M8: `messages[0]` у world с `cache=True` -- осознанно (повторяется в раундах инструментов одного вызова). M9: `user_input`/`world_text`
  в `WorldPromptBuilder.build` не используются (общий интерфейс). M11: отпечаток `save_v3.schema.json` перегенерируется отдельным шагом (тесты).
