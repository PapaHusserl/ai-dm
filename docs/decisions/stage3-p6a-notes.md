# П6а этапа 3: решения при реализации (кабан-разработчик)
- `rules/divine.py`: `tier`, `approx_label`, `best_favor` (перенесён из `world_sim/mortality`, там реэкспорт импортом), `change_favor` (шаг ±2 `[favor] step`, ±3 за сцену
  `[favor] per_scene`, сумма модулей по фактическому сдвигу, шкала −10..10), `try_intervention`, `pay_debt`, `add_servant_trigger`, `can_pray/pray`, `change_deity`,
  `channel_divinity_blocked`, `locked_slot_pool`. Конфиг `[favor]` (`FavorConfig`, значения по умолчанию в самой модели).
- `favor_change{target, god_id, delta, reason}`: нарратор -- только `target=hero`, иначе Invalid `hero_only`; роль world -- только id NPC (без `then_ref`, одна модель
  на обе роли). Лимит сцены: герой -- ключ `god_id` в `scene.favor_spent`, NPC -- `npc_id:god_id`. Каждый ненулевой сдвиг пишется в хронику (`kind: favor`).
  `delta=0` -- Invalid. Заморозка (`hero.divine.frozen`) -- rejected. Соперник бога не меняется (G1а).
- `pray{god_id}` (видимый нарратору, G3б): favor >= 6, бог не заморожен, сегодня ещё не молились -- `prayer_day = день`; бог неизвестен -- Invalid; иначе rejected с сигналом.
  Первый критический бросок героя за день (`critical_moment` или `stakes=critical`, у RollRequest задан `now_s`) снимает `prayer_day` в None и ставит `prayer_used_day`
  (новое поле `DivineState`), поэтому повторно в тот же день помолиться нельзя. Помеха −6 -- `curse_day_used`. Источник модификаторов `DivineFavorSource`
  (`rules/modifiers/divine_favor.py`) зарегистрирован в `default_modifier_registry`; он сам тратит дневной запас (как реролл-эффекты мутирует актёра).
- `critical_moment`: `stakes_tags` добавляет флаг при `stakes=critical`; death save его уже имел. Спасбросков боя от «эффектов, способных убить/вывести» (`can_kill|can_remove`)
  в контенте нет -- не размечены.
- Вмешательство +9: хук `intervene(hero) -> god_id|None` в `death_saves.{check_three,roll_death_save,after_damage,resolve_out_of_combat}` и исход `"saved"`; вызывается
  перед каждым `mark_dead` (3-й провал, убивающий урон при 0 HP, мгновенная смерть по overkill). Бросок `rng.d(100) <= 50/75` (`[favor] intervention_percent_9/10`),
  только если есть бог с favor >= 9 из пантеона, не замороженный. `intervention_chapter` = id текущей главы (`""` -- только в тестах без главы; после П2 глава есть всегда), `intervention_god` -- кто вмешался (новое поле).
  Герой 1 HP в сознании; бог получает триггер `debt:<hero>:<n>` (`if: flag debt_paid:<hero>:<n> = false`, `once`, then из `[favor] debt_then`), `frozen` +бог, `debts` +id.
  Выплата -- `set_flag debt_paid:<hero>:<n>` (обработчик `set_flag` вызывает `divine.pay_debt`): триггер выключается, бог размораживается, если других долгов ему нет.
- Слуга −9: после `favor_change` героя, если tier = −3, богу добавляется триггер `servant:<hero>:<god>` (`if: favor god lte −9`, `then: "послать слугу"`, cooldown `[favor] servant_cooldown`);
  «бог-враг» понят как бог, чья благосклонность упала до −9.
- Жрец: `DivineCastSource` в `default_cast_check_registry()` (только герой-жрец с `deity_id`): ≤ −3 -- `CastCheck(ability_check wis, dc 10)` для 1+ круга, ≤ −9 -- `forbidden`.
  Бой: `castable_spells` не предлагает 1+ круг при `forbidden`; `cast.perform` после траты ячейки бросает проверку, провал -- событие `spell_wasted`. `rests.long_rest`: при ≤ −6 пул
  высшего круга (наибольший `spell_slot:N` с max > 0) не восстанавливается. Божественный канал: в контенте нет такого умения, есть только `divine.channel_divinity_blocked(hero)`.
- Игроку: `/sheet` -- строки «Бог: благосклонна/равнодушна/гневается»; `state_data.divine` -- `gods` (mood, omens от ±3, frozen), `can_pray`, `debts`.
- Смена бога: только `divine.change_deity` (favor нового +1, старые не трогаются); вызова из запросов/триггеров пака нет.
- Ревью: D1 -- `debt_scene` (id долга -> сцена вмешательства), `set_flag debt_paid` в той же сцене -- rejected «долг ещё не исполнен». D2 -- `add_exhaustion(..., intervene=)`: на 6-й степени
  вмешательство вместо смерти, степень 5 (путь `defeat_outcome exhaustion`; HP при вмешательстве ставится в 1 только при 0 HP). D3 -- `prayer_god`: преимущество только если у бога
  favor >= 6 и он не заморожен. `favor_change` отдаёт модели `mood` и `applied`, а не число шкалы.
