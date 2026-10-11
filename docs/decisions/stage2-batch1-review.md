# Ревью партии 1 этапа 2: технические правки (оркестратор)

Вердикт мамы-кабана: можно мержить. Правки до партии 2:
1. `m0002.is_turn` — запись с ключами вне `{turn_seq, at_s, player_input, narration, requests, rolls}` отбрасывается (+ тест).
2. `individual_treasure.yaml` — комментарий «числа не сверены с SRD 5.2 (трек 1.5); если таблицы нет в SRD — source: custom».
3. `AppConfig` — `model_validator(after)`: модель каждой роли и `alternatives.narrator` есть в `prices` и `context_windows`,
   иначе ValueError (+ тест на пользовательский TOML).
4. `ModelPrice` — `strict=True` (float отвергается) (+ тест).
5. `LimitsConfig.gold_explicit_max_cp_by_level` — ключи ровно 1..5 (комментарий: MAX_LEVEL этапа 1) (+ тест).
6. `load_rules_config` — комментарий «внутренний загрузчик для devtools; игра использует `load_settings`».
7. Сторож архитектуры: пакеты движка (включая config) не импортируют `anthropic`, `google.genai`, `google`.
8. `app_defaults.toml` — комментарий: цены кэша Haiku выведены из правила ~0.1×/~1.25× входа (сверить с прайсом).
Исполнители: K — пункты 1–8 в `src/**` и `docs/**`; T — тесты к 1, 3, 4, 5, 7.
