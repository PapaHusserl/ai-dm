# П7: черновики ИИ для пака «Пьяный Дракон» (на утверждение проектировщику)

Решение 4а (grooming): мотивы, триггеры, opportunity NPC и фракций, pleased_by/angered_by/rivals
богов -- черновик ИИ, проектировщик правит. В паке `campaigns/drunk_dragon/` каждое такое поле
помечено комментарием `# draft`. Файл собран из `devtools/dragon_drafts.yaml` (тот же источник,
что у конвертера `devtools/import_dragon.py`). Правка -- в YAML пака руками (и в
`dragon_drafts.yaml`, если конвертер будет запускаться снова).

Всего черновых полей: 50.

Не draft (утверждено): шкалы тона (3а, G6) и всё, что перенесено из источника как есть.
Не заполнено намеренно: `servants` богов (слуг-охотников в источнике нет), `means` богов,
новые `key: true` (10 ключевых NPC источника остаются как есть, решение Q1).
Ссылки на источник: `ch1` = `saves/drunk_dragon/_import/source/chapter1_gemini_web.txt`,
`ch2` = `chapter2_agy.txt` (число после двоеточия -- номер строки); `world.json`, `session.json` --
`saves/drunk_dragon/slots/manual-import/`.

## NPC

### ethan

- **motive**
  ```yaml
  motive: Выследить и выбить гончих Топкого болота, чтобы деревне было безопасно
  ```
  Почему: Мотива в источнике нет. Итан -- охотник, сын Ольгерда, погиб у логова гончих; мотив выведен из роли.
  Источник: world.json npcs.ethan.relations_text; ch1 -- сюжет Ольгерда и Итана (Чёртов Затон)

### bloodfang

- **motive**
  ```yaml
  motive: Охранять логово у Чёртова Затона и кормить стаю
  ```
  Почему: Мотива в источнике нет. Вожак (альфа) болотных гончих; мотив выведен из роли.
  Источник: world.json npcs.bloodfang.means

### second_hierarch

- **motive**
  ```yaml
  motive: Доставить синий кристалл Ордена на Гадючий Остров и дальше по цепочке культа
  ```
  Почему: Мотива в источнике нет. Ритуалист вёл обоз с синим кристаллом (Ключом); мотив выведен из этого.
  Источник: world.json npcs.second_hierarch.means; ch1 -- обоз на Гадючьем Острове

### third_hierarch

- **motive**
  ```yaml
  motive: Хранить Второе Святилище и архив Ордена на Мёртвом Кургане
  ```
  Почему: Мотива в источнике нет. Хранитель Второго Святилища; архив, которым культ шантажировал Варена, лежал там же.
  Источник: world.json npcs.third_hierarch.means; memory.json chapters.ch1 (Мёртвый Курган)

### warlock_viper

- **motive**
  ```yaml
  motive: Удержать заслон на Гадючьем Острове и не пропустить чужих к обозу
  ```
  Почему: Мотива в источнике нет. Командир заслона на Гадючьем Острове; мотив выведен из роли.
  Источник: world.json npcs.warlock_viper.means; locations.viper_island

### abbey_tracker

- **motive**
  ```yaml
  motive: Выследить чужаков гончими и защитить Аббатство
  ```
  Почему: Мотива в источнике нет. Командир загонщиков с гончими; мотив выведен из роли.
  Источник: world.json npcs.abbey_tracker.means

### abbey_captain

- **motive**
  ```yaml
  motive: Удержать Аббатство Алого Тумана, пока Иерарх ведёт ритуал
  ```
  Почему: Мотива в источнике нет. Командир гарнизона Аббатства; Верховный Иерарх вёл в нём ритуал.
  Источник: world.json npcs.abbey_captain.means, npcs.supreme_hierarch.means

### plague_brute

- **motive**
  ```yaml
  motive: Охранять пленных в казематах Ратуши по воле Братства Мора
  ```
  Почему: Мотива в источнике нет. Мутировавший старший тюремщик; мотив выведен из роли (тюремщик).
  Источник: world.json npcs.plague_brute.means; ch2 -- бой в Ратуше

### sickle_executioner

