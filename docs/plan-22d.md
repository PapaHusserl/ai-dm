# 22д: docs/ по правилам дашборда (BACKLOG 68)

План — papa-kaban, 2026-10-17. Статус: на аппруве владельца.

## Суть
Перевести docs/ на правила дашборда (`~/projects/dashboard/docs/RULES.md` v3) и убрать мусор из репо. Только документы,
код не меняется; src/ и tests/ ссылаются на docs/ только в комментариях.

## Шаги
1. **Бэкап (оркестратор):** `git tag docs-legacy-22d 717e7bf` + архив неотслеживаемого
   `~/.config/ai-dm/backups/docs-legacy-22d-<дата>.tgz` (docs/, campaigns/test/, .dashboard.json).
   Откат: `git checkout docs-legacy-22d -- docs/`, удалить новые файлы (done/, plan-*.md, RULES.md, AGENTS.md, CLAUDE.md), распаковать архив.
2. **Чек-листы.** Пройдены — удалить: b1, b2, b3, mu, k0, p37. Не пройдены — в `~/.config/ai-dm/checklists/`: zhp1, 19f, tm, to, ts.
   Спорные (В4): k0-fix и поглощённые ЖП1 r1-f1-r2, k1, k7k, k7x, k7d, b59, t60, tv. Новые чек-листы — туда же, итог прогона — в «Итог» документа шага.
3. **Планы → документы шага:** `git mv docs/<ШАГ>-PLAN.md docs/plan-<шаг>.md` (38 файлов, строчные; ROADMAP-PLAN.md →
   docs/decisions/roadmap-plan-r2-r4.md; decisions/ranger-2-5-plan.md → plan-ranger-2-5.md; decisions/stage2-plan.md сверить с plan-stage2).
   Миграция: шапка `# <Шаг>: название (BACKLOG N)`, разделы «Суть», «Решения», «Правки по ревью» (ссылка на review), «Итог»
   (закрытые пункты, коммит, тесты/cov/smells, стоимость — перенос абзацев из HANDOFF.md). Ссылки — замена во всех docs/, README, tests/ (комментарии),
   src/ai_dm/combat/actions/cast.py, .dashboard.json; проверочный скрипт — нет битых `docs/*.md`.
4. **BACKLOG:** заголовки `## N. Название` + `status:/priority:/updated:`; закрытые (3, 4, 5, 6, 7, 12, 13, 14, 17, 18, 23, 35, 37, 38, 39,
   43, 44, 51, 52, 60, 61, 64) и снятый 53 — карточки `docs/done/NNN-<translit>.md` (тело без правок + `## Закрыто` со ссылкой на план);
   шапка — 3 строки, следующий номер 72; «Приоритеты» (история) удалить.
5. **HANDOFF.md → handoff.md** (git mv в два шага, регистронезависимая ФС), ≤ 80 строк по RULES; история — в «Итог» планов;
   роли, правила, качество, экономия — в AGENTS.md. **ROADMAP** — дерево `## Блок` со строками
   `- К1 Заклинания и дальность ✅ (BACKLOG 13, 14, 18) — M, v9, факт 0,84 — docs/plan-k1.md`; ранжирование R6 без изменений.
6. **Гигиена:** .gitignore += `/.dashboard.json`, `campaigns/test/`; `docs/import-examples/` закоммитить без invalid-too-long.txt
   (в README — команда, как его создать); AGENTS.md + CLAUDE.md (`@AGENTS.md`); RULES.md — побайтная копия эталона
   (`mix dashboard.scaffold --rules ai-dm`); .dashboard.json — ссылки на новые пути; README пути; удалить decisions/ts-mutants.txt.
7. **Порядок:** П1 бэкап → П2 чек-листы, .gitignore, import-examples → П3 планы и ссылки → П4 BACKLOG и done/ →
   П5 handoff/ROADMAP/AGENTS/CLAUDE/RULES → ревью mama-kaban → `make check` → один коммит.

## Проверка
Скрипт ссылок — 0 битых; нет `*-PLAN.md`, `checklist-*`, `HANDOFF.md` в docs/; `status:` у каждого пункта BACKLOG, 23 карточки в done/;
handoff ≤ 80 строк; RULES.md совпадает с эталоном; `git status` чист; `make check` зелёный; дашборд открывает ai-dm без предупреждений.

## Оценка
≈ 0,4–0,45 млн (в ROADMAP было 0,2); при слиянии decisions/ в планы (В1б) +1–1,5 млн.

## Риски
kaban без Edit — массовая замена скриптом и git mv; «Итог» 38 планов из HANDOFF — самая трудоёмкая часть, стоимости не терять;
теги stage-* из HANDOFF в репо не существуют (есть только k0) — отметить в handoff.

