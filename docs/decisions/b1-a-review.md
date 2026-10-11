# Ревью Б1а

## Решения проектировщика
1. vulture_allowlist до Б1б: временно внесены имена без потребителей в Б1а (группа «Б1а → снять в Б1б»); поля AbilityScores con/int_/wis/cha — постоянно (поля схемы).
2. `build_world` для листа героя: до `collect_conflicts` проверка `name_taken(hero.name, taken_names(pack))`, занято → `StartRefused`.
3. `HERO_HANDLERS` и `HERO_MODELS` разложены по режимам; `apply` берёт обработчики по `ctx.mode` (чужой инструмент → `not_available_in_mode`).
4. Ручная правка `opportunity` заменяет весь список (принято до Б1б); в подсказке поля это сказано; правка по id — BACKLOG (Б1б).
5. Пределы — только в `limits` справочника (`means_item_max`, `opportunity_then_max` и др.); числа из `hero_sheet_rules.md` убраны, правила ссылаются на ключи `limits`.
Прочее: `KnownIds.from_world` удалён; `AbilityScores.str` → `str_` (alias `str`); SRD-предыстория (строка) в `sheet_fields_lines`/`background_field` даёт «—» без TypeError.