- **motive**
  ```yaml
  motive: Освободить Ольбрехта и посеять панику в Ратуше
  ```
  Почему: Мотива в источнике нет. Культист в костяной маске среди диверсантов, освободивших Ольбрехта в Ратуше.
  Источник: IMPORT_NOTES, противоречие «Ольбрехт» (шаги 126-130); world.json npcs.sickle_executioner

### nazir

- **opportunity**
  ```yaml
  opportunity:
  - id: ritual_at_dawn
    if:
      all:
      - time_after: 23781600
      - npc_status:
          id: nazir
          is: alive
    then: Начинает ритуал у саркофага над трещиной -- вскрыть Могильник кровавой жертвой и пробудить Мор-Владыку
    once: true
    key: true
  - id: answers_black_spring_alarm
    if:
      flag: alarm_raised_at_black_spring
    then: Узнав о налёте у Чёрного Истока, усиливает охрану верхнего яруса и ждёт у алтаря
    once: true
  ```
  Почему: Основная линия главы II: ритуал на рассвете (срок -- по событию nazir_ritual). Условие структурное: время + Назир жив. Второй триггер -- на флаг тревоги, который сейчас false (тревога культу не поднята).
  Источник: world.json events.nazir_ritual (ends_at_s); session.json current_scene.deadlines; ch2:938 (записка Назира «Владыка просыпается»); ch2:1807 (ритуал на рассвете)

### mor_lord

- **opportunity**
  ```yaml
  opportunity:
  - id: awakens
    if:
      all:
      - time_after: 23781600
      - npc_status:
          id: nazir
          is: alive
      - narrative: Кровавая жертва принесена у саркофага в Древнем Могильнике
    then: Печати Могильника трескаются -- Мор-Владыка просыпается
    once: true
    key: true
  ```
  Почему: Пробуждение Мор-Владыки -- цель Назира. Структурная часть (срок, Назир жив) отсекает лишние вызовы world; нарративная часть -- факт жертвы.
  Источник: world.json events.mor_lord_awakening; ch2:938; npcs.mor_lord.motive

### captain_of_guard

- **opportunity**
  ```yaml
  opportunity:
  - id: advance_on_forge
    if:
      all:
      - time_after: 23781600
      - npc_status:
          id: nazir
          is: alive
    then: Не дождавшись вестей от Грея, выводит заслон из предгорных деревень к Кузнице Пепла
    once: true
  ```
  Почему: Мотив -- защитить город и деревни; заслон стоит в предгорьях (сотня-две стражи и ополчения). Если на рассвете Назир жив, Капитан действует сам -- по плану «Щит и Клинок».
  Источник: flags.war_council_plan; npcs.captain_of_guard.relations_text; IMPORT_NOTES, противоречие «Силы Капитана»

### bran_sedogriv

- **opportunity**
  ```yaml
  opportunity:
  - id: kills_edrin_if_betrays
    if:
      all:
      - flag: edrin_joined_as_guide
      - narrative: Эдрин предаёт отряд или пытается предупредить часовых
    then: Бран без колебаний убивает Эдрина (месть за перебитых егерей Ложи)
    once: true
  ```
  Почему: Мотив Брана -- не дать пробудить Мор-Владыку и отомстить за егерей. Бран не доверяет культисту; триггер срабатывает только при предательстве Эдрина.
  Источник: npcs.bran_sedogriv.motive; ch2:480 (Бран о перебитых егерях); ch2:1975 (условие Грея для Эдрина)

### edrin

- **opportunity**
  ```yaml
  opportunity:
  - id: changes_mind
    if:
      all:
      - flag: edrin_joined_as_guide
      - narrative: Эдрин говорит вслух, что передумал
    then: Остаётся у подножия и не идёт к шахте -- Грей обещал не принуждать
    once: true
    key: true
  ```
  Почему: Грей поставил условие: если Эдрин передумает -- сказать вслух. Триггер на это условие; Эдрин -- ключевой проводник к Восточной шахте.
  Источник: ch2:1975 («скажи мне вслух. Просто скажи»); ch2:1912 (Эдрин обещает провести к шахте); flags.edrin_joined_as_guide

### milo

- **opportunity**
  ```yaml
  opportunity:
  - id: waits_in_ratusha
    if:
      npc_status:
        id: nazir
        is: dead
    then: Мило встречает Грея в Ратуше; Капитан пристраивает его учеником в гильдию оружейников, как обещал
    once: true
  ```
  Почему: Мотив -- верность Грею. Капитан обещал пристроить Мило в гильдию оружейников после похода; триггер -- победа над Назиром.
  Источник: ch2:1032 (Мило в гильдию оружейников); npcs.milo.relations_text

