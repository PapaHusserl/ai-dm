# 73. Rules-настройки не читаются из пользовательского config.toml
status: done
priority: low
updated: 2026-10-18

(ЖП1 п. 0.4, docs/plan-zhp1.md; R7 вопрос 5а)
`[disarm]` и прочие rules-секции пользовательский `~/.config/ai-dm/config.toml` не принимает (AppConfig `extra_forbidden`):
rules-настройки читаются только из `src/ai_dm/config/defaults.toml`. Чек-лист К7х и план К7х ошибочно предлагали config.toml.
Решение проектировщика (R7, 2026-10-17): только дока (README/ARCHITECTURE — где живут rules-настройки), пользовательский
слой не делаем. Хвост ТХ (R7 #2).

## Закрыто

ТХ, 2026-10-18. Дока: README (настройки) и ARCHITECTURE (C1, `config`) — rules-секции только в `defaults.toml`. План: docs/plan-tx.md
