# Шаг К2. Воин и плут 1–5 (BACKLOG 48, 57, 66 — закрыть; 11 «стили», 50 «плут», 31 «воин и плут» — части)

Строка ROADMAP:152. Код на a8d726f. Контур: вне msa; режим: встроить. План — папа-кабан, 2026-10-30; переписан под
решения 11–38 в тот же день; боеприпасы вынесены в шаг БП — docs/plan-bp.md (решение 34).

## Груминг (2026-10-30, scratchpad сессии — свинопас, аудит свекрови)

- Свинопас, факты по коду: воин в данных — только 1 ур. (`fighting_style`, `second_wind`, `weapon_mastery`); плут — только
  `weapon_mastery`; подклассов воина/плута нет (есть `hunter`, `beast_master`); оружия 10, мастерств 6 (нет cleave, push);
  стили Стрельба/Защита считаются, двуручный/две оружия — только описание; живые герои классов — все 1 ур. (Арн, Ваня —
  воины; Томас — плут); метания нет (только `improvised_thrown`); `AutoHeroController` Скрытой атаки не знает.
- Свекровь, к папе: объём К2 — из r4 #19 + TZ §6, не из тела BACKLOG 31 (принято: 31 остаётся открытым, К2 закрывает
  его часть «воин и плут»); `weapon_mastery_count` и заговоры по уровню из plan-k0:26 (ответ: 4-е мастерство воина на 4 ур.
  — в К2, решение 28; заговоры по уровню — явно в К3, у воина и плута заговоров нет); миграция сейва (ответ: не нужна —
  новых полей сейва нет, флаги хода идут через `ActiveEffect`, пулы — через `resources`; отпечаток v13 не меняется);
  «решить» — как вторая рука, Nick и другие бонусные действия делят меню боя (решено в «Суть», п. «Бонусные действия»).

## Решения

Влад, 2026-10-30 (окнами по грумингу; все — рекомендации свинопаса):
1. Оружие — весь SRD: простое и воинское, все 8 мастерств (в т. ч. «Рассечение», «Толчок»).
2. Брошенное оружие падает в зоне цели; в бою поднять действием; после боя подбирается само со строкой «Подобрал …».
3. «Удар второй рукой» появляется в меню только после Атаки лёгким оружием; до неё пункта нет.
4. Оружие и доспех: в листе героя — полно («Длинный меч — 1к8 руб. (двумя руками 1к10), универсальное, мастерство:
   Ослабление»; доспех — «КД 11 + Лов»), в меню боя — коротко.
5. Скрытая атака срабатывает сама, строка в логе («Скрытая атака +3к6»).
6. Хитрый удар — группа «Хитрый удар ▸» в меню боя (как «Стрелы ▸», шаг 111): выбрал — следующая Скрытая атака с эффектом.
7. BACKLOG 150 — не в К2: отдельный шаг после К-мульти, для всех классов, с настройкой мира.
8'. Импровизация «сбить с ног» не действует на цель на 2+ размера крупнее героя; строка «Слишком велик, чтобы сбить с ног»;
   укус волка не трогать.
9. Стили боя: доделать оба недостающих из 4 SRD («Бой двуручным оружием», «Бой двумя оружиями»).
10. Подклассы — только Чемпион и Вор; свои — пунктом беклога позже.

Влад, 2026-10-30 (окнами по плану, развилки Р1–Р19 первой редакции; кроме 11 — рекомендации папы):
11. Р1 — огнестрел из таблицы SRD 5.2.1 **завозить** (против рекомендации папы): мушкет, пистолет, боеприпас.
12. Р2 — универсальное оружие двумя руками само, когда левая рука свободна (нет щита и оружия): кость `versatile_dice`.
13. Р3 — Толчок (мастерство push): цель в соседнюю зону, выбирает движок (ниже по высоте, иначе первая соседняя).
14. Р4 — Рассечение: после попадания свободный пункт с выбором второй цели в зоне (как Истребитель орд).
15. Р5 — подпись «Удар второй рукой: <оружие> → <цель>», с Проворством — «Удар второй рукой (Проворство): …».
16. Р6 — подбор брошенного в бою как у выбитого: свободное взаимодействие раз в ход, иначе действие.
17. Р7 — после боя своё оружие героя — «<герой>: подобрал <оружие>», чужое — «достаётся», как сейчас.
18. Р8 — Тактический ум срабатывает сам при провале проверки навыка, заряд тратится только при успехе.
19. Р9 — Невероятное уклонение само при попадании по плуту с целой реакцией.
20. Р10 — «Отравить» в Хитром ударе требует набор отравителя (новый предмет, 50 зм); без него пункта нет.
21. Р11 — подписи новых пунктов меню — как перечислено в плане («Бросок: …», «Хитрое действие: Рывок / Отход / Спрятаться»,
    «Верный прицел», «Всплеск действий», «Хитрый удар ▸» → «Сбить с ног», «Отравить», «Отступить», «Рассечение: … → …»).
22. Р12 — пакет адаптаций к зонам принят целиком (см. «Адаптации» в «Суть»).
23. Р13 — стартовый набор воина А по SRD: цеп + 8 метательных копий вместо копья (новые герои).
24. Р14 — «Слишком велик, чтобы сбить с ног»: отказ до броска, действие цело, текст — подсказка рассказчику.
25. Р15 — Истребитель орд и Рассечение — в блок цели TUI, rank 0.
26. Р16 — живой Томас (плут 1 ур. без экспертизы) добирает 2 навыка при переходе на 2 ур.
27. Р17 — Второе дыхание: 3 заряда с 4 ур. (SRD).
28. Р18 — 4-е мастерство воина на 4 ур. — в К2 (пункт меню уровня); смена мастерств после долгого отдыха — беклог.
29. Р19 — кость в строках листа — «1d8» (как в `effect_texts` и логе боя), не «1к8».

Влад, 2026-10-30 (окнами по развилкам Р20–Р23 второй редакции):
30. Р20 — (б) огнестрел только через мир: признак `world_only`, не в лавках и не в списке мастерств при создании героя
    (рекомендация папы).
31. Р21 — (а) перезарядку (`loading`) не считать (против рекомендации папы): воин 5 ур. делает две атаки мушкетом за
    действие, как с луком; арбалеты — как сейчас. Перезарядка — пунктом беклога.
32. Р22 — ответ вне вариантов, дословно: «стрелы тоже должны тратится, как и пули». Боеприпасы расходуются — пули
    огнестрела, стрелы и, по смыслу, болты, пули пращи, иглы (всё с `ammunition`). Разбор и реализация — шаг БП,
    docs/plan-bp.md.
33. Р23 — (а) огнестрел — как любое дальнобойное: стиль «Стрельба», мастерства `slow`/`vex`; плут им не владеет.

Влад, 2026-10-30 (окнами по развилкам Р24–Р28 третьей редакции; все — рекомендации папы) — записаны как решения 2–6 шага
БП в docs/plan-bp.md «Решения»:
34. Р24 — (б) боеприпасы — отдельный шаг БП перед К2; К2 опирается на готовое (`Weapon.ammo`, `firearm_bullets`, сейв v14).
35. Р25 — (а) подбор после боя — половина всех видов, включая особые стрелы; закрывает BACKLOG 215.
36. Р26 — (а) лук без стрел — пункта нет.
37. Р27 — (а) «(осталось N)» в подписи пункта.
38. Р28 — (а) стрелы поштучно, сейвы ×20.

Влад, 2026-10-30 (окном по разбору П1, «Правки по ревью»; рекомендация папы):
39. Р29 — (а) дальность рядом со свойством: «боеприпас 80/320», «метательное 20/60» (как сделал кабан).
40. Р30 — (а) духовая трубка остаётся `1d1`; урон числом — BACKLOG 234.

Влад, 2026-10-30 (окнами по ревью мамы П1; рекомендации папы — «Правки по ревью», ответы на ревью мамы):
41. Р31 — (а) шаг экспертизы в мастере — после выбора черты вида; варианты — все навыки героя (правка кабану — по плану).
42. Р32 — (а) один `explorers_pack` у всех классов остаётся; наборы по SRD — BACKLOG 235.

Влад, 2026-10-30/31 (окнами по прогону mutmut П1; варианты — доеба):
43. Бесконечные `while` в тестах выбора уровня — предел числа шагов (вариант А доебы).
44. Таймаут mutmut ×2 (`timeout_multiplier = 2`, `timeout_constant = 1`) и `test_selection` по TESTS — только на время
    прогона в `pyproject.toml`, в коммит не идут.
45. mutmut П1 догнать до конца, промежуточные статусы не нужны; повтор после тестов доебы — целиком по 23 функциям.
46. Р33 (а) (2026-10-31): авто-герой метательное оружие не бросает, идёт к врагу; тактика — П3/BACKLOG 50.
47. Р34 (а): одна строка «Слишком велик, чтобы сбить с ног или оттолкнуть: цель больше героя минимум на два размера».
48. Р35 (а): лог Толчка — прежнее «<цель> отброшен в зону <id>».
49. Р36 (б): Рассечение по SRD — обнуляется только неотрицательный модификатор, отрицательный вычитается.
50. Р37 (а): «Тактический ум: +1d10 (N) = X → успех, заряд Второго дыхания потрачен» / «→ провал, заряд не тратится».
51. Р38 (а): мастерство Замедление — в П2, как морозная стрела (метка на цели, строка «<цель>: Замедление, скорость −10 фт»).
52. Р39 (а): дальность метательного — как есть, по SRD (20/60 в соседнюю зону — с помехой).
53. Р40 (б): Замедление — одна метка и одна строка на цель (`e.id == "slow"` без `source`); механика скорости — BACKLOG 237.
54. Р41 (а): строка «<герой>: Всплеск действий».
55. Р42 (а): «  Тактический сдвиг: ход не провоцирует атаки» / «  Выдающийся атлет: ход не провоцирует атаки».
56. Влад (2026-10-31 18:14): cov и mutmut П2 пропускаем, идём в П3; П2 не закоммичена, П3 — поверх неё в дереве;
    cov — полным прогоном в конце П3; мутанты П2 — «не подтверждены».
57. Р43 (б) (2026-10-31): Скрытая атака — только фехтовальное или дальнобойное оружие по SRD; бросок метательного
    копья/топора её не даёт.
58. Р44 (б): эффект Хитрого удара — после урона, как Опрокидывание; убитая цель или урон 0 — без эффекта.
59. Р45 (б): строка «  Хитрый удар (Сбить с ног): цель слишком велика, кость не потрачена».
60. Р46 (а), Влад 2026-10-31: после Рывка без перемещения Верного прицела нет (`turn.move == 1`), как сейчас; отступление от SRD.
61. Р47 (б), Влад 2026-10-31: «Отступить» срабатывает при уроне > 0, в том числе на добитой цели; при уроне 0 — нет.
62. Влад 2026-10-31 19:34: cov и mutmut П2+П3 пропущены («сразу приступаем к следующему шагу, пропускаем сейчас
    cov+mutmut»); мутанты П2–П3 не подтверждены, cov не снят.
63. Влад 2026-10-31 19:37: полный pytest перед закрытием шага пропущен — закрытие по тестам затронутых каталогов.

## Суть

**Задача:** воин и плут до 5 ур. по SRD 5.2.1 — умения, Чемпион и Вор, всё оружие SRD (включая мушкет и пистолет) и 8
мастерств, стили двуручного боя и двух оружий, удар второй рукой, метание, строки оружия/доспеха в листе, размер цели у
«Лежит», Скрытая атака у авто-героя и пересчёт сетки.

**Правило** (главные замены; первым пунктом аппрува):
- `attacks_of` (`combat/actions/attack.py:62`): было — на оружие одна `AttackInfo(weapon_id, weapon.kind, …, weapon.damage_dice)`
  → станет: при `"thrown" in weapon.properties` ещё одна `AttackInfo(f"{weapon_id}_thrown", "ranged", …, weapon_id=weapon_id,
  range_*=weapon.range_*)`; кость — `weapon.versatile_dice`, если оружие универсальное и левая рука свободна (решение 12).
- `attack` (`attack.py:517`): было `total += colossus_damage(…)` → станет `total += colossus_damage(…) + sneak.damage(…)`;
  перед `engine.damage(target_ref, total, …)` (`:523`) — `total = rogue.uncanny_dodge(engine, target_ref, total)`.
- `bonus_actions` (`combat/available.py:536`): было Второе дыхание → предметы → перенос Метки → Проворное бегство → станет
  Второе дыхание → Удар второй рукой → Хитрое действие (Рывок, Отход, Спрятаться) → Верный прицел → предметы → Метка →
  Проворное бегство; Всплеск действий — в `standard_actions`-ветке «действие потрачено» с `cost="free"`.
- `size_problem` (`combat/actions/improvise.py:42`): было `if effect == "push" and not shove.size_ok(…)` → станет
  `if effect in ("push", "prone") and not shove.size_ok(…)`.
- `required_choices` (`rules/progression.py:112`): было `if ref.feature == "deft_explorer": result.add("expertise")` → станет
  «экспертиза» по данным умения (сумма `count` эффектов экспертизы умений ≤ уровня минус `len(sheet.skill_expertise)` > 0)
  и новый ключ `weapon_mastery`, когда `weapon_mastery_by_level` на этом уровне растёт.
- `inv_lines` (`game/sheet_text.py:192`): было `elif kind != "armor": text = effect_texts(item.effects)` → станет
  `weapon → weapon_text(item)`, `armor → armor_text(item)`, прочее — как было.
- `settle_ground` (`combat/end.py:98–106`): было для всех `f"{name}: достаётся {owner}"` → для своего оружия героя —
  `f"{owner}: подобрал {name}"` (решение 17).
- `CATEGORY_BY_KIND` (`ui/combat_menu.py:21`): было `horde_breaker` без записи (только «Ещё…») → станет `horde_breaker`,
  `cleave`, `offhand_attack` → `target`, rank 0 (решение 25).
- `merchant_sells` (`rules/trade.py:22`): было `category is None or category not in preset.categories → False`, иначе любое
  оружие → станет ещё `if kind == "weapon" and model.world_only: return False` (решение 30).
- Правило боеприпасов — шага БП (docs/plan-bp.md «Суть»), здесь не повторяется; К2 его только использует.

**Поведение:** меняется — (1) меню боя воина/плута 2–5 ур.: новые пункты (список в «Бонусные действия»); (2) все герои:
«Бросок: <оружие> → цель» у метательного, кость универсального двумя руками, Толчок/Рассечение у оружия с этими
мастерствами, строки оружия/доспеха в `/inv` и листе, «Слишком велик…» у импровизации «сбить с ног», «Подобрал …» после боя,
Истребитель орд виден в блоке цели TUI; (3) создание плута: шаг «экспертиза» (2 навыка); лист героя у рассказчика — поле
`expertise`; (4) выбор мастерства при создании — список из 36 оружий вместо 10 (38 минус мушкет и пистолет — решение 30);
у каждого торговца с категорией `weapon` в ассортименте все 36 (`rules/trade.py:22` `merchant_sells` — любое оружие
реестра без `world_only`); мушкет и пистолет — только паком или выдачей рассказчика (`give_item`), владение и мастерство
по решению 33; (5) сетка `sim_combat` — новая базовая линия; (6) мушкет/пистолет/арбалеты/праща/трубка тратят боеприпас
и показывают «(осталось N)» — механика шага БП, К2 лишь задаёт `ammo` у нового оружия и предмет `firearm_bullets`.
**Вне ai-dm:** нет.
**Зависимость:** шаг БП (docs/plan-bp.md) закрыт до П1 — `Weapon.ammo`, `Item.category: ammo`, предметы `bolts`/`needles`/
`sling_bullets`/`firearm_bullets`, сейв v14.

**Бонусные действия в меню (ответ на «решить» свекрови):** плоский список `bonus_actions` в порядке выше; одно бонусное за
ход — уже `turn.bonus`. Удар второй рукой: `kind="offhand_attack"`, цель в `params` → в TUI блок цели, rank 0, сразу после
строк атак (как стрелы); с Проворством (`nick` у оружия второй руки, выбранного в `weapon_masteries`) тот же пункт с
`cost="free"` и подписью по решению 15 — бонусное действие не тратится, раз за ход. Хитрое действие ×3, Верный прицел,
Всплеск действий — блок «бесцелевых», rank 2 (как Второе дыхание). «Хитрый удар ▸» — группа в бесцелевом блоке (rank 2),
раскрытие как `ammo:`; выбор ставит флаг на ход. Истребитель орд и Рассечение — блок цели, rank 0 (решение 25).

