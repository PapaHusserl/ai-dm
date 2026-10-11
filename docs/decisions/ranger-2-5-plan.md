# План: следопыт 2–5 ур., Охотник и Повелитель зверей, Грей 3 ур. (кусок трека 1.5)

Основание: решение проектировщика «Грей: уровень 3, Повелитель зверей» (конец `stage3-audit.md`), ТЗ разд. 6, трек 1.5.
Сверка: SRD_CC_v5.2.1.pdf (CC-BY-4.0), с. 57–61 (Ranger, Ranger Spell List, Hunter), с. 87–88 (Fighting Style feats),
раздел Spells. Тексты в YAML пишем своими словами, числа — по SRD.

**Задача:** довести следопыта до 5 ур. по SRD 5.2.1 (умения, заклинания 1–2 круга, Охотник, Повелитель зверей своей
редакции), сделать повышение уровня с выборами и собрать Грея 3 ур. в паке Дракона через конвертер.

## 1. Что есть сейчас (по коду)

- `srd/data/classes/ranger.yaml`: только `spellcasting` и `weapon_mastery` на 1 ур.; нет Favored Enemy (Метки охотника).
  `spellcasting.prepared: 2` — одно число, роста по уровням нет.
- `srd/data/tables/spell_slots_half.yaml` — сверено с SRD: 1:2, 2:2, 3:3, 4:3, 5:4+2. Правок нет.
- `rules/progression.level_up` — только HP + `sync_resources` (ячейки растут правильно). Выборов уровня (стиль, экспертиза,
  подкласс, ASI/черта, новые заклинания) нет ни в движке, ни в `game/app.py::choose_level_up` (там только average/roll).
  Итог: следопыт поднимается до 5 «по числам», но без умений и выборов.
- `campaign/build.build_hero` поднимает пресет до `preset.level` тем же `level_up` — выборов тоже нет.
- `CharacterSheet` (`state/hero.py`): есть `subclass_id`, `feats`, `spells_known/prepared`; нет экспертизы и выбора опций умений.
  `derived.hero_effects` уже читает умения подкласса до текущего уровня — формат подкласса (`Subclass`) готов, данных нет.
- `rules/builder.py`: боевой стиль только если у класса `fighting_style` на 1 ур. (`r.level <= 1`); подготовленные — только 1 круга,
  лимит `spellcasting.prepared`.
- Бой (`combat/actions/cast.py`): виды заклинаний attack/darts/area/heal/buff; неизвестный вид в бою не показывается.
  Каст всегда тратит действие. Атака героя — одна за действие (мультиатака только у монстров).
- Мастер (`master/prompt.py::state_data`) видит у героя HP, состояния, инвентарь, уровень, опыт, мотив; класса, умений,
  заклинаний и ячеек не видит. Операции протокола (`protocol/apply.py`) сотворения заклинаний вне боя не имеют.
- Заклинания в `srd/data/spells`: bless, burning_hands, cure_wounds (уже `classes: [cleric, ranger]`), fire_bolt, magic_missile.
- Черты: alert, defense (стиль), magic_initiate, savage_attacker, skilled. Нет Archery/GWF/TWF и Ability Score Improvement.
- Экспертизы нет нигде (у плута SRD она с 1 ур. — тоже не сделана).
- Грей (`campaigns/drunk_dragon/heroes/grey.yaml`, генерится `devtools/import_dragon.py::hero_preset`): 1 ур., xp 0, заклинаний нет.
  `dragon_drafts.yaml` принимает только kind npc|faction|god.
- Схема сейва v3 со снимком `tests/schema/save_v3.schema.json`: новые поля в `CharacterSheet`/`Hero` = v4 + миграция.

## 2. Умения: механика или текст

| Ур. | Умение (SRD) | Как | Где |
|---|---|---|---|
| 1 | Favored Enemy: Метка охотника всегда подготовлена, бесплатно 2/3 раза (1–4 / 5 ур.), восстановление — продолжительный отдых | механика: пул `favored_enemy` (`max_by_level`), заклинание всегда подготовлено | feature `favored_enemy` |
| 2 | Deft Explorer: экспертиза в 1 навыке; 2 языка | экспертиза — механика (двойной БМ); языки — текст (поле `languages`, движок не проверяет) | feature `deft_explorer` |
| 2 | Fighting Style: черта стиля или Druidic Warrior (2 заговора друида) | черта стиля — механика; Druidic Warrior — **не делаем** (нет заговоров друида; в BACKLOG) | feature `fighting_style` на 2 ур. |
| 3 | Подкласс | выбор `subclass_id` | — |
| 4 | Ability Score Improvement (+2 / +1+1, предел 20) или черта | механика | feat `ability_score_improvement` (repeatable) |
| 5 | Extra Attack: две атаки за действие Атака | механика в бою | feature `extra_attack` |
| — | Prepared Spells: 2/3/4/5/6 на 1–5 ур.; смена одного после продолжительного отдыха | механика: лимит по уровню; смена на отдыхе — **не сейчас** (BACKLOG, этап 6) | `Spellcasting.prepared_by_level` |