### father_mark

- **opportunity**
  ```yaml
  opportunity:
  - id: reads_folio_with_hero
    if:
      all:
      - hero_at: sanctuary_of_dawn
      - flag: abyss_keys_folio_stored_with_father_mark
    then: Предлагает вскрыть печать на фолианте «Ключи Бездны» вместе с героем -- в нём могут быть сведения о печатях Могильника
    once: true
  ```
  Почему: Мотив -- противостоять тьме Бездны. Фолиант лежит у него под печатью, герой в Святилище -- повод вернуться к нему. Содержимое фолианта в источнике не раскрыто -- это допущение.
  Источник: ch1:1039 (отец Марк о фолианте); ch1:1071 (запечатал ларец); flags.abyss_keys_folio_stored_with_father_mark

### varen

- **opportunity**
  ```yaml
  opportunity:
  - id: bargains_in_casemates
    if:
      all:
      - hero_at: city_ratusha
      - flag: varen_in_casemates
    then: Торгуется -- за смягчение приговора выдаёт всё, что знает о Магистре Второго Круга
    once: true
  ```
  Почему: Мотив Варена -- власть и заметание следов. Он в казематах и «раскололся», но личность Магистра не раскрыта (секрет magister_secret_1). Триггер даёт повод её раскрыть.
  Источник: ch2:224 (допросы Варена и Ольбрехта); ch1:858 (записка о Магистре); npcs.magister.secrets

## Фракции

### broken_key_brotherhood

- **opportunity**
  ```yaml
  opportunity:
  - id: goes_underground
    if:
      npc_status:
        id: nazir
        is: dead
    then: Остатки Братства уходят в подполье; Магистр Второго Круга берёт руководство и ищет новые Ключи
    once: true
  ```
  Почему: Магистр в источнике -- глава ордена с мотивом «закончить ритуал»; без Назира Братство не исчезает. «Ищет новые Ключи» -- допущение.
  Источник: ch1:858, ch1:1039 (Магистр); world.json npcs.magister.motive

### lodge_north_wind

- **opportunity**
  ```yaml
  opportunity:
  - id: returns_to_city
    if:
      all:
      - npc_status:
          id: olbrecht
          is: dead
      - npc_status:
          id: nazir
          is: dead
    then: Ложа открыто возвращается в Город; указ о «диких бандах» отменён Советом
    once: true
  ```
  Почему: Ложа объявлена браконьерами по указу Ольбрехта. Ольбрехт мёртв; после победы над Назиром у Ложи нет причин скрываться.
  Источник: ch2:480 (указ Ольбрехта о «диких бандах»); world.json factions.lodge_north_wind.motive

### city_guard

- **opportunity**
  ```yaml
  opportunity:
  - id: intercepts_raiders
    if:
      all:
      - event_active: harvest_raids
      - flag: captain_screens_villages
    then: Заслон перехватывает рейдовые группы орков и сопровождает жителей деревень в город
    once: true
  ```
  Почему: Заслон Капитана для того и поставлен: событие harvest_raids заканчивается, когда заслон перехватывает рейды.
  Источник: world.json events.harvest_raids.ends_when; flags.captain_screens_villages, signal_fires_lit

### city_council_conspiracy

- **opportunity**
  ```yaml
  opportunity:
  - id: silences_varen
    if:
      all:
      - flag: varen_in_casemates
      - npc_status:
          id: olbrecht
          is: dead
    then: Уцелевшие заговорщики пытаются освободить Варена или заставить его замолчать
    once: true
  ```
  Почему: Варен в казематах, Ольбрехт мёртв. Диверсанты уже освобождали Ольбрехта из казематов Ратуши -- такой ход Совета в духе источника.
  Источник: IMPORT_NOTES, противоречие «Ольбрехт» (шаги 126-130); flags.varen_in_casemates

### nazir_orcs