**Адаптации к зонам (решение 22, в `rules-adaptation.md`):** Тактический сдвиг — после Второго дыхания ход не провоцирует
(`turn.disengaged`), движение не добавляется; Выдающийся атлет после крита — то же; «Отступить» — то же; Верный прицел —
только если не ходил в этом ходу, после него перемещения нет (и после Рывка); Скрытая атака «союзник в 5 фт» = боеспособный
союзник в зоне цели; Невероятное уклонение делит пополам урон оружия (кости + модификаторы + Убийца колоссов), доп. кости
стрел/эффектов — нет; досягаемость (`reach`) и перезарядка (`loading`) не считаются (решение 31; `loading` — строкой
`properties`, движок её не читает); боеприпасы героев считаются (шаг БП), у монстров — нет; огнестрел — дальнобойное оружие без особых правил (решение 33); Толчок/Сбить с ног — цель ≤ Large
(SRD) и не крупнее героя на 2 размера (решение 8').

**Схема сейва:** в К2 не меняется (R4:125 «новых полей нет»); текущая версия после шага БП — v14 (миграция данных стрел,
docs/plan-bp.md). Флаги хода (`sneak_used`, `light_attack`, `cunning_strike`,
`steady_aim`, `moved`, `nick_used`, `cleave_ready`) — `ActiveEffect(kind="flag")` по образцу `horde_breaker`
(`combat/actions/features.py:22`); сброс «раз в ход» — в `CombatEngine.start_turn` (`combat/engine.py:376`) снятием флагов по
id у всех участников (как `colossus_used`), без поля в `TurnState`. Пулы `action_surge`, рост `second_wind` — `resources`
через `sync_resources`. Выбор мастерства уровня — `feature_choices["weapon_mastery"]`, без нового поля `LevelChoices`
(поле попало бы в `pending_level.draft` и в отпечаток). `tests/unit/persistence/test_schema_fingerprint.py` остаётся зелёным
без правок (ожидание, не проверено: `SaveBundle.model_json_schema()` не видит `ActiveEffect.params` и ключей `resources`).

## Файлы

**Данные (`src/ai_dm/srd/data/`)** — всё `source: srd-5.2`, `license: CC-BY-4.0`, числа по SRD_CC_v5.2.1.pdf (таблица Weapons,
главы Fighter/Rogue), тексты своими словами; русские названия — dnd.su/глоссарий:
- `weapons/` — 28 новых (итого 38): простое ближнее `club` Дубинка, `greatclub` Палица, `handaxe` Ручной топор, `javelin`
  Метательное копьё, `light_hammer` Лёгкий молот, `mace` Булава, `sickle` Серп; простое дальнее `dart` Дротик, `sling` Праща;
  воинское ближнее `battleaxe` Боевой топор, `flail` Цеп, `glaive` Глефа, `greataxe` Секира, `halberd` Алебарда, `lance`
  Длинное копьё, `maul` Молот, `morningstar` Моргенштерн, `pike` Пика, `rapier` Рапира, `trident` Трезубец, `warhammer`
  Боевой молот, `war_pick` Боевая кирка, `whip` Кнут; воинское дальнее `blowgun` Духовая трубка, `hand_crossbow` Ручной
  арбалет, `heavy_crossbow` Тяжёлый арбалет, `musket` Мушкет, `pistol` Пистолет. Мушкет: 1d12 колющий,
  40/120, `loading`, `two_handed`, `ammunition`, мастерство `slow`, 500 зм, `world_only: true`; пистолет: 1d10 колющий,
  30/90, `loading`, `ammunition`, мастерство `vex`, 250 зм, `world_only: true` (решение 30; числа — по SRD 5.2.1, кабан
  сверяет с PDF). Свойства `reach`, `loading`, `ammunition` — строками `properties`; движок их не читает (решение 31),
  боеприпас — по полю `ammo` из шага БП: мушкет/пистолет `ammo: firearm_bullets`, `hand_crossbow`/`heavy_crossbow` `bolts`,
  праща `sling_bullets`, духовая трубка `needles` (предметы — из БП; тест контента БП «`ammunition` ⇔ `ammo`» ловит пропуск).
- `masteries/cleave.yaml` Рассечение, `masteries/push.yaml` Толчок.
- `items/` — `poisoners_kit` Набор отравителя (`tool: true`, 5000 cp; решение 20); боеприпасы — уже есть из БП.
- `classes/fighter.yaml` — `features`: 2 `action_surge`, 2 `tactical_mind`, 5 `extra_attack`, 5 `tactical_shift` (ПХ как есть);
  `weapon_mastery_by_level: {1: 3, 4: 4, 10: 5, 16: 6}` (решение 28); набор `a`: `chain_mail`, `greatsword`, `flail`,
  `javelin` ×8, `explorers_pack` (решение 23).
- `classes/rogue.yaml` — `features`: 1 `expertise`, 1 `sneak_attack`, 1 `thieves_cant`, 2 `cunning_action`, 3 `steady_aim`,
  5 `cunning_strike`, 5 `uncanny_dodge` (ПХ как есть).
- `features/` новые: `action_surge` (пул `action_surge` max 1, `recover: short_rest all`, `activation: action`),
  `tactical_mind`, `tactical_shift`, `sneak_attack` (`activation: passive`, описание с ростом костей), `expertise` (эффект
  экспертизы `count: 2`), `thieves_cant` (текст), `cunning_action` (`bonus_action`), `steady_aim` (`bonus_action`),
  `cunning_strike` (`options: [cunning_trip, cunning_poison, cunning_withdraw]` — три умения-варианта как у `hunters_prey`,
  но выбор в бою, не на уровне — см. «Умолчания»), `uncanny_dodge` (`reaction`), `improved_critical` (`effects: [{type:
  crit_range, value: 19}]`), `remarkable_athlete` (`effects: [{type: modifier, target: initiative, mode: advantage}, {type:
  modifier, target: skill, skill: athletics, mode: advantage}]`), `fast_hands` (текст), `second_story_work` (текст); правки:
  `second_wind` — `max_by_level: {1: 2, 4: 3, 10: 4}` (решение 27); `deft_explorer` — тот же эффект экспертизы `count: 1`;
  `weapon_mastery` — описание про рост числа у воина.
- `subclasses/fighter/champion.yaml` (3: `improved_critical`, `remarkable_athlete`), `subclasses/rogue/thief.yaml`
  (3: `fast_hands`, `second_story_work`). Загрузчик каталогов подклассов — проверить `content/loader.py` (маппинг по
  `subclasses/<class>/`; у следопыта работает).
- `tables/sneak_attack.yaml` — уровень → число d6: 1:1, 3:2, 5:3, 7:4, 9:5, 11:6, 13:7, 15:8, 17:9, 19:10.
- `feats/great_weapon_fighting.yaml` — `effects: [{type: modifier, target: weapon_damage, when: two_handed, mode: floor,
  value: 3}]`, убрать «пока не считается»; `feats/two_weapon_fighting.yaml` — `effects: [{type: modifier, target:
  weapon_damage, when: off_hand, add: weapon_ability}]`.

**Модели (`content/models/`):** `common.py` — `EffectWhen` += `two_handed`, `off_hand`; `EffectMode` += `floor`, `expertise`;
`EffectAdd` += `weapon_ability`; `classes.py:32` `CharacterClass.weapon_mastery_by_level: dict[int, int] | None = None`;
`items.py:8` `Weapon.world_only: bool = False` (решение 30; контент, не сейв); `Weapon.ammo` и `Item.category: ammo` — из БП;
`features.py` — без правок.

**Правила (`rules/`):** `derived.py` — `attack_parts:249`/`damage_parts:271`/`damage_bonus:276` (вторая рука: без модификатора
характеристики, кроме отрицательного; с TWF — с модификатором), `resource_maxes:400` (уже читает `max_by_level`),
`initiative_bonus:95` (преимущество — `initiative.py`), новая `mastery_limit(hero, registry)` (по `weapon_mastery_by_level`
через `by_level:360`, иначе `weapon_mastery_count`); `progression.py` — `required_choices:112`, `missing_choices:149`,
`next_choice:167`, `choice_options:210` (`weapon_mastery` → оружие с мастерством, которым герой владеет и которого нет в
`weapon_masteries`; `expertise` — как есть), `choice_errors:241` (`weapon_mastery`: владение, не повтор, число по лимиту),
`apply_level_choices:348` (`sheet.weapon_masteries += feature_choices["weapon_mastery"]`); `builder.py:47`
`CharacterChoices.expertise: list[str] = []`, `build_character:257` — проверка числа/владения/повтора при умении экспертизы
на 1 ур., `sheet.skill_expertise = choices.expertise`; `checks.py:22` `skill_check` — Тактический ум (новый
`rules/tactical_mind.py:apply(hero, registry, rng, result)`, решение 18) и преимущество Атлетики по эффекту (`base_adv`);
`rules/modifiers/__init__.py:10` `default_modifier_registry` += новый `rules/modifiers/features.py:FeatureSource` (эффекты
умений героя → `Modifier(crit_min=…)` для `crit_range`, преимущество инициативы для `target: initiative, mode: advantage`);
`roll_pipeline.py:458` `roll_damage_request` — пол кости (GWF) по `tags["two_handed"]` и эффекту `floor` (в логе «1→3»);
`rules/inventory.py:110` `equip` — без правок; `rules/trade.py:22` `merchant_sells` — `world_only` не продаётся (решение
30; `merchant_buys:33` — без правок, скупка по категории); `rules/hero_options.py` `mastery_weapons`/`master/hero.py:37`
`class_data["mastery_weapon_ids"]` — без `world_only` при создании; при уровне (`choice_options:210`) `world_only` оружие
— только если оно в инвентаре героя.

**Бой (`combat/`):** `actions/attack.py` — `attacks_of:62` (бросок, кость универсального), `attack:486` (Скрытая атака,
Невероятное уклонение, флаг `light_attack` после атаки лёгким оружием в действии Атака), `perform:559` (`equip(…,
info.weapon_id)` вместо `info.id`; после броска — новый `combat/thrown.py:drop(engine, ref, info, target_ref)`: `remove_item`
самого дорогого стека, `GroundItem(owner_ref=ref)` в зоне цели, `main_hand=None`, если стек кончился), `spend_attack:546` —
без правок (решение 31); `available.py` — `attack_options:37` (подпись броска), `bonus_actions:536`,
`standard_actions:514` (Всплеск действий при `not turn.action`), `list_options:558` (пункты `cleave`, `cunning_strike`,
`offhand_attack` в нужных ветках; `(ещё N из 2)` — без правок), `pickup_options:409` — без правок (решение 16);
`mastery.py` — `on_hit:17` += `cleave` (флаг как `horde_mark`), `push` (зона: ниже по высоте через `falling.push`, иначе
первая соседняя; лог «отброшен: <зона>»), `mastery_of:7` — без правок (бросок несёт `weapon_id`); новые модули:
`combat/sneak.py` (`eligible(engine, ref, target_ref, result)`: плут с `sneak_attack`, оружие `finesse` или `ranged`, флага
`sneak_used` нет, и (`result.advantage == "advantage"` или боеспособный союзник в зоне цели при `result.advantage !=
"disadvantage"`); `damage(engine, ref, target_ref, crit, info, result)`: кости по таблице минус 1 при флаге `cunning_strike`,
лог «Скрытая атака +Nd6: …», затем `rogue.resolve`), `combat/actions/fighter.py` (`action_surge`, `cleave` — свободная атака
по образцу `features.horde_breaker:42`, `tactical_shift` — внутри `features.second_wind:8` при умении),
`combat/actions/rogue.py` (`cunning_action` — `dash`/`disengage`/`hide` с `params["bonus"]`: `standard.dash:9`,
`stealth.hide:29` учат `bonus` как `standard.disengage:17`; `steady_aim`; `cunning_strike` — выбор эффекта (флаг);
`uncanny_dodge(engine, target_ref, total) -> int`; `resolve` — Сбить с ног: цель ≤ Large, спас Лов СЛ 8+Лов+БМ, Отравить:
только с `poisoners_kit` в инвентаре, спас Тел, «отравлен» 1 мин (`Expiry rounds 10`), Отступить: `turn.disengaged = True`),
`engine.py:40` PERFORM += `offhand_attack`, `action_surge`, `cleave`, `steady_aim`, `cunning_strike` (`dash`/`hide` с бонусом
— те же обработчики), `engine.start_turn:376` — снятие флагов «раз в ход»; `end.py:90` `settle_ground` (решение 17);
`initiative.py:roll_initiative` — `base_adv` по `FeatureSource`; `improvise.py:42` `size_problem`; `protocol/handlers/
combat.py:33` `IMPROVISE_HINTS["target_too_large"]` — «Слишком велик, чтобы сбить с ног: …» (решение 24; сейчас кода
`target_too_large` в подсказках нет — проверить, что `Rejected` с ним доходит до модели и для `push`); `controllers.py:219`
`AutoHeroController.choose_turn` (+ `steady_aim` перед атакой при враге в своей зоне и без движения; `action_surge` при
потраченном действии и живом враге), `pick_attack:167` — без правок.

**UI/игра:** `ui/combat_menu.py` — `CATEGORY_BY_KIND:21`/`RANK_BY_KIND:29` (`offhand_attack`, `cleave`, `horde_breaker` →
target/0; `action_surge`, `steady_aim`, `dash`/`hide` бонусные → free/2), `free_block:188` (строка «Хитрый удар ▸»,
`kind="expand", group="cunning_strike"`), `group_rows:205` (ветка `cunning_strike`); `game/app.py:48`
`CHOICE_TITLES["weapon_mastery"] = "мастерство оружия"`, `record_choice:331` (`weapon_mastery` → `feature_choices`;
`expertise` — append, не замена, чтобы добрать 2); `game/hero_steps.py:432` STEPS — шаг `expertise` после `class_skills`
(`needs_expertise`/`options_expertise`/`count` по умению класса на 1 ур.), `game/hero_create.py:243` — поле;
`protocol/requests.py:925` `HeroSheet.expertise: list[Skill] = []`, `protocol/handlers/hero.py:71,114`, `master/hero.py:37`
`class_data["expertise_count"]`, `master/prompts/hero_sheet_rules.md:13` — строка про expertise; `game/sheet_text.py` —
`inv_lines:171`, новые `weapon_text(weapon)` («1d8 руб. (двумя руками 1d10), универсальное, мастерство: Ослабление» —
решения 4 и 29; слова свойств: лёгкое, фехтовальное, метательное 20/60, двуручное, универсальное, тяжёлое, досягаемость,
перезарядка, боеприпас), `armor_text(armor)` («КД 13 + Лов (не больше +2)», щит «+2 к КД»; `effect_texts:105` — доп.
эффекты магического оружия через запятую после), `ability_line:464` — без правок.

**Devtools/тесты данных:** `devtools/grid_heroes.py:14` `rogue_choices` (`expertise=["stealth", "perception"]`), `:57` `pick`
(`weapon_mastery`, `expertise` ×N); `devtools/sim_grid_baseline.yaml` — перегенерировать (П3); `tests/unit/content/
test_class_kits.py:minimal_choices`, `tests/unit/rules/test_classes_1_20.py:54 pick_choices`, `test_builder.py`,
`tests/unit/game/test_hero_steps.py` — конструкторы плута (`grep -rln 'class_id="rogue"' tests src` → 4 файла, 2026-10-30);
`tests/unit/content/test_srd_minimum.py` — списки `WEAPONS`/`MASTERIES`; тесты торговли с полным ассортиментом оружия
(`grep -rl 'assortment\|category_models' tests/` — кабан проверяет, что число позиций не зашито).

**Документы:** `docs/rules-adaptation.md` — раздел «Воин и плут 1–5» («Адаптации» выше + огнестрел по решениям 30, 31,
33; строка `:99` про боеприпасы — уже переписана в БП);
`docs/glossary.md` — новые термины (Action Surge Всплеск действий, Tactical Mind Тактический ум, Tactical Shift Тактический
сдвиг, Improved Critical Улучшенный критический удар, Remarkable Athlete Выдающийся атлет, Sneak Attack Скрытая атака,
Thieves' Cant Воровской жаргон, Cunning Action Хитрое действие, Steady Aim Верный прицел, Cunning Strike Хитрый удар, Uncanny
Dodge Невероятное уклонение, Fast Hands Быстрые руки, Second-Story Work Работа на высоте, Cleave Рассечение, Push Толчок,
Champion Чемпион, Thief Вор, Musket Мушкет, Pistol Пистолет; Expertise остаётся «Экспертиза» — `glossary.md:187`, не
«Компетентность» груминга); `docs/ARCHITECTURE.md` — F5 (`:1097`) строка про «Хитрый удар ▸» и новые kind, новый раздел «К2»
(флаги хода через `ActiveEffect`, модули `combat/sneak.py`, `thrown.py`, `actions/fighter.py`, `actions/rogue.py`,
`rules/modifiers/features.py`); `docs/BACKLOG.md` — 48, 57, 66 → `docs/done/048-…`, `057-…`, `066-…` (status done, тело без
правок, «Закрыто: Шаг К2, дата — docs/plan-k2.md»); 11 — строка «Боевые стили …» ✅ К2 (по образцу ✅ в теле 11); 50 — «плут
✅ К2, жрец — К3»; 31 — «воин и плут 1–5 ✅ К2»; новые пункты (в конец): смена мастерств после долгого отдыха (решение 28),
свои подклассы воина/плута (решение 10), монстры с метательным оружием (дротики гоблинов — статблок), перезарядка `loading`
(решение 31). BACKLOG 215 — закрыт шагом БП.

**Функции (grep 2026-10-30, a8d726f):** изменяются — `ai_dm.combat.actions.attack:attacks_of` (:62), `:attack` (:486),
`:perform` (:559); `ai_dm.combat.available:attack_options` (:37), `:bonus_actions` (:536), `:standard_actions` (:514),
`:list_options` (:558); `ai_dm.combat.mastery:on_hit` (:17); `ai_dm.combat.actions.features:second_wind` (:8);
`ai_dm.combat.actions.standard:dash` (:9); `ai_dm.combat.stealth:hide` (:29); `ai_dm.combat.engine:CombatEngine.start_turn`
(:376); `ai_dm.combat.end:settle_ground` (:90); `ai_dm.combat.initiative:roll_initiative`; `ai_dm.combat.actions.improvise:
size_problem` (:42); `ai_dm.combat.controllers:AutoHeroController.choose_turn` (:219); `ai_dm.rules.derived:attack_parts`
(:249), `:damage_parts` (:271), `:damage_bonus` (:276), `:initiative_bonus` (:95); `ai_dm.rules.progression:required_choices`
(:112), `:missing_choices` (:149), `:next_choice` (:167), `:choice_options` (:210), `:choice_errors` (:241),
`:apply_level_choices` (:348); `ai_dm.rules.builder:build_character` (:257); `ai_dm.rules.checks:skill_check` (:22);
`ai_dm.rules.roll_pipeline:roll_damage_request` (:458); `ai_dm.rules.modifiers:default_modifier_registry` (:10);
`ai_dm.game.sheet_text:inv_lines` (:171); `ai_dm.game.app:GameApp.record_choice` (:331); `ai_dm.ui.combat_menu:free_block`
(:188), `:group_rows` (:205); `ai_dm.master.hero:class_data` (:37); `ai_dm.devtools.grid_heroes:rogue_choices` (:14),
`:pick` (:57); `ai_dm.rules.trade:merchant_sells` (:22). Новые — `ai_dm.combat.sneak:eligible`,
`:damage`; `ai_dm.combat.thrown:drop`; `ai_dm.combat.actions.fighter:action_surge`, `:cleave`, `:tactical_shift`;
`ai_dm.combat.actions.rogue:cunning_action`, `:steady_aim`, `:cunning_strike`, `:uncanny_dodge`, `:resolve`;
`ai_dm.rules.tactical_mind:apply`; `ai_dm.rules.modifiers.features:FeatureSource.modifiers`; `ai_dm.rules.derived:
mastery_limit`; `ai_dm.game.sheet_text:weapon_text`, `:armor_text`; `ai_dm.game.hero_steps:needs_expertise`,
`:options_expertise`. Не меняются: `mastery_of` (:7), `base_advantage` (:180), `equip` (:110), `pickup_options` (:409),
`fit`/`build_view`/`MenuState` (`combat_menu.py`), `TurnState` (`state/combat.py:68`), `level_up.py`, `spend_attack` (:546).

## Партии

Порядок — family.md (кабан → доеба → мама → свекровь на каждую партию); перед коммитом каждой: `uv run ruff check src tests`,
`make cov` (≥ 94 %), `make smells` (≤ 200 — **сейчас ровно 200/200**, замер `make smells` 2026-10-30), `make dead`, `make mutate
FUNCS=… TESTS=…` + `make mutate-diff` (старые строки → BACKLOG). Коммит партии — после ревью, `git push`.

Предусловие: шаг БП закрыт (docs/plan-bp.md).

1. **П1 — данные и прогрессия** (без боя). Данные (28 оружий с мушкетом и пистолетом `world_only` и `ammo`, мастерства,
   набор отравителя, классы, умения, подклассы, таблица, стили с эффектами — эффекты в П1
   только загружаются), модели, `progression` (экспертиза по данным, `weapon_mastery` на 4 ур. воина, добор экспертизы —
   решение 26), `builder`/создание героя/лист рассказчика (экспертиза плута на 1 ур.; мастерства без `world_only`),
   `sheet_text` (строки оружия/доспеха, 66 ч. 2, «1d8»), `second_wind` 3 на 4 ур., набор воина А по SRD,
   `grid_heroes`/тестовые конструкторы, глоссарий; `merchant_sells` без `world_only` (решение 30).
   На выходе: `uv run pytest tests/unit/content tests/unit/rules tests/unit/game tests/unit/protocol tests/unit/master -q`
   зелёный; воин и плут проходят 1→20 в `test_classes_1_20` с новыми выборами; `/sheet` плута 5 ур. показывает все умения
   (`abilities_lines`) и строки оружия по решению 4.
   mutmut: `FUNCS="ai_dm.rules.progression:required_choices ai_dm.rules.progression:missing_choices ai_dm.rules.progression:
   next_choice ai_dm.rules.progression:choice_options ai_dm.rules.progression:choice_errors ai_dm.rules.progression:
   apply_level_choices ai_dm.rules.builder:build_character ai_dm.rules.derived:mastery_limit ai_dm.game.sheet_text:inv_lines
   ai_dm.game.sheet_text:weapon_text ai_dm.game.sheet_text:armor_text ai_dm.game.app:GameApp.record_choice"
   TESTS="tests/unit/rules tests/unit/game"` — каталоги целиком (AGENTS.md: узкий TESTS — ложные выжившие, шаг 202 реш. 16);
   `grep -l 'progression\|inv_lines' tests/` → `tests/unit/rules/*`, `tests/unit/game/test_inv_*.py`, `test_game_level_choices.py`,
   `tests/unit/protocol/test_gold_loot_gear.py`, `tests/scenarios/test_trophies.py`; время — ожидание, не проверено.
2. **П2 — бой воина и оружие.** Бросок (48) + `thrown.drop` + «подобрал» (решение 17); универсальное двумя руками (решение
   12); GWF/TWF в конвейере; удар второй рукой + Проворство (66 ч. 1); Рассечение (решение 14) и Толчок (решение 13);
   Всплеск действий, Тактический ум (решение 18), Тактический сдвиг, Улучшенный крит (`FeatureSource`), Выдающийся атлет;
   размер у «Лежит» (57, решение 24); PERFORM, `start_turn`; TUI `combat_menu` для новых kind и
   Истребителя орд (решение 25); `rules-adaptation.md` (часть воина и огнестрел).
   На выходе: `uv run pytest tests/unit/combat tests/unit/rules tests/unit/ui -q` зелёный; живая проверка руками — воин 2 ур.
   в тестовом мире (см. «Тесты»).
   mutmut: `FUNCS="ai_dm.combat.actions.attack:attacks_of ai_dm.combat.actions.attack:attack ai_dm.combat.actions.attack:perform
   ai_dm.combat.available:attack_options ai_dm.combat.available:bonus_actions ai_dm.combat.available:standard_actions
   ai_dm.combat.available:list_options ai_dm.combat.mastery:on_hit ai_dm.combat.thrown:drop ai_dm.combat.actions.fighter:
   action_surge ai_dm.combat.actions.fighter:cleave ai_dm.combat.actions.features:second_wind ai_dm.combat.end:settle_ground
   ai_dm.combat.actions.improvise:size_problem ai_dm.rules.roll_pipeline:roll_damage_request ai_dm.rules.derived:damage_parts
   ai_dm.rules.derived:damage_bonus ai_dm.rules.tactical_mind:apply ai_dm.rules.modifiers.features:FeatureSource.modifiers
   ai_dm.rules.checks:skill_check" TESTS="tests/unit/combat tests/unit/rules"`; `combat_menu` — отдельным запуском
   `FUNCS="ai_dm.ui.combat_menu:free_block ai_dm.ui.combat_menu:group_rows" TESTS="tests/unit/ui"` (Pilot-тесты, долго —
   plan-111 «Функции»).
3. **П3 — бой плута, авто-герой, сетка, закрытие.** Скрытая атака (решение 5), Хитрое действие, Верный прицел, Хитрый удар
   (решения 6, 20) + группа в TUI, Невероятное уклонение (решение 19), Быстрые руки/Работа на высоте — текст;
   `AutoHeroController` (50); `make sim-grid` — новая `sim_grid_baseline.yaml`, числа до/после — в «Итог» (свинопас: порога
   побед не ставим); `rules-adaptation.md` (часть плута), `ARCHITECTURE.md`, карточки done 48/57/66, пометки в 11/50/31,
   новые пункты беклога; BACKLOG 233 (`MEMORY_CONTEXT_CAP` — cap из прогона или развести сценарии; «Правки по ревью»
   П1 п. 8) — карточка done (снято: 233 остаётся в беклоге — разбор хэнд-бэка кабана П3, п. 1).
   На выходе: `uv run pytest tests/unit/combat tests/unit/ui tests/unit/devtools -q`; полный `make cov`; живой прогон —
   Влад играет плутом или воином в своём мире (AGENTS.md: живой прогон = игра; шпаргалка — `~/.config/ai-dm/checklists/
   checklist-k2-live.md`), итог — в «Итог».
   mutmut: `FUNCS="ai_dm.combat.sneak:eligible ai_dm.combat.sneak:damage ai_dm.combat.actions.rogue:cunning_action
   ai_dm.combat.actions.rogue:steady_aim ai_dm.combat.actions.rogue:cunning_strike ai_dm.combat.actions.rogue:uncanny_dodge
   ai_dm.combat.actions.rogue:resolve ai_dm.combat.engine:CombatEngine.start_turn ai_dm.combat.controllers:
   AutoHeroController.choose_turn ai_dm.combat.actions.standard:dash ai_dm.combat.stealth:hide"
   TESTS="tests/unit/combat"`; `ui/combat_menu` — как в П2.

## Тесты (для кабана-доебы)

Все «ожидание, не проверено», кроме помеченных. Образцы: `tests/unit/combat/combat_kit.py` (`make_engine`, `make_fighter:177`,
`give_weapon:191`, `option_ids:309`), `test_mastery.py` (33 теста), `test_shove_size.py` (`:99` — образец `target_too_large`),
`test_horde_breaker.py` (свободная атака по флагу), `tests/unit/rules/test_classes_1_20.py`, `test_progression_choices.py`
(101 тест), `tests/unit/ui/test_combat_menu.py` (группа `ammo:`), `tests/unit/game/test_inv_*.py`.

П1:
- все новые YAML грузятся; `registry.all("weapon")` = 38; у мушкета, пистолета, ручного и тяжёлого арбалетов, пращи и
  трубки задан `ammo` (тест контента БП зелёный); у каждого оружия `mastery` из 8; `cleave`, `push` есть; мушкет
  `kind: ranged`, `two_handed`, `loading`; пистолет одноручный; `test_srd_minimum.py` — дополнить.
- владение: `weapon_proficient` — воин владеет мушкетом и пистолетом (воинское), плут — нет (ни `finesse`, ни `light`),
  ручным арбалетом — да (`light`); следопыт — да.
- воин 1→5 (`pick_choices`): `required_choices(…, 4)` = {asi_or_feat, weapon_mastery}; после 4 ур. `len(weapon_masteries) == 4`;
  `resource_maxes["second_wind"]` 2/2/2/3/3; `action_surge` появляется на 2 ур. = 1; `hero_feature_ids` на 5 ур. содержит
  `extra_attack`, `tactical_shift`; Чемпион на 3 → `improved_critical`, `remarkable_athlete`; `weapon_mastery` 5-й на 4 ур.
  с оружием без владения/повтором → ошибка; набор `a` воина — цеп и 8 метательных копий (`test_class_kits.py`).
- плут: `build_character` с `expertise=["stealth", "perception"]` → `skill_expertise` = 2; без экспертизы → ошибка кода
  `expertise_invalid`; навык не из владений → ошибка; `required_choices(…, 3)` = {subclass}; Вор на 3 → `fast_hands`;
  5 ур. → `cunning_strike`, `uncanny_dodge`; герой-плут 1 ур. с пустой `skill_expertise` (как Томас) на 2 ур. →
  `next_choice` = `expertise` дважды, затем `None`; `skill_bonus` Скрытность с экспертизой = Лов + 2·БМ.
- следопыт (регрессия): `required_choices(…, 2)` = {fighting_style, expertise} — как `test_ranger_progression.py`.
- `inv_lines` у Арна (`chain_mail`, `shield`, `longsword`, `spear`): «Длинный меч — 1d8 руб. (двумя руками 1d10),
  универсальное, мастерство: Ослабление, 15 зм»; доспех «КД 16» (chain_mail, без Лов), щит «+2 к КД», кольчужная рубаха
  «КД 13 + Лов (не больше +2)»; мушкет — «1d12 кол., 40/120, двуручное, перезарядка, боеприпас, мастерство: Замедление»;
  `test_inv_prices.py` и `test_gold_loot_gear.py` остаются зелёными (цена после текста через запятую).
- `hero_steps`: у плута шаг `expertise` с 2 выборами из `class_skills` + предыстории, у воина шага нет; `HeroSheet`
  рассказчика с `expertise` → лист собирается; шаг мастерства воина — 38 вариантов, TUI-мастер не ломается (руками).
- торговля (решение 30): `assortment` кузнеца (`trade.presets.smith`, `defaults.toml:173`) — 36 оружий, без `musket`/
  `pistol`; `merchant_buys` мушкет — да (категория `weapon`); `mastery_weapon_ids` воина у рассказчика и `options_masteries`
  при создании — без них; воин с мушкетом в инвентаре на 4 ур. видит его в выборе мастерства, без мушкета — нет.
- сетка: `grid_heroes.build_hero("fighter", 5)` и `("rogue", 5)` собираются без ошибок (ошибка `pick` — красный).

П2:
- бросок: герой с кинжалом (×2) и гоблином в соседней зоне → есть `attack:dagger_thrown:g1` (`mode: ranged`), нет
  `attack:dagger:g1`; после броска `count_item(hero, "dagger") == 1`, `main_hand == "dagger"`; `ground_items` =
  [`dagger`, зона цели, `owner_ref=hero`]; второй бросок → `main_hand is None`; в своей зоне кинжал — помеха («враг рядом»);
  дротик (20/60) из зоны через одну — нет варианта; метательное копьё (30/120) из соседней — `normal`, через одну — помеха;
  мастерство Nick/Sap срабатывает при броске (`mastery_of` по `weapon_id`); победа → кинжал в инвентаре, лог «Арн: подобрал
  кинжал», чужое выбитое — «достаётся» как было (`test_disarm_end.py` зелёный после правки строки своего оружия);
  бегство → «остался на поле боя»; `pickup:0` в зоне цели — `cost="free"` при целом свободном взаимодействии, иначе
  `"action"` (как у выбитого, `test_pickup.py`).
- универсальное: длинный меч без щита → `info.dice == "1d10"`, со щитом — `1d8`; GWF: двуручный меч 2d6 с бросками (1, 2) →
  в логе «1→3, 2→3», итог 6 + Сил; GWF с длинным мечом и щитом — не действует; Savage Attacker + GWF не ломают друг друга
  (`roll_damage_request`, `rerolls`).
- вторая рука: плут с `shortsword` в правой и `dagger` в левой: до Атаки `offhand_attack` нет; после Атаки короткий меч →
  `offhand_attack:g1` (`cost="bonus"`, подпись «Удар второй рукой: кинжал → Гоблин»), урон `1d4` без Лов (Лов +3 не
  прибавляется, Сил −1 прибавляется); со стилем TWF (воин) → +Лов; после удара `turn.bonus` False; атака тяжёлым/не лёгким
  оружием → пункта нет; Nick: кинжал в левой в `weapon_masteries` → `cost="free"`, подпись «(Проворство)», бонусное действие
  цело, второй раз за ход пункта нет.
- Рассечение: секира, попадание по g1 при g2 в той же зоне → пункт `cleave:g2` (free, «Рассечение: секира → Гоблин 2»);
  урон без модификатора характеристики; раз в ход; промах — пункта нет. Толчок: боевой молот, попадание → цель в соседней
  зоне (ниже, если есть; падение через `falling.push`), лог «отброшен: <зона>»; цель Huge → без толчка.
- Всплеск действий: воин 2 ур., действие потрачено → `action_surge` (free) в `option_ids`; выбор → `turn.action` True, пул 0,
  пункта больше нет; короткий отдых → пул 1; 1 ур. — пункта нет.
- Тактический ум: проверка Скрытность СЛ 15, бросок 12 → +1d10 (3) = 15 → успех, `second_wind.current` −1; +1d10 (2) →
  провал, пул не тратится; пул 0 → ничего. Тактический сдвиг: Второе дыхание на 5 ур. → `turn.disengaged` True; на 2 ур. — нет.
- Улучшенный крит: Чемпион, d20 = 19 → `crit`; воин без подкласса — `hit`. Выдающийся атлет: инициатива с преимуществом
  (две кости в логе); Атлетика с преимуществом; крит → `turn.disengaged`.
- «Лежит» и размер (57): человек → огр (Large) `prone` — работает; → великан (Huge) → `Rejected("target_too_large")` до
  броска, действие цело (как `test_shove_size.py:99`); подсказка рассказчику начинается с «Слишком велик, чтобы сбить с ног»;
  укус волка — `test_monster_on_hit.py` зелёный без правок.
- огнестрел (решения 31, 33): воин 5 ур. с мушкетом и 10 пулями — две атаки за действие как с луком, после них 8 пуль
  (механика БП); со стилем «Стрельба» +2 к атаке мушкетом; `slow` при попадании; плут с пистолетом — без владения (без БМ);
  пистолет с 0 пуль — пункта нет (БП).
- TUI: `build_view` с `offhand_attack` → строка в блоке цели сразу после атак; `horde_breaker`/`cleave` — в блоке цели;
  `action_surge` в бесцелевом блоке; плоский список/id — `test_list_options_ids_are_unchanged…` зелёный; Pilot-тест: воин
  2 ур. — строка «Всплеск действий» после атаки.
- Проверка руками (П2): TUI, тестовый мир с воином (Арн 1 ур. — `vale-43cd433c`, копия во временный каталог) — выдать 300
  опыта (dev-способ по `test_game_fight_debug.py`) → уровень 2: Всплеск действий в бою после атаки; бросок копья в соседнюю
  зону, после боя «Арн: подобрал копьё»; `/inv` — строки с уроном/КД.

П3:
- Скрытая атака: плут 1 ур., короткий меч, союзник-NPC в зоне цели → при попадании «Скрытая атака +1d6», урон +d6;
  без союзника и без преимущества — нет; с преимуществом (скрытно) — есть; с помехой и союзником — нет; раз в ход
  (провоцированная атака в чужой ход после своей — нет); крит удваивает кости; 3 ур. → 2d6, 5 ур. → 3d6; безоружный/
  импровизированный — нет; лук, пистолет — да (ranged); длинный меч — нет.
- Хитрое действие: плут 2 ур. → в `bonus_actions` `dash_bonus`, `disengage_bonus`, `hide_bonus` (последний — при укрытии);
  подписи «Хитрое действие: Рывок / Отход / Спрятаться»; выбор тратит `turn.bonus`, действие цело; 1 ур. — нет.
- Верный прицел: плут 3 ур., не двигался → `steady_aim`; после — следующая атака с преимуществом (→ Скрытая атака без
  союзника), `turn.move == 0`, `move_options` пуст; после перемещения в этом ходу пункта нет.
- Хитрый удар: 5 ур. → группа «Хитрый удар ▸» в TUI (`build_view`), раскрытие → «Сбить с ног», «Отступить», «Отравить» только
  при `poisoners_kit` в инвентаре; выбор «Сбить с ног» → следующая Скрытая атака 2d6 + спас Лов СЛ 8+Лов+БМ, провал →
  «Лежит»; цель Huge → без эффекта, кости 3d6; «Отступить» → `turn.disengaged`; флаг снимается в конце хода.
- Невероятное уклонение: плут 5 ур. получает попадание 10 → 5, «Невероятное уклонение: 10 → 5», `turn.reaction` False;
  второе попадание в раунде — полный урон; ослеплённый — нет.
- Авто-герой: `AutoHeroController` у плута 3 ур. в сетке `goblins3` выбирает `steady_aim` перед атакой; воин 2 ур. —
  `action_surge` после атаки; `uv run python -m ai_dm.devtools.sim_grid --check` зелёный с новой базовой линией; старая линия:
  плут 5 ур. goblins3 17.0 %, cellar 0.0 % (`devtools/sim_grid_baseline.yaml`, проверено 2026-10-30) — новые числа в «Итог».
- Схема: `tests/unit/persistence/test_schema_fingerprint.py` зелёный на v14 из БП без новой перегенерации (если красный —
  см. риск «отпечаток»).
- Проверка руками (П3): плут Томас (`u1_live`, копия) → 2 ур.: меню добирает 2 экспертизы; бой — Хитрое действие в меню;
  Скрытая атака в логе при атаке из засады.

## Развилки и риски

Р1–Р19 первой редакции решены (Решения 11–29); Р20–Р23 второй — Решения 30–33; Р24–Р28 третьей (боеприпасы) — Решения
34–38, подробности и новые развилки шага БП — docs/plan-bp.md «Развилки и риски». Риски К2:
- **Риск — smells 200/200** (замер 2026-10-30): любой новый smell валит порог; мера — новые мелкие модули, не ветвление в
  `attack`/`list_options`/`target_block`; при красном кабан убирает smell в том же модуле, `vulture_allowlist`/порог не трогать.
- **Риск — отпечаток сейва:** любое новое поле в моделях сейва (`LevelChoices`, `TurnState`, `CharacterSheet`) →
  `test_schema_fingerprint` красный → ещё одна версия (v15, раз v14 занята миграцией стрел) с пустой миграцией (образец ФС,
  `m0013`), решает архитектор; план полей не добавляет.
- **Риск — `attack()` и так 60 строк** (`attack.py:486–543`): Скрытая атака и Уклонение — вызовами новых функций, не ветками.
- **Риск — регресс следопыта/Грея:** `attacks_of`, `bonus_actions`, `required_choices` общие; `test_ranger_combat.py`,
  `test_ranger_progression.py`, `test_game_grey_combat.py` — в каждой партии; у Грея (8 ур., `north_wind_blade` — не лёгкое)
  вторая рука не появится.
- **Риск — ассортимент лавок вырос с 10 до 38 оружий** во всех мирах: окно торговли в TUI (`ui/tui` shop modal) — проверить
  руками, что список листается; тесты торговли с зашитым числом позиций — поправить (П1).
- **Риск — mutmut по `tests/unit/combat`** (69 файлов `test_*.py`, `ls` 2026-10-30) долго — ожидание, не проверено; усечение —
  решение оркестратора с пометкой «узкий TESTS».
- **Риск — 38 оружий в шаге создания героя** (`options_masteries`): длинный список в TUI-мастере; проверить руками в П1.

## Умолчания (внутреннее)

- Флаги хода — `ActiveEffect(id=<флаг>, kind="flag", source=ref, expires=Expiry(end_of_turn, 0, owner=ref))`; «раз в ход
  для всех» (`sneak_used`) снимается в `start_turn` по id — как `colossus_used`; сейв не меняется.
- Экспертиза в данных — `EffectSpec(type="proficiency", target="skill", mode="expertise", count=N)` у `expertise` (2) и
  `deft_explorer` (1); `required_choices` считает недобор; `record_choice("expertise")` — append.
- Выбор мастерства уровня — `feature_choices["weapon_mastery"]` (id оружия, накопительно), `mastery_limit` =
  `by_level(weapon_mastery_by_level)`; `apply_level_choices` переносит в `sheet.weapon_masteries`.
- Скрытая атака — `tables/sneak_attack.yaml` (`Table.rows` int), кости `f"{n}d6"`, тип урона — оружия; крит удваивает
  (через `roll_damage(…, crit)`); Хитрый удар — кости `n − 1`, СЛ 8 + Лов + БМ.
- Бросок — id `f"{weapon_id}_thrown"`, `weapon_id` оружия; `perform` экипирует по `weapon_id`; `thrown.drop` снимает самый
  дорогой стек (`dearest_cost`, как `strip_weapon`); на землю — `GroundItem(owner_ref=ref)`; монстры чужое не берут
  (`can_pick`).
- Вторая рука — флаг `light_attack` ставится в `attack.perform`, если `info.weapon_id` лёгкое и это действие Атака
  (`turn.action` только что потрачено или `attacks_left`); пункт требует `equipped.off_hand` лёгкое ≠ оружие атаки;
  с Проворством `cost="free"` и флаг `nick_used`.
- GWF — `tags["two_handed"]` ставит `roll_damage` по `AttackInfo.two_handed` (новый атрибут; двуручное или универсальное
  двумя руками); `floor` применяется к каждой кости оружия, лог «1→3»; с Savage Attacker — пол к обоим наборам.
- TWF — `damage_parts` для `off_hand=True`: без части характеристики, если модификатор ≥ 0 и нет эффекта `off_hand`.
- Толчок — зона выбирается движком в `mastery.on_hit`, без пункта меню; Рассечение — флаг `cleave_ready` с `weapon`/`target`/
  `zone`, пункт `cleave:<цель>` (free) как `horde_options`; урон без модификатора: `AttackInfo` с `damage_bonus=0`,
  `damage_parts=[]`.
- `FeatureSource` — только для героев (`hasattr(actor, "sheet")`), читает `hero_effects`; `crit_range` → `crit_min`;
  `initiative` + `advantage` → `advantage=True` для `kind == "initiative"`; Атлетика — в `skill_check` через `base_adv`.
- Тактический ум — `rules/tactical_mind.py`, вызов в `skill_check` после `roll` при `dc is not None` и `outcome == "fail"`;
  текст добавляется к `result.log.text`.
- Огнестрел — `kind: ranged`, `category: martial`, без `heavy`; `Weapon.world_only: bool = False` (контент, не сейв;
  решение 30), `merchant_sells` и список мастерств при создании его отсеивают; при уровне — только из инвентаря.
- Боеприпасы нового оружия — только поле `ammo` в YAML; механика, флаг `ammo_spent`, хелпер `give_weapon` — из БП; в наборах
  К2 (воин a, по решению 23) боеприпасов нет.
- Авто-герой: порядок в `choose_turn` — Второе дыхание → `steady_aim` (враг в своей зоне, не ходил) → стабилизация/
  Истребитель → подбор → заклинание → `action_surge` после тактики (если действие потрачено и есть боеспособный враг).
- Имена тестов — стиль файлов (`test_<что>_<ожидание>`); Pilot-тесты — `tests/unit/ui/tui/test_tui_combat_menu.py`, без
  маркера `slow` (как соседние); чек-лист живого прогона — `~/.config/ai-dm/checklists/checklist-k2-live.md` (не в репо).
- Карточки done, пометки в 11/50/31, строки ROADMAP/handoff — при закрытии, после аппрува, по RULES; строка К2 в ROADMAP
  уже без «v11» (архитектор 2026-10-30): сейв v14 из БП, К2 новых полей не добавляет.

## Правки по ревью

### П1 — разбор хэнд-бэка кабана (папа-кабан, 2026-10-30; дифф не закоммичен)

Проверено по коду: `git diff` 46 файлов (+404/−87), новые — 28 оружий, 14 умений, 2 подкласса, таблица, 2 мастерства,
набор отравителя. Таблица оружия (38 позиций: кость, универсальная кость, тип, цена, дальность, свойства, мастерство)
сверена с SRD 5.2.1 — расхождений нет; числа умений (Второе дыхание 2/3/4, Всплеск 1, Тактический ум 1d10, Скрытая атака
по таблице, Улучшенный крит 19, СЛ Хитрого удара 8 + Лов + БМ) — верны.

**Вернуть кабану (П1, до доебы):**
1. **Вопрос 1 — экспертиза у рассказчика.** Фильтр `PromptBuilder.sheet_data` (`master/prompt.py:460`: умения с
   `effects` скрыты — «движок считает сам») верен, `deft_explorer`/`expertise` под него попадают правильно. Но план уже
   требует поле («Поведение» п. 3: «лист героя у рассказчика — поле `expertise`») — в диффе его нет. Сделать:
   `sheet_data` → `data["expertise"] = list(sheet.skill_expertise)`, только если список не пуст (как `languages`);
   `master/prompts/narrator_rules.md:112` — в перечень состояния героя добавить «навыки с экспертизой `expertise`
   (бонус мастерства удвоен)»; тест в `tests/unit/master` — плут с экспертизой → поле есть, воин → поля нет. Golden
   `k0_sheet_data_v4_dragon.json` перегенерировать после этого: блок `deft_explorer` остаётся убранным (фильтр),
   добавится `"expertise": ["survival"]` (Грей, `tests/fixtures/saves/v4_dragon/heroes/01_грей/hero.json`).
2. **Вопрос 2 — подсказка `not_sold`.** Регресс в области плана (риск «ассортимент вырос с 10 до 38»): `sold_ids`
   (`protocol/hints.py:49`) ставит купленное у героя первым, а `allowed()` (`:9`) сортирует и режет до 20 — с 36 оружиями
   у кузнеца стек героя из подсказки выпадает. Правка теста на `arrows` маскирует регресс — вернуть `scimitar`. Код:
   `allowed(ids, first=())` — элементы `first` впереди, остаток по алфавиту, общий срез `LIMIT`; `not_sold`
   (`handlers/trade_pick.py:131`) передаёт `first=[e.item_id for e in npc.trade.stock]`. Тест: стек `scimitar` у кузнеца при
   ассортименте > 20 → `scimitar` в сообщении ровно один раз. Остальные вызовы `allowed` не меняются.
3. **`cunning_action.yaml`** — «Рывок, Отход или Засада» → «Спрятаться» (решение 21, `glossary.md:208`).

**Принято как уточнение плана (кабану правок нет):**
4. `cunning_strike.yaml` без `options` — верно: `option_features_at` потребовал бы выбор на 5 ур., а Хитрый удар
   выбирается в бою. Три варианта — в коде П3 (`combat/actions/rogue.py:resolve`, подписи по решению 21), умений
   `cunning_trip`/`cunning_poison`/`cunning_withdraw` в данных нет; строка «Файлы» про `options` — снята этой правкой.
   Побочно верно: без `effects`/`options` умение видно рассказчику текстом.
5. `expertise_due` = `max(новое на этом уровне, итог по умениям − len(skill_expertise))` вместо «итог − есть».
   Гибрид ≥ формулы плана, отличается только когда у героя экспертиз уже больше, чем дали умения до этого уровня (тогда
   план дал бы 0, гибрид — выбор всё равно) — это точнее SRD (Ловкий исследователь даёт ещё один навык независимо от
   имеющихся). Добор Томаса (решение 26) сохранён: плут 1 ур. без экспертизы на 2 ур. → 2 выбора. `ranger_kit.ranger_at`
   считает экспертизу выбранной с 3 ур. — фикстура, не поведение.
6. `weapon_text(weapon, registry)` — реестр нужен для имени мастерства; сигнатура внутренняя.
7. Мастерство уровня — только при росте `weapon_mastery_by_level`, без добора: `build_character` требует ровно
   `weapon_mastery_count` (`mastery_count_invalid`), живые воины 1 ур. собраны им — недобора быть не может.
8. `MEMORY_CONTEXT_CAP` 3010 → 3045 — та же правка, что БП (plan-bp.md «Правки по ревью» п. 12) и ФС; причина — рост
   реестра (28 оружий, умения) — не проверена замером, прогон достаточен. Но BACKLOG 233 («делать при следующем сдвиге
   (К2)») и ROADMAP:159 («233 → К2 при сдвиге») — сдвиг случился: 233 входит в К2 **П3** (закрытие): cap из прогона или
   развести ступень chapters и переполнение по сценариям (текст пункта). В П3, не П1: реестр после П1 не растёт, cap
   стабилен; П1 — 46 файлов; 233 — устройство сценария, от кода П1 не зависит. К2 закрывает 233 карточкой done.
9. Golden `k0_sheet_data_v4_dragon.json` — убран `deft_explorer`, изменён текст `weapon_mastery`: оба следствия фильтра
   и данных, верны; золото неполное до п. 1. `k0_sheet_v4_dragon.txt` не тронут — оружие Грея `source: world`, `inv_lines`
   идёт через `world_item_text`.
10. Полный pytest вместо затронутых — без последствий (время кабана); в «Итог» как расход.

**Окно Владу (видимое пользователю — развилки, не умолчания):**
- Р29 — дальность в строке оружия: (а) кабана — слово свойства с дальностью: «метательное 20/60», «боеприпас 40/120»
  (мушкет: «1d12 кол., двуручное, перезарядка, боеприпас 40/120, мастерство: Замедление»); (б) по образцу «Тесты П1» —
  дальность отдельной частью после урона: «1d12 кол., 40/120, двуручное, перезарядка, боеприпас, …». Рекомендую (а) —
  одна форма для метательного и стрелкового, дальность стоит у свойства, которое её даёт. При (а) строка мушкета в
  «Тесты П1» читается по (а).
- Р30 — духовая трубка (SRD урон «1», без кости): парсер `core/dice.py:7` `DICE_RE` числа не принимает, кабан записал
  `1d1` — в `/inv` «1d1 кол.», в логе боя «1d1». (а) оставить `1d1` (крит даёт 2 вместо 1 — отличие от SRD в 1 хит
  у оружия, которым почти не бьют), пункт беклога low «урон числом без кости (`damage_dice: "1"`)»; (б) в П2 научить
  `parse_dice` числу (`count 0`, `modifier 1`) и `weapon_text` печатать «1 кол.» — трогает `roll_damage_dice`/крит у
  всех. Рекомендую (а).

**В BACKLOG (новые пункты, заводит оркестратор):** при Р30 = (а) — «урон оружия числом без кости».

**Для доебы П1 дополнительно:** п. 1 — `sheet_data` плута/воина и golden; п. 2 — `allowed(first=…)` (срез 20, без дубля);
п. 5 — `expertise_due` следопыта 2 ур. с уже заданной экспертизой → 1, плут 1 ур. без экспертизы на 2 ур. → 2, на 3 ур.
с двумя → 0; `tests/unit/content/test_srd_minimum.py` — 38 оружий, 15 таблиц (есть в диффе).

### П1 — ответы на ревью мамы (папа-кабан, 2026-10-30; scratchpad `k2-p1-mama.md`)

Проверено по коду: `build_character` (`rules/builder.py:473–476`) считает владением для экспертизы навыки предыстории,
`class_skills`, навыки черт (`feat_skills`) и навык вида (`species_choices["skill"]`); `hero_sheet_rules.md:14` говорит
рассказчику то же. Мастер TUI (`game/hero_steps.py:272` `options_expertise`) даёт только предысторию + `class_skills`, потому
что шаг `expertise` (`STEPS`, `:470`) стоит раньше `species_skill` (`:493`), `species_feat` (`:497`) и `feat_picks_*`
(`:501`, `:505`). SRD 5.2.1 «Expertise»: любые два навыка, которыми плут владеет. Расхождение мамы подтверждено: плут-человек
с Умелостью или Одарённым в TUI не может взять экспертизу в этих навыках, через рассказчика — может.

**Окно Владу (видимое — порядок шагов мастера и список вариантов):**
- Р31 — экспертиза в мастере создания плута: (а) шаг «Экспертиза» переехать после «Выбор черты вида» (перед «Набор
  класса»), варианты — все навыки героя: предыстория, класс, Умелость, выборы черт (как у `build_character` и
  рассказчика); (б) оставить как есть — после «Навыки класса», только предыстория + класс; записать в план, что TUI уже
  рассказчика. Рекомендую (а): одно правило для трёх путей создания (TUI, рассказчик, пак), по SRD; цена — перенос
  одного `StepDef` и одна строка в `options_expertise`.
  При (а) кабану: `STEPS` — `StepDef("expertise", …)` перенести сразу после `feat_picks_species` (`:505–509`);
  `options_expertise` — `owned = spec_skills(draft, registry) + draft.class_skills + draft.feat_picks_bg +
  draft.feat_picks_species + ([draft.species_skill] if draft.species_skill else [])` (инструменты из выборов черт
  отсеет текущий фильтр `s in SKILLS`); `CODE_STEPS` (`:530`) — добавить `"expertise_invalid": "expertise"` (сейчас код
  ошибки падает в `species`). Тесты `tests/unit/game/test_hero_steps.py`: `KEYS` (`:29`) и шапка (`:4`) — новый порядок;
  `test_rogue_expertise_options_are_class_and_background_skills` (`:311`) — остаётся (без вида/черт список тот же);
  новый — человек-плут с `species_skill="persuasion"` и `feat_picks_species=["arcana"]` видит оба в вариантах
  `expertise`; `step_for_code("expertise_invalid") == "expertise"`. `clear_from` правок не требует: смена навыка вида
  или черты теперь сбрасывает экспертизу — так и нужно. При (б) кабану правок нет.
- Р32 — набор снаряжения воина и плута. По SRD 5.2.1: воин A и B — Dungeoneer's Pack, плут A — Burglar's Pack,
  следопыт — Explorer's Pack. В данных с К0 один предмет `items/explorers_pack.yaml` «Набор путешественника» (описание,
  без механики) у всех классов: воин A/B (`fighter.yaml:79`, `:111`), плут (`rogue.yaml:90`), жрец (`cleric.yaml:72`,
  в SRD — Priest's Pack), волшебник (`wizard.yaml:71`, Scholar's Pack). Решение 23 про набор говорило только о цепе и
  копьях; набор кабан не менял (в HEAD тот же `explorers_pack`) — это не ошибка П1, а соглашение данных К0.
  (а) оставить один набор у всех; пункт беклога low «наборы снаряжения по SRD: Dungeoneer's, Burglar's, Priest's,
  Scholar's — предметы-описания и замена в `starting_kits`»; (б) в П1 завести `dungeoneers_pack` и `burglars_pack`
  (два yaml: имя, описание, `cost_cp` по таблице SRD) и подставить воину A/B и плуту A; жрец и волшебник — беклог.
  Рекомендую (а): предмет без механики, игрок видит одну строку инвентаря; К2 — про бой, а не про снаряжение всех
  классов; при (б) правка на полпути (два класса из четырёх). При (б) кабану: два файла в `items/`, три строки в
  `classes/`, тест `test_fighter_kit_a_keeps_chain_mail_greatsword_and_gold` (`test_class_kits.py:168`) и аналог для B
  и плута — новый id набора; `glossary.md` — Dungeoneer's Pack / Burglar's Pack.