Охотник (SRD, source: srd-5.2):
| 3 | Hunter's Lore: под Меткой знаешь иммунитеты/сопротивления/уязвимости | механика-лайт: при наложении Метки в бою строка лога со списком | `hunters_lore` |
| 3 | Hunter's Prey: Colossus Slayer (+1d8 раз в ход по раненой цели) или Horde Breaker (доп. атака по соседу); смена на отдыхе | Colossus Slayer — механика; Horde Breaker — текст для мастера (BACKLOG); смена на отдыхе — не сейчас | `hunters_prey` + опции `colossus_slayer`, `horde_breaker` |

Повелитель зверей (source: custom, своя редакция, без текста и чисел PHB; только 3 ур., следующие — 7+, вне 1–5):
| 3 | «Зверь-спутник» (`beast_companion`): зверь Среднего размера или меньше, связан с героем; вне боя разведывает, идёт по следу, сторожит стоянку, понимает простые команды; в бою не участвует до этапа 7. Погиб — новый после 8 ч обряда в дикой местности (число своё) | текст для мастера + состояние спутника (имя, вид, заметка) в `state_data` | `beast_companion` |
| 3 | «Чутьё стаи» (`pack_sense`): герой понимает настроение зверя и знает направление к нему в пределах ~1 мили | текст | `pack_sense` |

## 3. Заклинания (1–2 круг)

Метка охотника — обязательна. Остальное — набор под 1–5 ур. (6 подготовленных на 5 ур. + Метка), ТЗ: 10–12 на класс.
| id | Круг | В бою (механика) | Вне боя |
|---|---|---|---|
| `hunters_mark` | 1 | да: новый вид `mark` — бонусное действие, концентрация, на цели эффект «+1d6 силовым при попадании атакой от наложившего» (крит удваивает кость); первыми тратятся бесплатные использования `favored_enemy`, потом ячейка. Перенос метки после 0 HP — текст (BACKLOG) | преимущество Восприятие/Выживание для поиска цели — текст |
| `cure_wounds` | 1 | есть (heal) | — |
| `ensnaring_strike` | 1 | нет (срабатывает после попадания — нужен хук; BACKLOG) | текст |
| `entangle` | 1 | нет (area без урона; BACKLOG) | текст |
| `fog_cloud` | 1 | нет | текст |
| `goodberry` | 1 | нет | текст (10 ягод — можно как предмет позже) |
| `speak_with_animals` | 1 | нет | текст, ритуал |
| `longstrider` | 1 | нет | текст |
| `alarm` | 1 | нет | текст, ритуал |
| `pass_without_trace` | 2 | нет | текст (+10 Скрытность — мастер учитывает при проверке) |
| `spike_growth` | 2 | нет | текст |
| `lesser_restoration` | 2 | нет | текст (снятие состояния — через существующие операции мастера, если есть) |
| `barkskin` | 2 | нет («КД не ниже 17» — новый вид модификатора; BACKLOG) | текст |

Модель `Spell` годится как есть; нужен только `casting_time: bonus_action` в каст-логике и вид `mark`. Ритуал: поле
`ritual: bool = False` — опционально (только для текста мастеру), по умолчанию не вводим.

## 4. Модели (минимально)

1. `content/models/classes.py::Spellcasting` — `prepared_by_level: dict[int, int] | None = None` (ranger: 1:2 … 5:6).
   `prepared` остаётся лимитом при создании. Пригодится жрецу/волшебнику.
2. `content/models/common.py::EffectSpec` — `max_by_level: dict[int, int] | None` (пул по уровню героя; `favored_enemy`
   2/2/2/2/3; заодно `second_wind` воина 2/2/2/3/3 — отдельная правка, не в этой партии). `EffectWhen` += `ranged_weapon`
   (Archery), `target_wounded` (Colossus Slayer). `EffectSpec.type` += ничего: Метка — `extra_damage` на заклинании.
3. `state/hero.py::CharacterSheet` — `skill_expertise: list[str] = []`, `languages: list[str] = []`,
   `feature_options: dict[str, str] = {}` (`{"hunters_prey": "colossus_slayer"}`).
   `Hero` — `companion: Companion | None = None` (`name`, `kind`, `notes`) — модель в `state/hero.py`.
