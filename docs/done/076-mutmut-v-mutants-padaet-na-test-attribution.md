# 76. mutmut в `mutants/` падает на test_attribution (нет README/Makefile/docs)
status: done
priority: medium
updated: 2026-10-17

(ТС, 19ф — docs/plan-ts.md, docs/plan-19f.md)
`make mutate` в каталоге `mutants/` падает на тестах, читающих README/Makefile/docs — критерий mutmut закрывается ручной
проверкой doeba. Починить: `also_copy` в конфиге mutmut или копия файлов в Makefile. Шаг 0 партии ТБ (R7 #1).

## Закрыто

Шаг ТБ «Бюджет контекста», 2026-10-17. План: docs/plan-tb.md