**В BACKLOG (заводит оркестратор):** при Р32 = (а) — «наборы снаряжения по SRD (Dungeoneer's, Burglar's, Priest's,
Scholar's)».

**Остальные ⚠️ мамы — кабану без развилок:** тест на ветку `new` в `expertise_due` (следопыт 1→2 с заданной
`skill_expertise`) — он же п. 5 «Для доебы П1»; имя теста `test_skill_without_expertise_is_dex_plus_single_proficiency`
(`test_classes_1_20.py:469`, проверять один навык) — как сказала мама; тест воина 5 ур. в `test_grid_heroes.py:218` уже
называется `test_fighter_level_5_has_four_masteries` — правки нет.

**`required_choices` после `apply_level_choices` (вопрос мамы, сверка кабана) — так и задумано, теста для доебы нет.**
По коду (`rules/progression.py:127–133`) `expertise_due` на том же уровне после применения по-прежнему ≥ `new`, и
`required_choices(…, level)` снова вернёт `expertise` — как и `fighting_style` (`:152`, по `ref.level == level`) и
`weapon_mastery` (`:158`, по росту таблицы): функция отвечает «что выбирают на уровне level» (комментарий `:145`), а не
«что ещё не выбрано» — за это отвечают `next_choice`/`choice_errors` по `pending_level.draft`. Все живые вызовы
(`rules/level_up.py:36,42` через `preview_hero`, `campaign/build.py:89`, `devtools/grid_heroes.py:80`) идут до применения;
после `apply_level_choices` `pending_level = None` (`level_up.py:58–59`), и вопрос не задаётся. Поведение игроку не видно,
развилки нет. Снятый пункт «доебе тестом» из абзаца выше — отменён; тест кабана
`test_ranger_level_2_requires_expertise_even_with_one_already_chosen` (`test_classes_1_20.py:534`) закрывает ветку `new`
(п. 5 «Для доебы П1», ⚠️ мамы).

### П1 — исправлено по ревью мамы (кабан, 2026-10-30)

- Тест ветки `new` в `expertise_due` (следопыт 2 ур. с выбранной экспертизой) — `test_classes_1_20.py`.
- Имена тестов: `test_skill_without_expertise_…` проверяет `acrobatics`; `test_fighter_level_5_has_four_masteries`.
- Р31 (а), решение 41 Влада: шаг `expertise` после `feat_picks_species`, `options_expertise` — все навыки героя,
  `CODE_STEPS["expertise_invalid"]`; тесты в `test_hero_steps.py`.
- Р32 (а), решение 42 Влада: `explorers_pack` без изменений — BACKLOG 235.
- `required_choices` после применения — без правок (вердикт папы выше).
- Р29/Р30 — решения 39–40 Влада, тесты «40/120» и `1d1` оставлены.
- Круг 2 мамы: тест навыков черты предыстории в `options_expertise`; экспертиза сбрасывается `clear_from` при смене
  навыка вида/черты (код не менялся) — тест `test_changing_species_skill_clears_expertise`.
- mutmut П1 (решения Влада окнами 2026-10-30/31): бесконечные `while` в `test_game_level_choices.py` заменены пределом
  `MAX_CHOICE_STEPS` (доеба); таймаут mutmut ×2 — только на время прогона. Выжившие в диффе 17: 16 убиты тестами
  доебы (`test_classes_1_20.py`, `test_game_level_choices.py`), `options_expertise` мутант 12 — эквивалентный
  (`None` отсекает `s in SKILLS`). Старые строки — BACKLOG 236.
- Круг 5 мамы (кабан): текст `expertise_problem` — «экспертиза: нужно навыков — {expected}, без повторов» (было
  «нужно 2 разных навыков»), тест поправлен; `StubRegistry` без изменений (всё используется). Правка текста — после
  старта повтора mutmut/cov: «cov: цифра до правки builder.py», мутанты этой строки — по старому тексту.
- Повтор mutmut (2026-10-31, 1889 мутантов): в диффе выжили 7, старых 301 (BACKLOG 236); cov 98,18 %. Доеба:
  `weapon_text` 3, 4, 5, 28, 33 и `build_character` 604 — новые тесты в `test_inv_prices.py`, `test_builder.py`;
  `options_expertise` 12 — эквивалентный. Повтор mutmut по ним — Влад «не надо» (окно 16:13): мутанты не подтверждены.

### П2 — разбор хэнд-бэка кабана (папа-кабан, 2026-10-31; дифф не закоммичен)

Проверено по коду: `git diff HEAD` 15 файлов (+301/−57) + 5 новых модулей (`combat/actions/fighter.py`, `combat/offhand.py`,
`combat/thrown.py`, `rules/modifiers/features.py`, `rules/tactical_mind.py`). Замеры 2026-10-31: `ruff check src tests` чисто;
`make smells` 200/200; `pytest tests/unit/combat tests/unit/rules tests/unit/protocol/test_apply_resources.py` — 9 красных,
5869 зелёных (44,6 с); `tests/unit/ui/test_combat_menu.py` — 2 красных; `tests/unit/master/test_static_budget.py` зелёный
(STATIC_MAX кабан не проверял — проверено, П2 статику рассказчика не трогает). Все 11 красных — следствия решений плана
(12 — `longsword` 1d10 без щита; 8' — `prone` на Huge; бросок — `attack:spear_thrown:*` у воина с копьём; флаг `light_attack`
после кинжала; Тактический ум на 5 ур. — `d10` в `skill_check` протокола), не ошибки кода.

**Принято (кабану правок нет):**
- п. 2 — один флаг `offhand_used` на бонусный удар и на Проворство. По SRD 5.2.1 лишняя атака свойства Light — одна за ход;
  Nick лишь переносит её в действие Атака («you can make this extra attack only once per turn»). Строки плана с `nick_used`
  («Схема сейва», «Умолчания») читать как `offhand_used`.
- п. 3 — один предмет в обеих руках при `count_item >= 2`: SRD «different Light weapon» — другой предмет, два кинжала годятся;
  план «≠ оружие атаки» имел в виду это. Лёгкость оружия левой руки обеспечивает `equip` (`rules/inventory.py:121`), в
  `offhand.info` проверки нет — верно, не дублировать.
- п. 5 — GWF только ближнее двумя руками: SRD «Melee weapon that you are holding with two hands … Two-Handed or Versatile»;
  луки/арбалеты — нет. Формулировку «Умолчаний» («двуручное или универсальное двумя руками») читать с «ближнее».
  `weapon_info`: бросок универсального — обычной костью (копьё 1d6 в броске) — по SRD.
- п. 7 — Атлетика через `FeatureSource` (`request.skill`, `roll_pipeline.py:46`), не `base_adv` в `skill_check`: один источник на
  три эффекта Чемпиона, `skill_check` без ветки. «Умолчания» (`base_adv`) — снято этой правкой.
- п. 8 — `damage_log_text(…, floor)` 9-й параметр — внутреннее; smells не вырос (замер выше).
- п. 4, механика — `REJECT_WORDS` в `combat/actions/improvise.py` + лог в `PlayerController` (`game/controllers.py:37`):
  проверка размера живёт в движке при `perform` (`improvise.size_problem`), а `IMPROVISE_HINTS` (`protocol/handlers/
  combat.py:33`) — валидация spec до боя, размера там нет; тащить размер в протокол — дублировать проверку. Рассказчик
  читает лог боя — строка доходит. Строка плана «Файлы» про `IMPROVISE_HINTS["target_too_large"]` — снята. Сам текст — Р34.
- п. 1, механика — `EngineTactics.pick_attack` отсеивает `*_thrown` как `improvised*`: без этого авто-герой с копьём
  (набор воина А, решение 23) швыряет его вместо шага (`test_auto_hero_walks_to_a_distant_enemy`). Монстров правка не
  задевает (их `attacks_of` — из статблока, id без `_thrown`). Поведение авто-героя видно игроку (`engine.py:146`:
  `AutoHeroController` у героев без игрока) — развилка Р33; правка кабана — вариант (а).
- Красные тесты (11) — доебе вместе с тестами П2 (kaban.md п. 5: тесты — её зона); ожидаемое ниже в «Для доебы П2».

**Окно Владу (видимое — развилки, не умолчания):**
- Р33 — авто-герой и метание: (а) кабана — авто-герой своё оружие не бросает, идёт к врагу (как до К2; строка «Авто-герой
  оружие не бросает» в `rules-adaptation.md` остаётся); (б) бросает, когда враг не в своей зоне и метательного ≥ 2 (одно
  остаётся в руке) — в П3 вместе с `choose_turn` (Скрытая атака, `steady_aim`), `pick_attack` учит стек. Рекомендую (а)
  сейчас: П2 — про меню игрока, тактика авто-героя — П3 и BACKLOG 50; при (б) — строка в П3, кабану П2 правок нет.
- Р34 — текст отказа «сбить с ног»/«толкнуть» слишком крупную цель (лог боя, видят игрок и рассказчик). Код один
  (`target_too_large`) на оба эффекта: (а) кабана — одна строка «Слишком велик, чтобы сбить с ног или оттолкнуть: цель
  больше героя минимум на два размера» (начинается с слов решения 8', объясняет рассказчику, почему не повторять);
  (б) по эффекту — «Слишком велик, чтобы сбить с ног» / «Слишком велик, чтобы оттолкнуть» (`REJECT_WORDS` по паре
  причина+эффект или подстановка `EFFECT_WORDS`), без пояснения. Рекомендую (а): одна строка, причина видна. При (б)
  кабану: `REJECT_WORDS[(reason, effect)]`, `PlayerController` передаёт `spec.effect`; тест доебы — обе строки.
- Р35 — лог Толчка: (а) кабана — прежняя строка `falling.push` «<цель> отброшен в зону <id>» (одна на толчок монстра,
  импровизацию push и мастерство Push); (б) по плану — «отброшен: <зона>». Рекомендую (а): строка уже в игре, новой не
  нужно; «Тесты П2» про «отброшен: <зона>» читать по (а).
- Р36 — Рассечение и отрицательный модификатор (SRD-отклонение). SRD 5.2.1 Cleave: «don't add your ability modifier to that
  damage unless that modifier is negative». (а) кабана по плану — всегда 0 (`fighter.cleave:21–22`); (б) по SRD — обнулять
  только неотрицательный: `if info.damage_bonus >= 0:` перед обнулением (то же правило, что `derived.bare_off_hand:271` у
  второй руки). Рекомендую (б): SRD и одно правило с ударом второй рукой; цена — одно условие. Видно только герою с
  отрицательной Сил и секирой/алебардой (`mastery: cleave` — `greataxe`, `halberd`) — редко, но правило одно. При (б)
  кабану: условие в `cleave`; доебе — тест «Сил 8 → −1 в уроне Рассечения».
- Р37 — строка Тактического ума в логе проверки (видит игрок): (а) кабана — «…; Тактический ум: +1d10 (3) = 15 → успех,
  заряд Второго дыхания потрачен» / «… → провал, заряд не тратится»; (б) короче — «…; Тактический ум: +1d10 (3) = 15 →
  успех» / «… → провал», без слов о заряде. Рекомендую (а): игрок видит, почему пул Второго дыхания уменьшился.

**Кабану (П2, до доебы, без развилок):** правок нет — всё по развилкам выше (при Р34 = (б), Р36 = (б) — по одной правке
в `improvise.py`/`controllers.py` и `fighter.py`).

**Для доебы П2 дополнительно (красные тесты — новое ожидаемое):** `test_list_options_order.py` (3) — `attack:spear_thrown:*`
в списке после `attack:spear:*` (воин `make_fighter` с копьём; `EXIT_HERO` — бросок копья по `boss` первым);
`test_sleep_arrow.py` (3) — длинный меч без щита 1d10 (решение 12; либо дать герою щит, если тест про сон, а не про кость);
`test_mastery.py::test_nick_weapon_attacks_normally` — после атаки кинжалом `effect_ids(hero) == ["light_attack"]`
(Nick без второй руки — удара нет, цели — пусто); `test_shove_size.py::test_prone_of_a_huge_target_is_still_allowed` →
инвертировать по решению 8' (`Rejected("target_too_large")`, действие цело; имя теста сменить); `test_apply_resources.py::
test_deadly_level_5…` — герой 5 ур. с Тактическим умом добирает `d10` после провала `persuasion` (ещё один `d10` в очереди
или уровень героя без умения); `test_combat_menu.py` (2) — id `attack:*_thrown:*` в плоском списке. Плюс сценарии «Тесты П2»
плана с поправками Р33–Р37; `tests/unit/master/test_static_budget.py` — зелёный (замер 2026-10-31).

### П2 — разбор хэнд-бэка доебы (папа-кабан, 2026-10-31)

Хэнд-бэк — scratchpad `k2-p2-doeba-handback.md`, пп. 1–6. Проверено по коду (дифф не закоммичен): `combat/mastery.py:17`
`on_hit` — ветки sap/vex/topple/cleave/push, `slow` нет; `combat/zones.py:30` `range_band_ft` — 0/1/2/3+ зон = 10/30/60/120 фт;
`combat/actions/attack.py:199` `base_advantage` — `band ≤ normal → normal`, `≤ long → disadvantage`, иначе варианта нет;
эффект `kind="speed"` создаёт только морозная стрела (`attack.py:491–500`), движок его не читает (grep `"speed"` по `src` — одно
место; движение — `turn.move` зонами, `available.py:190`); `end.py:103` `settle_ground` — ветка «остался на поле боя» одна для
любого исхода ≠ победа, вызов из `conclude:153`.

**п. 3 — мастерство `slow` (дыра плана, не кабана).** Решение 1 — «все 8 мастерств», «Тесты П2» ждут «`slow` при попадании»,
но «Файлы» (`mastery.py` += `cleave`, `push`) Замедление не назвали; кабан шёл по «Файлам». До К2 Slow — «данные без
механики» (ARCHITECTURE.md:260, шапка `test_mastery.py:3`), а в модели зон скорости в футах нет: эффект `speed` морозной стрелы —
метка и строка лога. Видно игроку → Р38.

**п. 2 — дальность метания (план ошибся в арифметике, код верен).** Через одну зону — 60 фт; дротик 20/60: 60 ≤ long 60 →
помеха, варианта нет с трёх зон (120) — доеба права (`test_dagger_from_beyond_the_long_range_is_not_offered`); строку «Тесты П2»
«дротик … через одну — нет варианта» читать «через одну — помеха, через две — нет варианта». Кинжал из соседней зоны (30 фт >
normal 20) — помеха; «нормального» план не обещал (строка «бросок» — только `mode: ranged`), но следствие видно игроку: из 7
метательных SRD (`range_normal_ft` в YAML) только метательное копьё 30/120 летит в соседнюю зону без помехи, остальные 20/60 —
всегда с помехой; так уже работает «бросок подручного предмета» 20/60 (`attack.py:126`) → Р39.

**п. 1 — Pilot-тест «Всплеск действий» — принято, не писать.** Стенд TUI боя — Грей (`grey_game`, следопыт 8 ур.,
`tests/unit/ui/tui/test_tui_combat_menu.py:24, 46–51`), воина 2 ур. там нет; новый стенд ради одной строки дороже пользы.
`action_surge` — обычный пункт бесцелевого блока (rank 2); отрисовку блока Pilot-тесты уже проверяют на «Выпить: Каменная Кожа»
(`:424–434`), место строки — `build_view` (`test_combat_menu.py`, у доебы зелёный). Остаётся «Проверка руками (П2)» плана
(Арн → 300 опыта → 2 ур.) — оркестратор. Строки «Умолчаний» о Pilot-тестах и «Тесты П2» «Pilot-тест: воин 2 ур.» — снять.

**п. 4 — Р36 (б) реализована** (`combat/actions/fighter.py:23` `if info.damage_bonus >= 0: info.damage_bonus = 0`), тест
`test_cleave_keeps_a_negative_modifier` (`test_fighter_actions.py:246`) — принято, решение 49 закрыто.

**п. 5 — плут с пистолетом без владения — доебе один тест.** Данные покрыты (`test_rogue_is_not_proficient_with_firearms`,
`tests/unit/rules/test_classes_1_20.py:613`), путь без «мастерство» в `attack_parts` (`rules/derived.py:252`) —
`test_improvised_weapon.py:113`; связка ни одним тестом не проверена. Стенд готов: `shooter(…, weapon="pistol")`
(`test_fighter_actions.py:338`) с плутом вместо `fighter_at` → `bonus_parts` без «мастерство», бросок = d20 + Лов. Малый тест,
кабану правок нет.

**п. 6 — бегство через `settle_ground` напрямую — принято.** Ветка «остался на поле боя» одна для любого исхода ≠ победа
(`end.py:109–114`), полный путь `check_end → conclude → settle_ground` проверен на поражении (`test_disarm_end.py:188–193`);
бегство героя добавило бы только `status == "fled"` → `outcome "fled"` (`end.py:37–38`), ветки это не меняет. Косметика доебе:
в `test_flight_leaves_the_thrown_weapon_on_the_field` (`test_thrown.py:218`) поставить `engine.state.outcome = "fled"` перед
вызовом — сейчас тест проходит при `outcome None` («бой идёт»).

**Окно Владу (видимое — развилки):**
- Р38 — Замедление (`mastery: slow` у 7 оружий: мушкет, длинный лук, лёгкий арбалет, дубина, кнут, праща, метательное копьё).
  (а) сделать в П2 как морозную стрелу: `mastery.on_hit` при `damage > 0` → на цель `ActiveEffect(id="slow", kind="speed",
  params={"amount": -10}, expires=Expiry(kind="start_of_turn", owner=ref))` (срок — как Sap, SRD «до начала вашего следующего
  хода»); повторное попадание эффект не дублирует (SRD «не складываются»); строка «  <цель>: Замедление, скорость −10 фт» (образец —
  Ослабление, `mastery.py:30`); механики движения нет — как у морозной стрелы, строку читает рассказчик; ARCHITECTURE.md:260 и
  шапка `test_mastery.py:3` — поправить (Slow — механика К2). (б) не делать в К2: «механика позже» в ARCHITECTURE остаётся, строку
  «`slow` при попадании» из «Тесты П2» снять, пункт беклога «Замедление и эффекты `speed` в зонах» (вместе с морозной стрелой).
  Рекомендую (а): решение 1 закрывается целиком, цена — одна ветка в `on_hit`; риск smells 200/200 (`on_hit` — шестая ветка) —
  при красном кабан выносит `slow` в `mark_slow` по образцу `mark_cleave:66`. Механическая скорость в зонах — пункт беклога при
  любом варианте (касается и морозной стрелы). При (а) кабану — ветка + две правки доков; доебе — тесты в `test_mastery.py`
  (попадание мушкетом → `effect_ids(goblin) == ["slow"]`; второе попадание — один эффект; промах/0 урона — нет;
  `start_turn("hero")` снимает; мастерство не выбрано — нет) и снять `test_slow_weapon_attacks_normally:216`
  (`test_nick_and_slow_do_not_add_conditions:226` остаётся — `conditions` пусты и при (а)).
- Р39 — метание 20/60 в соседнюю зону. (а) как есть: правило дальности одно для луков, подручного броска и метания
  (`base_advantage:199`), дистанции SRD; кинжал/копьё/ручной топор/дротик в соседнюю зону — с помехой («дальность»), без помехи —
  только в своей зоне (там помеха «враг рядом», если враг в ней) → метнуть 20/60 без помехи фактически нельзя, метательное копьё
  (30/120) — нормально. (б) адаптация к зонам: для метательного оружия соседняя зона считается нормальной дальностью
  (в `base_advantage` и `base_label:218` — `steps == 1` и `info.id.endswith("_thrown")` → normal; подручный бросок — туда же или
  нет, решает Влад), через одну — помеха; строка в `rules-adaptation.md` «Метание». Рекомендую (а): SRD и одно правило без
  ветки в `base_advantage` (риск smells); бросок — выбор игрока рядом с другими пунктами, не единственный вариант. При (б)
  кабану — условие в `base_advantage`/`base_label`; доебе — `test_thrown.py` (кинжал из соседней — `normal`, дротик через одну —
  помеха, `test_javelin_*` без правок).

**Кабану (П2, после окна Владу):** при Р38 = (а) — ветка `slow` в `mastery.on_hit` + ARCHITECTURE.md:260 + строка о Замедлении в
`rules-adaptation.md` («Воин и плут 1–5 (К2)»); при Р39 = (б) — условие в `base_advantage`/`base_label`; при (а)/(а) по Р39 и (б)
по Р38 — правок кода нет.
**Доебе (П2):** тест плута с пистолетом (п. 5); `outcome = "fled"` (п. 6); при Р38 = (а) — тесты Замедления и правка
`test_mastery.py:3, 216`; при Р39 = (б) — тесты дальности. mutmut при Р38 = (а): FUNCS += `ai_dm.combat.mastery:on_hit`,
TESTS `tests/unit/combat` (каталог целиком — правило AGENTS.md, шаг 202 решение 16; время — ожидание, не проверено).

### П2 — ответы на ревью мамы и аудит свекрови (папа-кабан, 2026-10-31)

Отчёты — scratchpad `k2-p2-mama.md`, `k2-p2-svekrov.md`. Проверено по коду (дифф не закоммичен): `combat/mastery.py:59–80`
(`on_hit` ветка `slow`, `slow`), `combat/actions/features.py:8–31` (`second_wind`, `athlete_crit`), `combat/actions/fighter.py:5`
(`action_surge`), `combat/actions/attack.py:26–85` (`AttackInfo`, `weapon_info`), `:534` (`two_handed=info.grip == "two_handed"`),
`:566` (`spend_attack` — правка по маме ⚠️ 1 уже в коде: остаток Доп. атаки тратится первым), `combat/engine.py:314` (`expire` —
снятие эффекта в лог не пишет), `campaigns/drunk_dragon/heroes/grey.yaml:35` (`weapon_masteries: composite_longbow`,
`mastery: slow`). Мама ⚠️ 2–3 (тест `damage > 0` у Замедления, утверждение GWF-теста) — доебе, как сказала мама, папе разбирать нечего.

**Свекровь «к папе» — принято (кабану правок нет):**
- `AttackInfo.grip` (`two_handed` / `off_hand` / `thrown` / `None`) вместо `AttackInfo.two_handed` из «Умолчаний» — внутреннее
  (ни в логе, ни в меню не видно). Один атрибут хвата вместо трёх флагов: по нему `weapon_info:72–76` выбирает кость универсального
  и ставит GWF-тег (`:534`), `available.py:41` — глагол «Бросок», `:87` — отсев боеприпаса, `perform:591` — `thrown.drop`,
  `damage_bonus/damage_parts` — ветка второй руки (`:80, :84`). Строку «Умолчаний» «`AttackInfo.two_handed` (новый атрибут)»
  читать как `AttackInfo.grip == "two_handed"` — как `nick_used` → `offhand_used` (разбор кабана П2, п. 2).
- `test_ordinary_shot_does_not_slow` → `test_ordinary_shot_puts_no_arrow_effect` (`test_dragon_arrows.py:313`) — следствие Р38 (а),
  не подгонка: Грей держит `composite_longbow` в `weapon_masteries`, лук — `mastery: slow` (`composite_longbow.yaml:13`), обычный
  выстрел теперь ставит метку `slow`, прежнее `not active_effects` красное по решению 51. Тест о стрелах — фильтр по стрелам верен.
  Доебе одна правка: вместо белого списка `startswith("arrow_")` — чёрный `[i for i in ids if i != "slow"] == []`, как в соседнем
  `test_sleep_arrow.py:386` (`e.id != "slow"`): ловит любой лишний эффект, не только стрельный; имя оставить. В «Для доебы П2»
  правка не названа — дыра разбора, не кабана.

**Мама ⚠️ 4 (дубль Замедления от двух героев) — видно в логе боя → развилка Р40.** Сейчас `slow:71` дубль ищет по
`e.id == "slow" and e.source == ref`: два героя с Замедлением (авто-герой без игрока — `AutoHeroController`, `engine.py:146`)
дают цели две метки и две строки «<цель>: Замедление, скорость −10 фт». SRD 5.2.1 Slow: «the speed reduction doesn't exceed
10 feet», срок каждого — «until the start of your next turn». Механики скорости нет (разбор доебы П2, п. 3), снятие метки в лог
не пишется (`expire:314`) — из разницы вариантов игрок видит только число строк.

**Свекровь «к пользователю» — три строки лога без решения Влада → развилки Р41–Р42.** Образцы в коде: действие героя —
«<герой>: рывок» / «<герой>: отход» / «<герой>: мультиатака» (`standard.py:13, 24`, `multiattack.py:10`), «<герой>: Второе дыхание
+N, …» (`features.py:18`); пояснение к механике — отступ в два пробела: «  <цель>: Ослабление, следующая атака с помехой»
(`mastery.py:30`), «  <цель> сбит с ног», «  <цель> горит: ещё 1d6 огнём в начале хода» (`attack.py:490`). «Отход» ставит тот же
`turn.disengaged`, но строки «не провоцирует» не пишет — игрок сам выбрал пункт; Тактический сдвиг и Выдающийся атлет
срабатывают сами, без строки игрок и рассказчик не узнают, почему атаки по возможности не было (`opportunity.py:19`).
«Тесты П2» (`:427`) ждут «строку „Всплеск действий“ после атаки» — строка планом обещана, текст не задан. Тесты на тексты уже
есть: `test_fighter_actions.py:113` («Арн: Всплеск действий»), `:151` («Тактический сдвиг» в логе).

**Окно Владу (видимое — развилки):**
- Р40 — Замедление от двух героев по одной цели (`mastery.py:71`). (а) как сейчас — метка на каждого героя, строка на каждого:
  две строки «Замедление, скорость −10 фт», рассказчик может прочесть как −20; сроки по SRD. (б) мамы — одна метка на цель
  (`any(e.id == "slow" …)` без `source`): второй герой строки не пишет, метка снимается в начале хода первого попавшего (для
  второго — чуть раньше SRD; невидимо, пока скорость — только строка). (в) метки по источнику, строка — только при первой
  (`had = any(e.id == "slow" …)` до добавления): сроки по SRD и одна строка; цена — второе условие в `slow` при smells 200/200.
  Рекомендую (б): правило SRD одно — «не больше 10 фт», и строка одна; разница в сроках невидима; пересмотреть вместе с
  морозной стрелой, когда появится механика скорости (пункт беклога «Замедление и эффекты `speed` в зонах» из разбора доебы
  П2 — в BACKLOG.md ещё не заведён, grep 2026-10-31; завести при закрытии). При (б) кабану — убрать `and e.source == ref`;
  доебе — тест: два воина с лёгкими арбалетами и `slow` в `weapon_masteries` (`make_engine(heroes=[…, …])`, образец
  `test_dragon_arrows.py:91`) бьют одну цель → `len(slow_effects) == 1`, одна строка «Замедление»; `test_slow_does_not_stack:275`
  и `test_slow_logs_once_when_not_stacking:280` остаются зелёными. При (в) — то же плюс `len == 2` меток.
- Р41 — строка Всплеска действий в логе боя (`fighter.py:9`). (а) кабана — «<герой>: Всплеск действий» (образец «<герой>: рывок»,
  «<герой>: отход»); (б) с пояснением — «<герой>: Всплеск действий — ещё одно действие в этот ход»; (в) без строки — только пункт
  меню исчезает. Рекомендую (а): строка в стиле соседних действий, имя умения — из глоссария (`glossary.md:201`), пояснять
  нечего — следующая строка лога и так атака; тест `:113` уже на этот текст.
- Р42 — строки Тактического сдвига и Выдающегося атлета (`features.py:21, 31`). (а) кабана — «  Тактический сдвиг: ход не
  провоцирует атаки» / «  Выдающийся атлет: ход не провоцирует атаки» (отступ-пояснение, как Ослабление); (б) короче — «  Тактический
  сдвиг» / «  Выдающийся атлет» без пояснения; (в) без строк — как у «отхода» (`standard.py:24`), только `turn.disengaged`.
  Рекомендую (а): умения срабатывают сами, и игроку с рассказчиком нужно знать, почему уход из зоны не вызвал атаки по
  возможности, — тот же довод, что Р37 (а) (решение 50: «заряд Второго дыхания потрачен»); текст — слова `rules-adaptation.md:274`
  («ход не провоцирует атаки по возможности») в короткой форме. При (б) кабану — два литерала; при (в) — снять строки и тест `:151`.

**Кабану (П2, после окна Владу):** при Р40 = (б) — одно условие в `mastery.slow`; при Р41/Р42 ≠ (а) — литералы в `fighter.py:9`,
`features.py:21, 31`; при (б)/(а)/(а) — одна правка. **Доебе (П2):** мама ⚠️ 2–3; `test_dragon_arrows.py:313` — фильтр `!= "slow"`;
при Р40 = (б) — тест двух героев. mutmut: `ai_dm.combat.mastery:slow` — уже внутри `on_hit` в списке разбора доебы П2
(FUNCS += `ai_dm.combat.mastery:slow`, TESTS `tests/unit/combat`).

### П2 — исправлено по ревью мамы и аудиту свекрови (кабан, доеба, 2026-10-31)

- Кабан: мама ⚠️ 1 — `spend_attack` тратит `attacks_left` первым (воин 5 ур. + Всплеск = 4 атаки); `tactical_mind.apply`
  вызывается только из `skill_check` с СЛ — правок нет; решение 53 — `mastery.slow` без `source`.
- Доеба: тест «атака → Всплеск → ещё три»; Замедление при 0 урона (иммунитет); GWF — явная строка лога и HP; два героя —
  одна метка (решение 53); `test_dragon_arrows.py:313` — фильтр `!= "slow"`. BACKLOG 237 заведён.
- Вне партии: `scripts/migrate_dusk_vibe.py` (c92ae96 дежурного, smells 201) — удалён и возвращён по окну Влада «Вернуть,
  сначала прогнать»; удаление — после миграции мира Владом.

### П3 — разбор хэнд-бэка кабана (папа-кабан, 2026-10-31; дифф П2+П3 не закоммичен)

Хэнд-бэк — scratchpad `k2-p3-kaban-handback.md`, пп. 1–9. Проверено по коду: `git diff HEAD` 33 файла (+1179/−156), новые
`combat/sneak.py` (69 строк), `combat/actions/rogue.py` (124); читаны оба модуля и диффы `attack.py`, `available.py`,
`standard.py`, `stealth.py`, `move.py`, `engine.py`, `controllers.py`, `combat_menu.py`, `roll_pipeline.py`,
`test_sim_grid_files.py`, `sim_grid_baseline.yaml`, BACKLOG/ARCHITECTURE/rules-adaptation, карточки done. Числа сетки
(goblins3 плут 5 ур. 17.0 → 89.5 %, cellar 0.0 → 11.5 %) — по диффу `sim_grid_baseline.yaml`. Тесты П3 — доебе (kaban.md п. 5).

**п. 1 — BACKLOG 233: в К2 не закрывать, оставить в беклоге (пересмотр П1 п. 8).** Сдвиг калибровки случился в П1 и снят
обычной подстройкой (3010 → 3045 → 3040, `memory_script.py:30–33`); П3 реестр и промпт не трогает, cap стабилен,
`test_stage4_memory` зелёный. Оба пути пункта — устройство сценария, не бой: `test_stage4_memory` держит обе встречные границы
сам (`test_every_stage_fires_somewhere:159` — ступень chapters сработала; `test_estimate_within_budget…:99` — нет
переполнения), развод с `test_zh0_npc_memory` (`:101`, тот же `MEMORY_CONTEXT_CAP` через `play_memory`) окно не расширит;
«cap из прогона» (замер пика динамики, подбор запаса) — отдельный малый шаг тестовой инфраструктуры. По правилу 9 —
оптимизация, не регресс. Кабану — ничего. При закрытии (архитектор): текст 233 «делать при следующем сдвиге (К2)» → «К2:
сдвиг снят руками (3040); следующий — К3 (жрец: заклинания, лист)», `updated`; строка ROADMAP К2 (`:162`) «233 … при
сдвиге» — снять, 233 → строка К3 «при касании». Карточки done по 233 не будет.

**Принято (кабану правок нет):**
- п. 2 — `sneak.damage(engine, ref, target_ref, info, result)` без `crit`: крит из `result.outcome` — внутреннее.
- п. 3 — `rogue.cunning_action` нет: пункты строит `available.cunning_action_options:565`, обработчики — `standard.dash:18`,
  `standard.disengage`, `stealth.hide:30` через общий `standard.spend_action:9` (`params["bonus"]`, как Проворное бегство).
  Список mutmut П3 — ниже, `rogue:cunning_action` снят.
- п. 4 — отдельный вид `hide_bonus` (`PERFORM["hide_bonus"] = stealth.hide`, `engine.py:51`): обычное «Спрятаться» (`kind="hide"`)
  не в `CATEGORY_BY_KIND` и уезжает в «Ещё…» (`test_help_hide_items_flee_pickup_are_not_rows_but_in_more:624`), бонусное — в
  бесцелевом блоке. Ранги: `dash_bonus`/`disengage_bonus`/`hide_bonus` — 3 (вид общий с действиями), `steady_aim`/`action_surge`
  — 2; план говорил «rank 2» для всех — разница только в порядке вытеснения при > 10 строк, внутреннее.
- п. 5 — Верный прицел: флаг `moved` (`rogue.mark_moved:34` из `move.perform:31`, только у героев с `steady_aim`) +
  `turn.move == 1` (`can_aim:40`) — после Рывка пункта нет. SRD: Рывок не перемещение, но Верный прицел обнуляет скорость —
  Рывок перед ним бесполезен; адаптация записана кабаном в `rules-adaptation.md` («не делал Рывок»).
- п. 8 — авто-герой (`controllers.py:221–255`): `pick_own` — Второе дыхание → Верный прицел при враге в своей зоне →
  стабилизация/Истребитель → подбор; Всплеск — когда тактика вернула `end_turn` и есть боеспособный враг (`surge_options` и так
  даётся только при потраченном действии, `available.py:613`); Хитрый удар и бросок не выбирает — по «Умолчаниям» и BACKLOG 50
  (пометка «плут ✅ К2» верна: Скрытая атака в сетке работает сама).
- Невероятное уклонение (`rogue.uncanny_dodge:111`) делит и доп. кости преимущества (`info.advantage_dice` — только у монстров,
  `attack.py:143`) — ближе к SRD «halve the attack's damage», чем строка «Адаптаций» в «Суть»; стрелы и `special_damage` идут
  после `engine.damage` и не делятся. Строку «Адаптаций» читать как `rules-adaptation.md:222–224` кабана: делится бросок урона
  самой атаки, эффекты после попадания — нет.
- Документы: ARCHITECTURE «К2», два раздела `rules-adaptation.md`, BACKLOG 237/238 и пометки 11/31/50 — верны.

**Вернуть кабану (П3, до доебы):**
1. Карточки done 48/57/66 (п. 9) — RULES «docs/done/»: перенос «в том же коммите, что ✅ в ROADMAP»; ✅ — при закрытии после
   cov и живого прогона, коммит П3 — раньше. Вернуть тела 48/57/66 в BACKLOG.md (из `git show HEAD:docs/BACKLOG.md`) со
   `status: done`, `updated: 2026-10-31` — «проездом» по RULES; три файла `docs/done/0{48,57,66}-*.md` — в scratchpad до
   закрытия (вернутся как есть, тексты «Закрыто» верны). Пометки 11/31/50 и пункты 237/238 остаются в П3.
2. `tests/unit/devtools/test_sim_grid_files.py:70–82` — константа `GOBLINS3_K7K` и тест `test_repo_baseline_goblins3_is_unchanged`
   после пересчёта лгут (комментарий «К7д: … goblins3 прежняя»): `GOBLINS3_K2`, комментарий «К2: линия после Скрытой атаки и
   авто-героя», имя `test_repo_baseline_goblins3_is_the_k2_line`.
3. По развилкам ниже: при Р43 = (б) — `sneak.eligible:33` `info.kind != "ranged"` → `weapon.kind != "ranged"` и строка
   `rules-adaptation.md:210`; при Р44 = (б) — `strike_effect` оставляет флаг `cunning_strike_pending`, новый
   `rogue.resolve_pending(engine, ref, target_ref, dealt)` одной строкой в `attack` после `special_damage` (`attack.py:547`);
   при Р45 = (б) — строка лога в `strike_effect:84`.

**Окно Владу (видимое — развилки):**
- Р43 — Скрытая атака броском нефехтовального метательного (метательное копьё, ручной топор, лёгкий молот, копьё, трезубец —
  `kind: melee` + `thrown`). Сейчас `eligible:33` считает бросок дальнобойной атакой (`info.kind == "ranged"`) → Скрытая атака
  есть; SRD 5.2.1 Sneak Attack: «The attack must use a Finesse or a Ranged weapon» — метательное копьё остаётся Melee weapon,
  Скрытой атаки нет; кинжал и дротик — Finesse, не затронуты. (а) кабана — любой бросок даёт Скрытую атаку (адаптация,
  `rules-adaptation.md:210` «бросок метательного — дальнобойная атака»); (б) по SRD — `weapon.kind == "ranged"` или `finesse`.
  Рекомендую (б): отклонение без причины зон; цена — одно слово в условии и строка документа.
- Р44 — порядок строк Хитрого удара в логе (`sneak.damage:67` → `rogue.resolve` до `engine.damage`, `attack.py:545`). Сейчас:
  «Урон…», «Скрытая атака +2d6…», «  Хитрый удар (Сбить с ног): СЛ 15», спасбросок, «  Гоблин сбит с ног», затем строка HP
  цели; при смертельном уроне цель «сбита с ног»/«отравлена», потом мертва. Topple (`mastery.on_hit:19`) идёт после урона и
  мёртвую цель пропускает. (а) как есть; (б) эффект после урона, как Topple: `resolve_pending` после `special_damage`, на мёртвой
  цели и при `dealt.final == 0` — ничего (SRD Trip: «If the attack hits and deals damage»). Рекомендую (б): один порядок с
  Topple, по SRD, рассказчик не читает «сбит с ног» о трупе. «Скрытая атака +Nd6» остаётся до HP — часть урона, как Убийца
  колоссов.
- Р45 — «Сбить с ног» по цели крупнее Large (`strike_effect:83–85`): сейчас молча — эффекта нет, кости целы, выбор остаётся;
  игрок выбрал пункт и не видит, почему ничего не случилось. (а) молча; (б) строка-пояснение «  Хитрый удар (Сбить с ног):
  цель слишком велика, кость не потрачена» (образец — отказ импровизации, решение 24). Рекомендую (б): довод Р42 (а)
  (решение 55) — сработало не так, как ждал игрок, причина в логе.

**Для доебы П3:** сценарии «Тесты П3» с поправками: Хитрое действие — id `dash_bonus`/`disengage_bonus`/`hide_bonus`,
`hide_bonus` тратит `turn.bonus`, действие цело, обычный `hide` остаётся в «Ещё…»; Верный прицел — после Рывка пункта нет,
в логе атаки «[верный прицел]» (`SOURCE_WORDS`), второй раз за ход — нет; авто-герой — `pick_own` с `steady_aim` при враге в
зоне, `action_surge` только после `end_turn` тактики; Невероятное уклонение — нечётный урон 7 → 3, в чужой ход при целой
реакции; при Р43 = (б) — плут с метательным копьём и союзником у цели: Скрытой атаки нет, с кинжалом — есть; при Р44 = (б) —
порядок строк, убитая цель без спасброска, урон 0 (иммунитет) — без эффекта; при Р45 = (б) — строка про размер.
`test_sim_grid_files.py` — новая константа. mutmut П3 (функции — grep 2026-10-31): `FUNCS="ai_dm.combat.sneak:eligible
ai_dm.combat.sneak:damage ai_dm.combat.sneak:ally_near ai_dm.combat.sneak:dice_count ai_dm.combat.sneak:reset
ai_dm.combat.actions.rogue:can_aim ai_dm.combat.actions.rogue:mark_moved ai_dm.combat.actions.rogue:steady_aim
ai_dm.combat.actions.rogue:cunning_strike ai_dm.combat.actions.rogue:strike_effect ai_dm.combat.actions.rogue:resolve
ai_dm.combat.actions.rogue:uncanny_dodge ai_dm.combat.available:cunning_action_options ai_dm.combat.available:steady_aim_options
ai_dm.combat.available:strike_options ai_dm.combat.actions.standard:spend_action ai_dm.combat.actions.standard:dash
ai_dm.combat.stealth:hide ai_dm.combat.engine:CombatEngine.start_turn ai_dm.combat.controllers:AutoHeroController.choose_turn
ai_dm.combat.controllers:AutoHeroController.pick_own ai_dm.combat.controllers:AutoHeroController.enemy_here"
TESTS="tests/unit/combat"` (каталог целиком — AGENTS.md, шаг 202 реш. 16); `ui/combat_menu` — `free_block`, `group_rows`,
`TESTS="tests/unit/ui"` как в П2; при Р44 = (б) FUNCS += `ai_dm.combat.actions.rogue:resolve_pending` (новая). Решение 56: cov
и mutmut — полным прогоном в конце П3.

### П3 — ответы на ревью мамы и аудит свекрови (папа-кабан, 2026-10-31)

Отчёты — scratchpad `k2-p3-mama.md`, `k2-p3-svekrov.md`. Проверено по коду: `rogue.can_aim:42–49`, `mark_moved:36`,
`standard.dash:20` (`turn.move += 1`), `move.py:38`, `rogue.resolve_pending:95–103`, `resolve:109–111`, `sneak.reset:9`,
`engine.py:391`; тесты `test_rogue.py` по grep.

**Свекровь «к пользователю» — Верный прицел после Рывка → развилка Р46.** Мой п. 5 разбора П3 принял видимое поведение
сам; по правилу 4 это развилка. Код: `can_aim:49` `turn.move == 1`; Рывок `dash:20` делает `move == 2` → пункта нет, пока
плут не сходил (а сходил — флаг `moved`, пункта нет и по SRD). Разница только в одном случае: Рывок без перемещения.

**Мама ⚠️ 1 — «Отступить» на добитой цели и при уроне 0 → развилка Р47.** `resolve_pending:102` — общее условие Р44
(решение 58) для трёх эффектов; Р44 ставился про эффекты на цели (trip/poison), Withdraw — на плуте. Отступлением кабана
не считаю: он сделал по решению 58 буквально.

**Мама ⚠️ 2 — флаг «Сбить с ног» по Huge висит до конца хода:** проверено мамой, по SRD и решению 59, правок нет.

**Окно Владу (видимое — развилки):**
- Р46 — Верный прицел после Рывка, без перемещения (`rogue.can_aim:49`). SRD 5.2.1 Steady Aim: «only if you haven't moved during
  this turn», Рывок перемещением не считается. Что видит игрок: (а) как сейчас — после Рывка пункта «Верный прицел» в меню нет
  (адаптация, строка `rules-adaptation.md` «не делал Рывок»); (б) по SRD — пункт есть, пока плут не сходил по зонам; выбор
  обнуляет скорость, Рывок пропадает. Пользы у (б) нет: Рывок бонусом (Хитрое действие) и Верный прицел — оба бонусное
  действие, вместе невозможны; Рывок действием — после него атаковать нечем, а преимущество живёт до конца хода. Рекомендую
  (а): в меню не появляется пункт, который только тратит бонусное действие; записать решением, строку `rules-adaptation.md`
  оставить.
- Р47 — «Отступить» при убитой цели или уроне 0 (`rogue.resolve_pending:102`). SRD 5.2.1 Cunning Strike — «when you deal Sneak
  Attack damage», Withdraw — «following the attack, you move… without provoking». Что видит игрок: (а) как сейчас — плут
  добил гоблина с «Отступить», строки «Хитрый удар (Отступить): ход не провоцирует атаки» нет, уход из зоны провоцирует
  атаки остальных, кость Хитрого удара потрачена; (б) «Отступить» срабатывает и на убитой цели, при уроне 0 — нет (урона
  Скрытой атаки не было); Сбить с ног/Отравить — по решению 58; (в) «Отступить» — всегда при сработавшей Скрытой атаке, даже при
  уроне 0 (иммунитет). Рекомендую (б): по SRD (эффект на плуте, условие — нанесён урон), «добить и уйти» — главный сценарий
  этого эффекта; (в) — отклонение от «deal damage».

**Кабану (П3, после окна Владу):** при Р46 = (б) — убрать `and turn.move == 1` (`can_aim:49`), строку «не делал Рывок» в
`rules-adaptation.md`; при Р46 = (а) — ничего. При Р47 = (б) — в `resolve_pending:102` для `effect == "withdraw"` условие
только `dealt.final > 0`; при (в) — без условия; строка `rules-adaptation.md:294–297` про «Отступить» на добитой цели.

**Доебе (П3):** тест мамы ⚠️ 3 — Скрытая атака в чужой ход: плут бьёт со Скрытой атакой в свой ход → `start_turn(GOBLIN)`
(`engine.py:391` `sneak.reset`) → атака плута по возможности → кости Скрытой атаки есть (сейчас
`test_sneak_attack_is_available_again_in_the_next_turn:155` ставит `action = True` руками). При Р46 = (б) — Рывок без
перемещения → пункт «Верный прицел» есть. При Р47 = (б) — «Отступить» на добитой цели → `turn.disengaged is True` и строка
в логе; урон 0 → нет; при (в) — оба `True`. mutmut — список П3 без изменений (`rogue:can_aim`, `rogue:resolve_pending` уже в нём).

### П3 — исправлено по ревью мамы и аудиту свекрови (кабан, доеба, 2026-10-31)

- Р46 (а), решение 60 Влада: код не менялся, отступление записано в `rules-adaptation.md`; тест — уже есть
  `test_no_steady_aim_after_a_dash`.
- Р47 (б), решение 61 Влада: `rogue.resolve_pending` — «Отступить» при уроне > 0 без проверки живости цели; trip/poison —
  как было; блок «Хитрый удар» в `rules-adaptation.md` переписан.
- Доеба: `test_sneak_attack_in_another_creatures_turn`, `test_withdraw_works_on_a_finished_target`,
  `test_withdraw_does_nothing_when_the_damage_is_zero`; test_rogue.py 85 passed, ruff чисто; smells 201 (тот же).
- Второе замечание мамы (флаг «Сбить с ног» по Huge-цели) — без правок, по решению 59 (папа).

## Открыто: стенд / аналитик

П1 (хэнд-бэк доебы 2026-10-30) — не проверено руками: шаг мастерства воина (36 вариантов) в TUI-мастере; окно
торговли с 36 оружиями листается; `/sheet` плута 5 ур. (`abilities_lines`, автотеста нет); правка `narrator_rules.md`
(экспертиза, без «бонус мастерства удвоен») тестом не проверена; golden `k0_sheet_data_v4_dragon.json` доеба не гонял.

П2/П3 (хэнд-бэки доебы 2026-10-31) — не проверено руками: воин 2 ур. в TUI (Всплеск после атаки, бросок копья,
«подобрал»), Pilot-теста нет; плут Томас (`u1_live`, копия) → 2 ур., Хитрое действие и Скрытая атака в TUI; Pilot на
«Хитрый удар ▸» нет; `test_schema_fingerprint` на v14 — в полном прогоне.

## Открытые вопросы

1. Р46 — Верный прицел после Рывка без перемещения (`rogue.py:49`): (а) пункта нет, как сейчас; (б) по SRD — пункт есть.
   Рекомендую (а) — пункт без пользы; разблокирует: правку/закрытие П3; решает: Влад. Подробно — «П3 — ответы на ревью мамы и
   аудит свекрови».
2. Р47 — «Отступить» Хитрого удара на добитой цели / при уроне 0 (`rogue.py:102`): (а) как сейчас — не срабатывает; (б) на
   добитой срабатывает, при уроне 0 — нет; (в) всегда. Рекомендую (б) — по SRD, эффект на плуте; разблокирует: правку
   `resolve_pending` и тест доебы; решает: Влад.

Закрыто: Р1–Р28 закрыты решениями 11–38 (2026-10-30); Р29–Р32 — окна после П1, Р33–Р37 — решения 46–50; Р38–Р39 (Замедление,
дальность метания) — решения 51–52; Р40–Р42 (дубль Замедления от двух героев, строки лога Всплеска, Тактического сдвига и
Выдающегося атлета) — решения 53–55; Р43–Р45 (Скрытая атака броском нефехтовального, порядок строк Хитрого удара,
строка о слишком крупной цели) — окно после разбора хэнд-бэка кабана П3 (см. «Правки по ревью»). BACKLOG 233 в К2 не
закрывается (П3, п. 1). Открытые вопросы шага БП (БП-Р1…Р3) — docs/plan-bp.md.

## Смета (кабан-тесть, режим 1)

**Что проверено:** план К2 после решений 30–38 (огнестрел, боеприпасы вынесены в БП), 2026-10-30. Масштаб — против
шага 111 («Итог» plan-111: 1 партия, 8 файлов, +590 строк, 9,26 $): К2 ≈ 80–90 файлов (28 оружий, ≈ 20 умений, 7 новых
модулей, ≈ 40 изменяемых функций), ≈ 4000–6000 строк в 3 партиях — на партию ×3–4 по кабану/ревью. Предыдущая смета
(≈ 33–44 $, agents.md) — до решений 30–38. Модели: `grep -H '^model:'` — kaban sonnet, kaban-doeba sonnet, mama-kaban
opus, kaban-svekrov opus, kaban-test opus, kaban-dekart fable (по ценам Opus); свой запуск Opus 5.5.

| Статья | Сейчас ($/мес) | Допущения | Дешевле | Экономия | Что теряем |
|---|---|---|---|---|---|
| Платные сервисы/API игры | 0 | шаг не добавляет подписок/хостинга; лист рассказчика растёт на строку экспертизы — вход рассказчика ≈ +0 | — | — | — |
| Прогон цепочки К2 (разово) | ≈ 38–52 $ на шаг | см. таблицы ниже | разбор выживших mutmut — haiku вместо sonnet (AGENTS.md п. 7) | ≈ 0,5 $ | ничего заметного |
| то же | | | `/compact` оркестратора между партиями (по CLAUDE.md) — кэш-чтение 190 K+ на вызов | ≈ 3–5 $ | ничего, если состояние записано в документ |
| то же | | | Декарт только сводным вызовом (1 вместо 4) | ≈ 3,5 $ | разбор по партиям; не рекомендую — решение family.md |

| Партия | Время |
|---|---|
| груминг + аудит + план + 3 редакции (общие с БП) | прошло |
| П1 данные и прогрессия: kaban / doeba / мама / свекровь | 60–100 / 15–25 / 5–10 / 5–10 мин |
| П2 бой воина: то же | 80–120 / 20–30 / 8–12 / 8–12 мин |
| П3 бой плута, авто-герой, сетка: то же | 70–110 / 20–30 / 8–12 / 8–12 мин |
| cov + smells + dead + mutmut (×3 партии, combat + ui отдельно, фоном) | 3 × (15 + 60–120) мин |
| проверка руками П2/П3 + живой прогон Влада | 30–45 мин + время Влада |
| закрытие (папа) + тесть р.3 + Декарт (3 партии + 1 сводный = 4 вызова) | 5 + 3 + 10–15 мин |
| итого | ≈ 6–9 ч агентов + 4–7 ч фоном |

| Роль | Модель | Токены | $ (тариф metrics.py от 2026-10-25) |
|---|---|---|---|
| уже прошло (папа a637bc2c…/aaf00f10…, свинопас a3c612ae…, свекровь a7e7ff02… — общие на К2 и БП) | fable / opus / opus | 11,05 M | **10,34** |
| orchestrator | opus | 25–35 M | 11–15 |
| kaban (3 партии) | sonnet | 25–35 M | 10–14 |
| kaban-doeba (3 + разбор mutmut) | sonnet | 4–6 M | 2–3 |
| mama-kaban (3) | opus | 3–4 M | 2,5–3,5 |
| kaban-svekrov (3) | opus | 3–4 M | 2,5–3,5 |
| papa-kaban (закрытие, отступления) | fable | 1 M | 1–1,5 |
| kaban-test (р.3) | opus | 0,4 M | 0,6 |
| kaban-dekart (4 вызова) | fable | — | ≈ 5 (≈ 1,25 $/вызов: факт Ш27 2,50 $, `plan-sh32.md` «Итог», допущение 2 вызова) |
| **итого вперёд** | | ≈ 62–86 M | **≈ 35–46** |

**Итого:** прогон К2 ≈ 35–46 $ вперёд (вместе с прошедшим ≥ 45 $; прошедшее общее с БП); $/мес — 0. Рост против
прежних 33–44 $ — огнестрел и 6 новых оружий с `ammo`, мелочь; боеприпасы ушли в БП (≈ 12–16 $ там).
**Вердикт:** ок по бабкам (бюджет не ориентир — решение 2026-10-18). Оговорка: риск отпечатка (v15) и smells 200/200 —
лишний круг ревью ≈ +3–5 $ на партию.

## Итог

**Источник токенов:** `metrics.py ~/.claude/projects/-Users-vladislavahtamov-projects-ai-dm/fe4a9168-ff5e-4840-b211-8ca745a8a148.jsonl`
(сессия только К2, `--from` не нужен); **цены:** тариф metrics.py от 2026-10-25,
https://platform.claude.com/docs/en/about-claude/pricing (fable — по ценам Opus); страницу 2026-10-31 не сверял.

Время — «минут работы» из metrics.py (сумма сегментов), местное UTC+5.

| Партия | Смета | Факт |
|---|---|---|
| П1 kaban / doeba / мама / свекровь | 60–100 / 15–25 / 5–10 / 5–10 мин | 66 / 13 / 8 / 6 мин; интервал 30.10 19:41 → 31.10 16:14, в т. ч. ночной простой и mutmut |
| П2 то же | 80–120 / 20–30 / 8–12 / 8–12 мин | 26 (+1 мини dusk_vibe) / 46 / 4 / 2 мин — доеба дольше: Замедление (решение 51) отдельным заходом |
| П3 то же | 70–110 / 20–30 / 8–12 / 8–12 мин | 29 / 8 / 4 / 2 мин |
| cov + mutmut | 3 × (15 + 60–120) мин | только П1: cov 13,5 + 25 мин, mutmut 1 ч (остановлен) + 3 ч 18 мин + 4 ч 41 мин (повтор); П2/П3 — пропущено (решения 56, 62; BACKLOG 239) |
| проверка руками + живой прогон | 30–45 мин | не было до итога (см. «Открыто: стенд / аналитик») |
| закрытие (папа) + тесть + Декарт | 5 + 3 + 10–15 мин | папа 1,5 мин; тесть идёт; Декарт — после итога |

| Роль | Модель | Токены | $ |
|---|---|---|---|
| orchestrator (на момент подсчёта 19:49) | opus | 34,88 M | 15,25 |
| kaban (4 запуска, вкл. мини dusk_vibe 0,21 $) | sonnet | 76,95 M | 20,05 |
| kaban-doeba (7) | sonnet | 22,76 M | 7,06 |
| mama-kaban (5) | opus | 6,78 M | 8,02 |
| kaban-svekrov (4) | opus | 4,06 M | 4,92 |
| papa-kaban (8) | fable / opus | 6,94 M | 8,21 |
| kaban-test (на момент подсчёта 19:49) | opus | 0,16 M | 0,29 |
| kaban-dekart | fable | — | ещё не запускался |
| **итого сессии** | | 152,5 M | **63,80** |

**Итого:** смета ≈ 35–46 $ вперёд (+ 10,34 $ прошедшего, общего с БП) → факт 63,80 $ в сессии; превышение — kaban
(20 $ против 10–14: кэш-чтение 72,7 M, пик контекста 354 K), doeba (7 $ против 2–3: 7 запусков, Замедление и два
разбора mutmut), мама (8 $ против 2,5–3,5: 4 круга по П3, 7 кругов по П1). Время агентов ≈ 4 ч работы против 6–9 ч сметы;
фон — только mutmut П1 (≈ 9 ч), cov/mutmut П2+П3 не снимались, полный pytest не прогнан (решение 63).
Сетка sim (П3): goblins3 плут 5 ур. 17.0 → 89.5, плут 3 ур. 1.5 → 37.5; cellar плут 5 ур. 0.0 → 11.5.
smells 201 при пороге 200 — от чужого коммита c92ae96 (`scripts/migrate_dusk_vibe.py`), не от К2.
Коммиты: П1 — a71303c; П2+П3 — в дереве, коммит после итога.
Churn после ревью: код +1482/−458, тесты +3006/−260 (203 % от строк до T0)
Разбор — кабан Декарта.