4. `campaign/models.py::HeroPreset` — `level_choices: list[LevelChoices] = []`, `companion: Companion | None = None`.
5. `rules/progression.py` — `LevelChoices` (pydantic, extra=forbid): `level`, `fighting_style`, `expertise`,
   `subclass_id`, `feature_options`, `asi: dict[str,int] | None`, `feat`, `spells_add: list[str]`, `languages`.
6. Сейв: схема v4, `persistence/migrations/m0004_v3_to_v4.py` (setdefault новых полей), `tests/schema/save_v4.schema.json`.

## 5. План реализации

1. Данные SRD — `srd/data/classes/ranger.yaml`: `features` на 1 (favored_enemy), 2 (deft_explorer, fighting_style), 3 (subclass —
   маркер не нужен, выбор через LevelChoices), 4 (ability_score_improvement — feature-маркер), 5 (extra_attack);
   `spellcasting.prepared_by_level`. Файлы `srd/data/features/{favored_enemy,deft_explorer,extra_attack,ability_score_improvement,
   hunters_lore,hunters_prey,colossus_slayer,horde_breaker}.yaml` (srd-5.2, CC-BY-4.0).
2. Подклассы — новый каталог `srd/data/subclasses/`: `hunter.yaml` (srd-5.2), `beast_master.yaml` (source: custom, license пусто
   или MIT как у кода; в описании пометка «своя редакция»), features `beast_companion`, `pack_sense` (custom). Проверить, что
   `content/loader.py` грузит kind `subclass` из каталога (модель есть; если каталога нет в маппинге — добавить по образцу feats).
3. Черты — `srd/data/feats/{archery,ability_score_improvement}.yaml` (+ `great_weapon_fighting`, `two_weapon_fighting` только
   описанием, без эффектов — чтобы список стилей SRD был полным; эффекты BACKLOG). Archery: `modifier attack_roll +2 when ranged_weapon`.
4. Заклинания — 13 файлов из таблицы разд. 3 в `srd/data/spells/` (ru-названия по глоссарию dnd.su: Метка охотника, Опутывающий
   удар, Опутывание, Туманное облако, Чудо-ягоды, Разговор с животными, Скороход, Тревога, Бесследное передвижение, Шипастая поросль,
   Малое восстановление, Дубовая кора). `classes` по SRD (в т.ч. druid и др. — для будущего).
5. Модели — разд. 4 п. 1–4.
6. Производные — `rules/derived.py`: `skill_bonus` удваивает БМ при `skill_expertise`; `resource_maxes` учитывает `max_by_level`;
   `hero_effects` добавляет умение из `feature_options` (опция выбрана → её эффекты); новая `prepared_limit(hero, registry)`;
   `always_prepared(hero, registry)` → `["hunters_mark"]` по умению `favored_enemy` (через `spell_access`-эффект, тип уже есть).
7. Повышение уровня — `rules/progression.py`: `required_choices(hero, registry, level) -> set[str]` (что надо выбрать на уровне по
   умениям класса/подкласса), `apply_level_choices(hero, registry, choices) -> ValidationErrors | None` (валидация по образцу
   `builder.py`: стиль — `feat.category == fighting_style`; экспертиза — навык из владений, не повтор; подкласс — `class_id`
   совпадает; ASI — ≤20, сумма 2; заклинания — из списка класса, круг ≤ максимального по ячейкам, итог ≤ `prepared_limit`).
   `level_up` не меняем по сигнатуре; выборы — отдельным шагом после него.
   `builder.py`: проверка стиля `r.level <= 1` оставить (это создание на 1 ур.) — стиль следопыта идёт через LevelChoices.
8. Пак — `campaign/build.build_hero`: после каждого `level_up` применить `preset.level_choices` для этого уровня; отказ старта
   (`StartRefused`) при ошибке или отсутствии обязательного выбора. Перенос `preset.companion` в `hero.companion`.
9. Игра — `game/app.py::choose_level_up`: после HP — шаги выбора по `required_choices` (меню вариантов, как сейчас
   average/roll). Объём — см. вопрос В5.