- **opportunity**
  ```yaml
  opportunity:
  - id: doubles_watch
    if:
      flag: alarm_raised_at_black_spring
    then: Орки удваивают караулы у вентиляционных шахт и отменяют «мёртвое окно» смены часовых
    once: true
  ```
  Почему: Сейчас тревога не поднята (флаг false), и отряд рассчитывает на смену часовых. Если её поднять, орки реагируют.
  Источник: session.json current_scene.enemies_known.schedule; flags.alarm_raised_at_black_spring

### chernolesye_village

- **opportunity**
  ```yaml
  opportunity:
  - id: bars_the_gates
    if:
      event_active: harvest_raids
    then: Деревня запирает ворота, ополчение встаёт на частокол, староста Тобин просит помощи у Города
    once: true
  ```
  Почему: Мотив -- выжить у болот. Набеги за жертвами идут на деревни предгорий (событие harvest_raids). Чернолесье -- деревня за частоколом с ополчением.
  Источник: world.json events.harvest_raids; factions.chernolesye_village.means; npcs.tobin.means

## Боги

### selune

- **motive**
  ```yaml
  motive: 'Каждая живая душа священна; её сила -- в живом и цветущем: чем больше жизни в её землях, тем она сильнее'
  ```
  Почему: Текст проектировщика (корыстный мотив: покровительство жизни, сила растёт с жизнью).
  Источник: stage3-p7-review.md, «Мотивы богов»
- **pleased_by**
  ```yaml
  pleased_by:
  - спасённая жизнь
  - рождение
  - исцеление
  - посеянное и выращенное
  - цветущая земля
  ```
  Почему: Текст проектировщика.
  Источник: stage3-p7-review.md
- **angered_by**
  ```yaml
  angered_by:
  - напрасная смерть
  - нежить
  - Мор
  - убийство сдавшихся
  ```
  Почему: Текст проектировщика.
  Источник: stage3-p7-review.md
- **rivals**
  ```yaml
  rivals:
  - shar
  - abyss_demon
  ```
  Почему: Текст проектировщика: соперники Шар и демон Бездны (Мор -- порождение культа демона).
  Источник: stage3-p7-review.md; ch1:160 (Шар -- враг Селунэ)
- **season_power**
  ```yaml
  season_power:
    весна: 15
    лето: 25
    осень: -15
    зима: -25
  ```
  Почему: S1: с весной силы Селунэ возрастают, с осенью убывают. Поправка к шансу божественного вмешательства в процентных пунктах. Числа -- на утверждение проектировщику. Лето +25 (решение проектировщика), сейчас осень (-15).
  Источник: stage3-p7-review.md, «S1»; имена сезонов -- стандартный календарь (зима, весна, лето, осень)
- **opportunity**
  ```yaml
  opportunity:
  - id: omen_for_the_living
    if:
      all:
      - not:
          flag: selune_owl_omen_seen
      - npc_status:
          id: edrin
          is: alive
      - hero_at: east_shaft
    then: Посылает отряду знамение (белая сова) -- её взгляд на тех, кто идёт спасать живых
    once: true
  - id: weakens_as_mor_spreads
    if:
      all:
      - time_after: 23781600
      - npc_status:
          id: nazir
          is: alive
      - narrative: Мор разошёлся по долине и губит живое
    then: Сила Селунэ в этих землях тает -- знамения слабеют, молитвы доходят хуже
    once: true
  ```
  Почему: Мотив Селунэ -- жизнь в её землях. Первый триггер -- знамение у шахты, пока знамения ещё не было (условие «не было», решение проектировщика; Эдрин жив -- повод для её внимания). Второй -- Мор отнимает жизнь: структурная часть (срок ритуала, Назир жив) отсекает лишние вызовы world, нарратив -- сам факт распространения Мора.
  Источник: ch2:1874-1890 (белая сова); ch2:1983; world.json events.nazir_ritual

### lathander

- **motive**
  ```yaml
  motive: Всё новое должно начинаться под его именем -- храмы, клятвы, первые шаги -- его слава
  ```
  Почему: Текст проектировщика.
  Источник: stage3-p7-review.md
- **pleased_by**
  ```yaml
  pleased_by:
  - дела, начатые с его именем
  - восстановленные святилища
  - уничтоженная нежить (оскорбляет рассвет)
  ```
  Почему: Текст проектировщика.
  Источник: stage3-p7-review.md