## Вопросы владельцу (рекомендация — (а))
1. docs/decisions/ (162 файла): (а) архив только для чтения, новые ревью — в документ шага; (б) слить по шагам в plan-*.md и удалить.
2. Пункт «5а»: (а) перенумеровать в 72 «(бывш. 5а)»; (б) оставить (дашборд не увидит).
3. Пункт 9: (а) planned с хвостом (`ends_when` → Ж2); (б) карточка done, хвост — в 10.
4. Спорные чек-листы: (а) удалить k0-fix и 8 поглощённых ЖП1; (б) вынести вместе с zhp1.
5. Место непройденных чек-листов: (а) `~/.config/ai-dm/checklists/`; (б) gitignored `live/` в корне.
6. (а) campaigns/test/ в .gitignore, import-examples закоммитить; (б) обе в .gitignore.
7. ROADMAP: (а) переформатирует kaban по спецификации; (б) пишет papa-kaban отдельно.

## Решения владельца (2026-10-17)
В1 — **(б)**: docs/decisions/ слить по шагам в plan-*.md и удалить (оценка +1–1,5 млн; ссылки в комментариях тестов — править).
В7 — **(б)**: ROADMAP пишет papa-kaban отдельным вызовом. В2–В6 — (а).

## Доработка под В1б (papa-kaban, 2026-10-17)
- **Способ:** слияние — механическая конкатенация скриптом (CSV `источник;цель;тип`, сдвиг заголовков на уровень,
  раздел `## <Тип>: <заголовок> (бывш. docs/decisions/<имя>.md)`, текст без правок, `git rm` источника), не пересказ моделью.
- **Тип по имени:** grooming/plan/spec → «Решения»; review/notes/batch*/audit-1 → «Правки по ревью»;
  live/findings/audit/cost/acceptance/flight-review → «Итог»; drafts/tracks/sim-* → «Приложение».
- **Сопоставление:** по этапам и партиям в одноимённые plan-*.md; новые: plan-stage1, plan-17a (аудит К7д+B59+Т60 и разбор полётов),
  plan-zhp1, plan-techdebt (tech-debt-2026-10-14), plan-roadmap-r2…r6 (история роадмапа); ranger-2-5-plan → plan-ranger-2-5;
  decisions/README.md и ts-mutants.txt удалить. Нераспределённые — 5 ресёрчей (В8).
- **Сокращать нельзя:** решения проектировщика, цифры расходов, находки прогонов, вердикты мутантов, сетки sim.
  Сырые выгрузки > 50 строк не трогать — kaban выписывает их в «Итог» 22д, уборка отдельным решением.
- **Порции kaban:** П3а этапы 1–6 + ranger (61 файл); П3б Б/Му/Д1/К/П37/Р/Ф/custom/trade/combat (66); П3в техдолг, 17а, zhp1,
  roadmap, research, «Суть» новых планов (35); П3г — замена ссылок + скрипт полноты.
- **Полнота (скрипт):** все заголовки источников найдены в цели; число слов цели = старое + источники (±1 %); все строки-решения
  (В/Q/Р/P-N) на месте; docs/decisions пуст. Ревью mama-kaban — журнал скрипта + выборка 5 документов.
- **Ссылки:** 20 тестов и 3 файла devtools (комментарии), 208 вхождений в docs/, README.md:211 (индекс decisions убрать),
  NOTES.md. Агенты kaban-svekrov.md:31, mama-kaban.md:46 (путь отчёта) — не трогаем, позже через skill-intake;
  до тех пор путь отчёта оркестратор задаёт в задании. Память live-run-checklist — итог прогона в «Итог» документа шага.
- **ROADMAP (В7б):** papa-kaban пишет полный текст после П4 и до П5; оркестратор записывает.
- **Оценка:** ≈ 0,75–0,8 млн.
- **В8 (ресёрчи: local-llm, music, openai, gemini-503, presets-adult-models):** (а) новый docs/research/; (б) три LLM-ных в docs/llm-notes/, два в docs/research/. **Решение владельца: (а).**

## Итог
- Закрыт BACKLOG 68 (и 59 — карточкой, решение владельца). docs/decisions (162 файла) слит скриптом в plan-*.md
  (полнота check.py: заголовки, слова, строки-решения); ресёрчи → docs/research/; 38 `*-PLAN.md` → plan-*.md;
  новые plan-stage1, plan-17a, plan-zhp1, plan-techdebt, plan-roadmap-r2…r6. История HANDOFF дословно — в «Итог» 43 планов.
- BACKLOG: status/priority/updated, 5а → 72, следующий 73; docs/done/ — 24 карточки (даты updated у старых — ориентировочные,
  git-история до 2026-10-11 утрачена). ROADMAP — дерево блоков (писал papa-kaban). handoff.md, AGENTS.md, CLAUDE.md,
  docs/RULES.md (scaffold), NOTES.md в корне. Чек-листы: 15 удалены, 5 → ~/.config/ai-dm/checklists/.
- Ревью mama-kaban: блокер — пропал список мутантов ТС, возвращён приложением в plan-ts.md. Аудит kaban-svekrov:
  решения за владельца (4 перенаправленные ссылки, статусы BACKLOG, блоки ROADMAP, NOTES в корне) — подтверждены владельцем.
- Тесты: 17130 passed, 1 xfailed (18 мин); битых ссылок 0; в src/tests — только комментарии.
- Бэкап: тег docs-legacy-22d, архив ~/.config/ai-dm/backups/docs-legacy-22d-20261017-1327.tgz.