10. Бой — `combat/actions/cast.py`: `spell_kind` → `mark`, если у заклинания `extra_damage`; `cast_mark` вешает `ActiveEffect(kind="mark",
    source=ref, params={dice, damage_type}, expires=concentration)`; `perform` — бонусное действие при `casting_time == bonus_action`
    (`turn.bonus`), трата `favored_enemy` вместо ячейки, если есть; `castable_spells` — плюс всегда подготовленные; `available.cast_options`
    — бонусные касты при занятом действии. Hunter's Lore — строка лога при наложении.
    `combat/actions/attack.py::attack`: при попадании — урон Метки, если на цели `mark` от `ref`; Colossus Slayer — раз в ход
    (флаг в `TurnState`, напр. `colossus_used`). Extra Attack: `TurnState.attacks_left`; первое `attack.perform` ставит 1 при
    умении `extra_attack`, вторая атака доступна без действия (`available.attack_options`), как мультиатака по образцу `multiattack.py`.
11. Мастер — `master/prompt.py::state_data` → `hero_data` += `class`, `subclass`, `features` (id+имя+описание, только текстовые и выбранные),
    `spells_prepared`, `spell_slots` (current/max), `favored_enemy`, `companion`. Правило рассказчика: умения без механики — нарратив,
    спутник не дерётся до этапа 7.
12. Конвертер — `devtools/dragon_drafts.yaml`: записи `kind: hero, id: grey` с полями `level` (3), `xp` (900), `level_choices`,
    `companion` (why/source как у прочих). `devtools/import_dragon.py`: `hero_preset` берёт черновики hero; `docs/decisions/stage3-p7-drafts.md`
    перегенерируется. Перегенерировать `campaigns/drunk_dragon/heroes/grey.yaml`, правки руками не вносить.
13. Документы — `docs/rules-adaptation.md` (Метка в зонах, Horde Breaker текстом, Druidic Warrior нет, смена подготовленных/опций на
    отдыхе позже), `docs/BACKLOG.md` (пункты «BACKLOG» из этого плана), `docs/glossary.md` (новые термины).

## 6. Тесты (TDD, кабану-доебе)

Контент: `tests/unit/content/`
- все новые YAML загружаются без ошибок; `subclass hunter/beast_master` с `class_id: ranger`; у custom — `source: custom`.
- у каждого заклинания следопыта `ranger in classes`; `hunters_mark`: круг 1, бонусное действие, концентрация, 90 фт.
Производные/прогрессия: `tests/unit/rules/`
- следопыт 1→5 (average): HP по d10 (6+ТЕЛ за уровень), ячейки 2/2/3/3/(4,2), `favored_enemy` 2/2/2/2/3, `prepared_limit` 2/3/4/5/6.
- `required_choices`: 2 ур. → {fighting_style, expertise}; 3 → {subclass} (+ hunters_prey при hunter); 4 → {asi_or_feat}; 5 → пусто.
- экспертиза: Выживание при БМ +2 и МДР +2 → +6; повтор/навык без владения → ошибка.
- стиль Archery: +2 к атаке луком, 0 к мечу; стиль не из категории → ошибка.
- ASI: +2 к ЛОВ 17 → 19; 19 + 2 → ошибка (предел 20); +1/+1 валидно.
- заклинания: на 3 ур. `pass_without_trace` (2 круг) → ошибка; на 5 ур. — можно; сверх лимита → ошибка; `hunters_mark` не считается в лимит.
- `sync_resources` на 5 ур. заводит `spell_slot:2` и растит `favored_enemy` до 3 (текущее +1).
Бой (детерминированно по сиду): `tests/unit/combat/`
- Метка: бонусное действие, действие остаётся; тратится `favored_enemy`, ячейка — нет; при 0 бесплатных — ячейка 1 круга.
- попадание по цели с Меткой → +1d6 force в логе; по другой цели — нет; крит → 2d6; потеря концентрации (урон, проваленный спас) снимает метку.
- Hunter's Lore: в логе сопротивления цели. Colossus Slayer: раненая цель +1d8 один раз за ход; цель с полными HP — нет.
- Extra Attack: следопыт 5 ур. делает 2 атаки за действие; 4 ур. — одну. Следопыт без подкласса/1 ур. — поведение как раньше (регрессия).
- `ensnaring_strike` и прочие без вида не появляются в вариантах боя.
Пак/сейв: `tests/unit/campaign/`, `tests/unit/persistence/`
- пресет Грея собирается: 3 ур., xp 900, `subclass_id: beast_master`, стиль, экспертиза, 4 подготовленных + Метка, спутник.
- пресет с `level: 3` без выбора подкласса → `StartRefused` с понятным текстом.
- миграция v3→v4: старый сейв грузится, новые поля пустые; снимок схемы v4.
Мастер: `tests/unit/master/` — `state_data.hero` содержит класс, подкласс, заклинания, ячейки, спутника; без спутника — ключа нет/None.
Игра: `tests/unit/game/` — повышение 1→2 в приложении предлагает стиль и экспертизу, после выбора `pending` снимается (если В5 = да).

