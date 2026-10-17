# 51. К7х Слой content импортирует rules: список типов урона
status: done
priority: low
updated: 2026-10-14

✅ (из ревью К7к, 2026-10-14)
`DAMAGE_TYPE_WORDS` переехал в `content/models/common.py`; `roll_pipeline` и `loader` импортируют оттуда.

Было:
`content/loader.py:check_monster_gear` берёт `DAMAGE_TYPE_WORDS` из `rules/roll_pipeline.py` — content тянет rules. Развязка: держать список типов урона в content (или данными SRD), rules — импортирует оттуда.

## Закрыто

Шаг К7х, 2026-10-14. План: docs/plan-k7x.md