- **angered_by**
  ```yaml
  angered_by:
  - благословение без благодарности
  - брошенные начинания
  ```
  Почему: Текст проектировщика.
  Источник: stage3-p7-review.md
- **opportunity**
  ```yaml
  opportunity:
  - id: demands_thanks
    if:
      all:
      - hero_at: sanctuary_of_dawn
      - flag: lathander_blessing_used
    then: Через отца Марка напоминает герою о благодарности за Благословение -- новое начинание под его именем, тогда благословение возобновится
    once: false
    cooldown: 7d
  ```
  Почему: Мотив -- слава начинаний. Благословение в главе I использовано (флаг); без благодарности Латандр сердится (angered_by). Структурные условия, срок 7d -- допущение.
  Источник: ch1:1085; flags.lathander_blessing_used; stage3-p7-review.md

### shar

- **motive**
  ```yaml
  motive: Питается утратами и забытым; хочет, чтобы её боялись и почитали тайно, а свет Селунэ погас
  ```
  Почему: Текст проектировщика.
  Источник: stage3-p7-review.md
- **pleased_by**
  ```yaml
  pleased_by:
  - предательство
  - утрата
  - забытые имена
  ```
  Почему: Текст проектировщика.
  Источник: stage3-p7-review.md
- **angered_by**
  ```yaml
  angered_by:
  - возвращённая память
  - знаки Селунэ
  ```
  Почему: Текст проектировщика.
  Источник: stage3-p7-review.md
- **rivals**
  ```yaml
  rivals:
  - selune
  ```
  Почему: Взаимно с Селунэ: источник называет Шар её врагом.
  Источник: ch1:160
- **opportunity**
  ```yaml
  opportunity:
  - id: feeds_on_loss
    if:
      npc_status:
        id: milo
        is: dead
    then: Шепчет Грею в час утраты -- толкает к отчаянию и тайному поклонению Шар
    once: true
  ```
  Почему: Мотив -- питаться утратами. Самая личная утрата Грея в источнике -- Мило (дважды спасён, молится Селунэ, враг Шар). Мило жив, триггер спящий. Слабый черновик: у Шар в источнике нет действий.
  Источник: ch1:160; world.json npcs.milo; stage3-p7-review.md

### faceless

- **motive**
  ```yaml
  motive: 'Копит секреты: каждое скрытое знание -- его сила'
  ```
  Почему: Текст проектировщика.
  Источник: stage3-p7-review.md
- **pleased_by**
  ```yaml
  pleased_by:
  - хранимая тайна
  - сделка в тени
  - украденное знание
  ```
  Почему: Текст проектировщика.
  Источник: stage3-p7-review.md
- **angered_by**
  ```yaml
  angered_by:
  - раскрытые тайны и имена его служителей
  ```
  Почему: Текст проектировщика.
  Источник: stage3-p7-review.md
- **opportunity**
  ```yaml
  opportunity:
  - id: wants_the_folio
    if:
      all:
      - hero_at: dead_barrow
      - flag: abyss_keys_folio_stored_with_father_mark
    then: Предлагает герою сделку в тени -- тайна за тайну; его интересует фолиант «Ключи Бездны»
    once: true
  ```
  Почему: Мотив -- копить секреты. Самое ценное скрытое знание в источнике -- фолиант «Ключи Бездны», спрятанный у отца Марка; часовня Безликого стоит на Мёртвом Кургане. Слабый черновик.
  Источник: ch1:4674 (часовня Безликого); ch1:1039, ch1:1071 (фолиант); stage3-p7-review.md

### ilmater

- **motive**
  ```yaml
  motive: Набирает силу от тех, кто принимает чужую боль; ему нужны мученики
  ```
  Почему: Текст проектировщика.
  Источник: stage3-p7-review.md
- **pleased_by**
  ```yaml
  pleased_by:
  - стойкость в страдании
  - боль, взятая за другого
  ```
  Почему: Текст проектировщика.
  Источник: stage3-p7-review.md
- **angered_by**
  ```yaml
  angered_by:
  - спасение себя ценой чужой боли
  - лёгкие пути
  ```
  Почему: Текст проектировщика.
  Источник: stage3-p7-review.md