## 7. Риски

- Схема сейва v4 + миграция — обязательно, иначе снимок `save_v3` упадёт.
- Бонусное действие: правило 2024 «при касте бонусным в тот же ход — только заговор действием» в движке не проверяется — героям-полузаклинателям
  неважно (заговоров нет), но пометить в `rules-adaptation.md`.
- Метка в зонах: «в пределах 90 фт» — через `range_band_ft`, как у прочих заклинаний.
- `max_by_level` и `prepared_by_level` — ключи int из YAML (как в `cantrip_scaling`), проверить парсинг.
- Тексты custom-подкласса — без пересказа PHB (Primal Companion, Beast of Land/Sea/Sky, возрождение за ячейку — не брать).
- Бюджет контекста мастера: `features` в `state_data` — только короткие описания.
- Extra Attack затрагивает общий путь атаки героя — регрессия воина/плута.

## 8. Продуктовые вопросы (рекомендации из истории `saves/drunk_dragon/`)

В1. Зверь Грея. В истории спутника нет ни разу (ни в главе I, ни в II) — его надо ввести. Варианты: (а) волк/горный пёс — след, нюх ночью,
    в этапе 7 — понятный боец; (б) ястреб/сокол — связь с почтовыми соколами Ложи Северного Ветра, разведка сверху, но ночью и в штольнях бесполезен;
    сова не годится — это знамение Селунэ. **Рекомендация: (а) волк** (Грей — одиночка-егерь, «как зверь чует ветер»; отряд идёт ночью к шахте).
    Как объяснить, что раньше его не было: «был с Греем всегда, просто молчаливо» (ретро-правка памяти) или «прибился/доверен Йоргеном-звероловом перед
    походом» — **рекомендация: от Йоргена**, без правки прошлых сцен; имя — на выбор проектировщика.
В2. Боевой стиль. В истории — лук, тяжёлый арбалет «Загонщик», выстрелы решают бои (стрела срывает ритуал, сжигает Ольбрехта). **Рекомендация: Стрельба (Archery).**
    Альтернатива без новой механики — Защита (уже есть).
В3. Экспертиза. Навыки Грея: Восприятие, Проницательность, Природа, Скрытность, Выживание, Запугивание. В истории: «Выслеживание», скрытные заходы.
    **Рекомендация: Выживание** (след); альтернатива — Скрытность.
В4. Заклинания Грея на 3 ур. (4 подготовленных 1 круга + Метка всегда). В истории магией он не пользовался, есть «первая помощь».
    **Рекомендация:** Лечение ран, Опутывающий удар, Разговор с животными (под Повелителя зверей), Туманное облако. Языки (2): **Великаний и Гномий**
    (Железный Кряж, Кузница Пепла гномов) — либо оставить пустыми.
В5. Выборы при повышении уровня в живой игре (шаг 9): делать сейчас или только пресеты? Грею до 4 ур. нужно 2700 опыта — в этой главе маловероятно.
    **Рекомендация: сейчас — движок + пресеты + минимальное меню в `app.py`**; если меню тяжело — отдельной мини-партией до этапа 6.
В6. (Архитектура, по правилу 4 — решает проектировщик.) Заклинания вне боя: в протоколе нет операции «сотворить» — ячейки и Метка вне боя
    не тратятся, мастер может «колдовать» бесплатно. Варианты: (а) новая операция протокола `cast_spell {spell_id}` — движок проверяет подготовку и
    ячейку, тратит, концентрацию отмечает, эффект описывает мастер; (б) не трогать протокол, полагаться на нарратив. **Рекомендация: (а)**, но
    можно отдельной партией после этой — без неё Грей играется.
В7. Extra Attack (5 ур.): Грею не нужен сейчас. Делать в этой партии (полнота трека 1.5) или отложить? **Рекомендация: в этой партии последним шагом.**

## Решения проектировщика (2026-10-04: «1. волк, Акела 2. всё верно 3. ок 4. ок 5. делать сейчас 6. ок 7. ок»)
1. Зверь Грея — волк Акела (вводится через Йоргена-зверолова, прошлые сцены не переписываются).
2. Боевой стиль — «Стрельба». 3. Экспертиза — Выживание.
4. Заклинания Грея на 3 ур.: Лечение ран, Опутывающий удар, Разговор с животными, Туманное облако; Метка охотника — всегда.
5. Меню выборов при повышении уровня в живой игре — в этой партии.
6. `cast_spell` вне боя — отдельной партией после этой.
7. Вторая атака 5 ур. — в этой партии последним шагом.