- **opportunity**
  ```yaml
  opportunity:
  - id: seeks_a_martyr
    if:
      all:
      - flag: edrin_joined_as_guide
      - hero_at: east_shaft
    then: Обращает внимание на того, кто готов взять удар за других -- знамение стойкости для героя или Эдрина
    once: true
  ```
  Почему: Мотив -- мученики. Эдрин идёт искупать вину и рискует собой у шахты -- ближайший кандидат в источнике. Слабый черновик: Ильматер упомянут один раз.
  Источник: ch2:428; ch2:1912 (Эдрин обещает провести к шахте); stage3-p7-review.md

### abyss_demon

- **motive**
  ```yaml
  motive: Прорваться в мир через Врата Бездны, которые открывает Орден Разбитого Ключа
  ```
  Почему: Источник: культ поклоняется высшему демону Бездны и ищет печати; мотив бога выведен из цели культа. Связь с Мор-Владыкой не подтверждена.
  Источник: ch1:1029 (слова отца Марка); world.json gods.abyss_demon.role
- **pleased_by**
  ```yaml
  pleased_by:
  - вскрытие печатей и Врат
  - кровавые жертвы
  - служение Братству Мора
  ```
  Почему: Выведено из целей и обрядов культа.
  Источник: ch1:1029; world.json factions.broken_key_brotherhood.motive
- **angered_by**
  ```yaml
  angered_by:
  - уничтожение Кристаллов-Ключей
  - запечатывание Врат и Могильника
  - убийство иерархов Ордена
  ```
  Почему: Выведено из того, что Грей уже сделал: все три Кристалла уничтожены, иерархи убиты.
  Источник: flags.all_crystals_destroyed, abbey_hierarch_dead, second_hierarch_dead, third_hierarch_dead
- **opportunity**
  ```yaml
  opportunity:
  - id: answers_awakening
    if:
      all:
      - time_after: 23781600
      - npc_status:
          id: nazir
          is: alive
      - narrative: Мор-Владыка пробуждается
    then: Откликается на пробуждение Мор-Владыки и тянется к Вратам Бездны
    once: true
  ```
  Почему: Связь демона с Мор-Владыкой источник не подтверждает (role: «возможно связан»). Слабый черновик: структурное условие то же, что у Назира.
  Источник: world.json gods.abyss_demon.role; ch1:1029

## Герои (решения проектировщика)

### grey

- **level**
  ```yaml
  level: 3
  ```
  Почему: Решение проектировщика: Грей начинает на 3 ур., Повелитель зверей.
  Источник: docs/decisions/stage3-audit.md (решение «Грей: уровень 3»); docs/decisions/ranger-2-5-plan.md, решения
- **xp**
  ```yaml
  xp: 900
  ```
  Почему: Опыт 3 ур. по таблице (xp.yaml).
  Источник: srd/data/tables/xp.yaml
- **level_choices**
  ```yaml
  level_choices:
  - level: 2
    fighting_style: archery
    expertise:
    - survival
    languages:
    - celestial
    - gnomish
  - level: 3
    subclass_id: beast_master
    spells_add:
    - cure_wounds
    - ensnaring_strike
    - speak_with_animals
    - fog_cloud
  ```
  Почему: Решения проектировщика 2-4: стиль «Стрельба», экспертиза в Выживании, Повелитель зверей, 4 заклинания 1 круга (Метка охотника подготовлена всегда). Языки (2) -- Великаний и Гномий (рекомендация папы-кабана, пункт В4).
  Источник: docs/decisions/ranger-2-5-plan.md, разд. 8 (В2-В4) и решения проектировщика
- **companion**
  ```yaml
  companion:
    name: Акела
    kind: волк
    notes: Серый волк; перед походом его доверил Грею Йорген-зверолов. Идёт по следу, чует ветер, сторожит стоянку; в бою пока не участвует.
  ```
  Почему: Решение проектировщика 1: зверь Грея -- волк Акела, введён через Йоргена-зверолова, прошлые сцены не переписываются.
  Источник: docs/decisions/ranger-2-5-plan.md, В1 и решение 1

## Отчёт конвертера (не draft, правит проектировщик)

- Локации «Предгорья Кряжа» и «Серый Квартал» добавлены конвертером (решение Q3); на них
  ссылаются регионы `harvest_raids` и `city_council_conspiracy`.
- Мотив Грея взят из решения проектировщика (Q2), а не из `hero.json`; средства героя не перенесены.
