from typing import Annotated, ClassVar, Literal, get_args

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator, model_validator

from ai_dm.content.models.common import Ability, DcCategory, Skill
from ai_dm.state.combat import ImproviseEffect, Intent
from ai_dm.state.gender import Gender
from ai_dm.state.knowledge import KNOWLEDGE_KINDS, KNOWLEDGE_SOURCES
from ai_dm.state.relations import GOAL_KINDS, MEMORY_KINDS
from ai_dm.state.world import Tone

# strict-схема без union: необязательные поля обязательны для модели и имеют нейтральное значение
# («» / 0 / «none» / [] = нет); при разборе нейтральное значение превращается в None
AbilityOrNone = Literal[(*get_args(Ability), "none")]
SkillOrNone = Literal[(*get_args(Skill), "none")]
GenderOrNone = Literal[(*get_args(Gender), "none")]
GenderUpdate = Literal[(*get_args(Gender), "none", "unset")]
MemoryKindOrNone = Literal[(*MEMORY_KINDS, "none")]
GoalKindOrNone = Literal[(*GOAL_KINDS, "none")]
ImproviseEffectOrNone = Literal[(*get_args(ImproviseEffect), "none")]
DcCategoryOrNone = Literal[(*get_args(DcCategory), "none")]
ParleySkillOrNone = Literal["intimidation", "persuasion", "deception", "none"]
ParleyOutcomeOrNone = Literal["surrender", "flee", "defect", "waver", "quarrel", "none"]


class Request(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # имя поля -> нейтральное значение, которое при разборе становится None
    NEUTRAL: ClassVar[dict] = {}

    @model_validator(mode="after")
    def cut_neutral(self):
        for name, neutral in self.NEUTRAL.items():
            if getattr(self, name) == neutral:
                setattr(self, name, None)
        return self


# вложенные части запросов

class FeatureSpec(Request):
    kind: str = Field(
        description="Вид: cover_half, cover_three_quarters, difficult, hazard или другой."
    )
    damage: str = Field("", description="Кубики урона hazard, например 2d6; иначе пусто.")
    damage_type: str = Field("", description="Тип урона hazard; пусто = fire.")
    save: AbilityOrNone = Field("none", description="Спасбросок против hazard; none = нет.")
    dc: int = Field(0, description="СЛ спасброска hazard; 0 = по умолчанию 10.")
    NEUTRAL: ClassVar[dict] = {"damage": "", "damage_type": "", "save": "none", "dc": 0}


class ZoneSpec(Request):
    id: str = Field(description="Идентификатор зоны, латиницей.")
    name: str = Field(description="Название зоны для игрока; у зон боя названия разные.")
    adjacent: list[str] = Field(description="Идентификаторы соседних зон; связь взаимная.")
    exit: bool = Field(False, description="Из зоны можно сбежать с боя.")
    elevation: int = Field(
        0,
        description="Высота зоны: 0 -- земля, выше (стена, крыша, уступ) -- 1 и больше, "
        "ниже (яма, овраг) -- -1 и меньше. Стрелок выше цели бьёт с преимуществом, "
        "ниже -- с помехой.",
    )
    pos: list[int] = Field(
        [],
        description="Место зоны на карте боя [ряд, колонка], от 0; пусто = раскладка "
        "по смежности. Нужно, только если раскладка по умолчанию неудачна.",
    )
    features: list[FeatureSpec] = Field([], description="Особенности зоны; пусто = нет.")


class EnemySpec(Request):
    ref: str = Field(
        description="id именованного NPC мира или новый id безымянного монстра."
    )
    monster_id: str = Field(description="Id монстра из реестра (его характеристики).")
    zone: str = Field(description="Идентификатор зоны, где враг стоит в начале боя.")
    group: str = Field(description="Идентификатор группы врага из groups.")
    name: str = Field("", description="Имя безымянного монстра; пусто = из реестра.")
    NEUTRAL: ClassVar[dict] = {"name": ""}


class GroupSpec(Request):
    id: str = Field(description="Идентификатор группы.")
    leader: str = Field(description="ref врага-лидера группы.")
    intent: Intent = Field(description="Намерение группы: kill, capture, rob, drive_off, spare.")
    lair_location_id: str = Field("", description="Id локации-логова (для плена); пусто = нет.")
    NEUTRAL: ClassVar[dict] = {"lair_location_id": ""}


class ImproviseSpec(Request):
    skill: SkillOrNone = Field("none", description="Навык импровизации; none, если её нет.")
    category: DcCategoryOrNone = Field(
        "none", description="Категория сложности проверки; none, если импровизации нет."
    )
    effect: ImproviseEffectOrNone = Field(
        "none",
        description="Эффект при успехе, только из набора: advantage — преимущество на следующую "
        "атаку героя; prone — цель сбита с ног (нужен target); extra_damage — доп. урон цели "
        "(target); push — цель отброшена в соседнюю зону (target и zone: зона, соседняя с зоной "
        "цели, не её собственная; в зону ниже -- урон от падения); "
        "disarm — выбить оружие (target); none — импровизации нет.",
    )
    target: str = Field("", description="ref цели; пусто = нет.")
    zone: str = Field("", description="Идентификатор зоны, если действие про зону; пусто = нет.")
    NEUTRAL: ClassVar[dict] = {"effect": "none", "target": "", "zone": ""}


class PreparedSwapSpec(Request):
    drop: list[str] = Field([], description="Id подготовленных, которые снять; пусто = нет.")
    take: list[str] = Field(
        [], description="Id заклинаний класса, которые подготовить; пусто = нет."
    )


class ParleySpec(Request):
    skill: ParleySkillOrNone = Field(
        "none", description="Навык переговоров: intimidation, persuasion, deception; none = нет."
    )
    outcome: ParleyOutcomeOrNone = Field(
        "none",
        description="Чего хочет герой от цели: surrender, flee, defect (перейти на сторону героя), "
        "waver (поколебаться, потерять ход), quarrel (поссориться со своими: цель один ход бьёт "
        "союзника); none = нет. Исход и СЛ решает движок.",
    )
    target: str = Field("", description="ref врага, с кем говорят; пусто = нет.")
    NEUTRAL: ClassVar[dict] = {"target": ""}


class ConnectionSpec(Request):
    to: str = Field(description="Id локации, с которой есть связь.")
    distance_m: int = Field(description="Расстояние в метрах.")


# запросы мастера (ТЗ 2.1)

class SkillCheck(Request):
    """Проверка навыка героя. Мастер выбирает навык и категорию сложности, движок бросает."""

    type: Literal["skill_check"]
    skill: Skill = Field(description="Навык.")
    category: DcCategory = Field(
        description="very_easy 5, easy 10, medium 15, hard 20, very_hard 25, nearly_impossible 30"
    )
    stakes: Literal["normal", "critical"] = Field(
        "normal", description="critical, если от броска зависит критический исход; иначе normal."
    )
    NEUTRAL: ClassVar[dict] = {"stakes": "normal"}


class SavingThrow(Request):
    """Спасбросок героя. Мастер выбирает характеристику и категорию сложности, движок бросает."""

    type: Literal["saving_throw"]
    ability: Ability = Field(description="Характеристика спасброска.")
    category: DcCategory = Field(description="Категория сложности.")
    stakes: Literal["normal", "critical"] = Field(
        "normal", description="critical, если от броска зависит критический исход; иначе normal."
    )
    NEUTRAL: ClassVar[dict] = {"stakes": "normal"}


class StartCombat(Request):
    """Начать бой: зоны, враги и их группы с намерениями. Герой стоит в зоне hero_zone."""

    type: Literal["start_combat"]
    zones: list[ZoneSpec] = Field(description="Зоны боя, от 2 до 5, связный граф.")
    enemies: list[EnemySpec] = Field(description="Враги, не больше шести.")
    groups: list[GroupSpec] = Field(description="Группы врагов с лидером и намерением.")
    hero_zone: str = Field(description="Идентификатор зоны, где стоит герой.")
    initiated_by: Literal["enemies", "hero"] = Field(
        "enemies", description="hero, если герой сам напал на заведомо сильного противника."
    )
    hero_hidden: bool = Field(
        False,
        description="true, если герой перед боем успешно спрятался (проверка Скрытности "
        "удалась): его первая атака пойдёт с преимуществом.",
    )


class PlayerAction(Request):
    """Действие игрока в бою: цепочка вариантов из списка движка и/или импровизация."""

    type: Literal["player_action"]
    steps: list[str] = Field(description="Идентификаторы вариантов из списка движка по порядку.")
    improvise: ImproviseSpec = Field(
        default_factory=ImproviseSpec,
        description="Импровизированное действие; без него skill и category равны none.",
    )
    parley: ParleySpec = Field(
        default_factory=ParleySpec,
        description="Уговоры, угрозы или ложь врагу в бою (не improvise); без них skill и "
        "outcome равны none.",
    )
    unsupported: str = Field("", description="Часть фразы, которой нет в механике; пусто = нет.")
    NEUTRAL: ClassVar[dict] = {"unsupported": ""}

    @model_validator(mode="after")
    def cut_improvise(self):
        spec = self.improvise
        if spec.skill == "none" and spec.category == "none":
            self.improvise = None
        elif spec.skill == "none" or spec.category == "none":
            raise ValueError("improvise: skill и category задаются вместе или обе none")
        elif spec.effect is None:
            effects = ", ".join(get_args(ImproviseEffect))
            raise ValueError(f"improvise: effect обязателен ({effects})")
        return self

    @model_validator(mode="after")
    def cut_parley(self):
        spec = self.parley
        if spec.skill == "none" and spec.outcome == "none" and spec.target is None:
            self.parley = None
        elif spec.skill == "none" or spec.outcome == "none" or spec.target is None:
            raise ValueError("parley: skill, outcome и target задаются вместе или все пусты")
        elif self.improvise is not None:
            raise ValueError("parley и improvise вместе не задаются")
        return self


class NpcAction(Request):
    """Выбор действия ключевого NPC или напарника из списка движка."""

    type: Literal["npc_action"]
    choice: str = Field(description="Идентификатор выбранного варианта из списка.")


class DefeatOutcome(Request):
    """Последствия поражения героя: одно или два из таблицы."""

    type: Literal["defeat_outcome"]
    consequences: list[
        Literal["capture", "rob", "left_to_die", "scar", "exhaustion", "debt"]
    ] = Field(description="Одно или два последствия.")
    lair_location_id: str = Field("", description="Id логова для плена; пусто = нет.")
    scar_ability: AbilityOrNone = Field(
        "none", description="Характеристика, которую снижает шрам; none = нет."
    )
    scar_skill: SkillOrNone = Field(
        "none", description="Навык шрама (вместо характеристики); none = нет."
    )
    scar_text: str = Field("", description="Описание шрама; пусто = нет.")
    debt_to: str = Field("", description="Id NPC-кредитора для долга; пусто = нет.")
    debt_text: str = Field("", description="Описание долга; пусто = нет.")
    rob_items: int = Field(
        0, description="Сколько предметов отобрать, 1 или 2; 0 = на усмотрение движка."
    )
    NEUTRAL: ClassVar[dict] = {
        "lair_location_id": "", "scar_ability": "none", "scar_skill": "none", "scar_text": "",
        "debt_to": "", "debt_text": "", "rob_items": 0,
    }


class EndCombat(Request):
    """Завершить бой после сдачи или бегства врагов по логу (переговоры);
    пока враги дерутся — отклоняется.
    """

    type: Literal["end_combat"]
    reason: str = Field("", description="Причина завершения; пусто = нет.")
    NEUTRAL: ClassVar[dict] = {"reason": ""}


class Damage(Request):
    """Урон герою вне боя. Мастер выбирает тяжесть, движок бросает кубики."""

    type: Literal["damage"]
    severity: Literal["nuisance", "dangerous", "deadly"] = Field(
        description="Тяжесть: nuisance, dangerous, deadly (deadly только после провала)."
    )
    damage_type: str = Field(description="Тип урона: fire, poison, falling и т.п.")
    failed_roll_ref: str = Field(
        "", description="roll_ref проваленного броска этого хода; нужен для deadly, иначе пусто."
    )
    NEUTRAL: ClassVar[dict] = {"failed_roll_ref": ""}


class Curse(Request):
    """Проклясть героя (реликвия, ведьма, осквернённое место, ловушка): только после его
    проваленного броска этого хода. Снимается платной услугой храма.
    """

    type: Literal["curse"]
    failed_roll_ref: str = Field(
        description="roll_ref проваленного броска (проверка или спасбросок) этого хода."
    )
    cause: str = Field(description="Источник проклятия одной фразой, до 80 знаков.")


class GiveItem(Request):
    """Дать герою предмет из реестра."""

    type: Literal["give_item"]
    item_id: str = Field(description="Id предмета из реестра.")
    qty: int = Field(description="Количество.")


class GiveCustomItem(Request):
    """Создать и дать герою сюжетный предмет, которого нет в реестре (ключ, записка, перстень)."""

    type: Literal["give_custom_item"]
    name: str = Field(description="Короткое название предмета.")
    description: str = Field(description="Описание в одну-две фразы; пусто = без описания.")
    qty: int = Field(description="Количество.")
    weight_lb: float = Field(description="Вес в фунтах; 0 = не задан.")
    cost_cp: int = Field(description="Цена в медных монетах; 0 = без цены.")
    quest: bool = Field(description="Важный для сюжета предмет.")
    NEUTRAL: ClassVar[dict] = {"weight_lb": 0}


class UseItem(Request):
    """Герой применяет расходник из инвентаря (сам или ему его дают): выпивает эликсир или зелье
    (вне боя)."""

    type: Literal["use_item"]
    item_id: str = Field(description="Id предмета из инвентаря героя.")
    qty: int = Field(1, description="Сколько штук применить (эликсир с эффектом на время: одну).")


class CastSpell(Request):
    """Герой творит заклинание вне боя: ячейка, бесплатное применение и эффект по данным движка."""

    type: Literal["cast_spell"]
    spell_id: str = Field(description="Id заклинания героя (известный заговор или подготовленное).")
    circle: int = Field(
        description="Круг ячейки: круг заклинания или выше у заклинаний с усилением (upcast); "
        "0 для заговоров; бесплатное применение -- только круг заклинания."
    )
    target: str = Field(
        "", description="hero или id NPC в локации; пусто = на себя или без цели."
    )
    free: bool = Field(
        False, description="true: бесплатное применение умения (например, Избранный враг)."
    )
    NEUTRAL: ClassVar[dict] = {"target": ""}


class TakeItem(Request):
    """Забрать у героя предмет."""

    type: Literal["take_item"]
    item_id: str = Field(description="Id предмета.")
    qty: int = Field(description="Количество.")
    why: Literal["given", "lost", "stolen", "spent"] = Field(
        description="Почему предмет уходит: given отдан, lost потерян, stolen украден, "
        "spent израсходован не применением (вылит, сожжён, сломан, уничтожен). "
        "Выпить или применить предмет: только use_item."
    )
    holder_npc_id: str = Field(
        "", description="Для сюжетных предметов при given/lost/stolen: id NPC в этой локации, "
        "у которого вещь оказалась (обязателен); при spent и для обычных предметов пусто."
    )
    NEUTRAL: ClassVar[dict] = {"holder_npc_id": ""}


class Trade(Request):
    """Купить или продать предмет у NPC-торговца в локации героя. Цену считает движок."""

    type: Literal["trade"]
    npc_id: str = Field(description="Id NPC-торговца (в scene_npcs с merchant).")
    direction: Literal["buy", "sell", "list"] = Field(
        description="buy герой покупает, sell продаёт, list: показать все позиции категории "
        "с ценами (без сделки)."
    )
    item_id: str = Field(description="Id предмета; для list пусто.")
    qty: int = Field(description="Количество; для list 0.")
    category: str = Field(
        "", description="Только для list: категория из categories торговца; иначе пусто."
    )
    quality: Literal["junk", "worn", "used", "new", "any"] = Field(
        "any", description="Какой стек: качество экземпляра, new без качества; any = любой."
    )
    NEUTRAL: ClassVar[dict] = {"quality": "any", "category": ""}


class Haggle(Request):
    """Торг Убеждением с торговцем: движок бросает Убеждение героя против СЛ торговца, итог --
    скидка или наценка покупки у него до конца дня. Раз в день на торговца."""

    type: Literal["haggle"]
    npc_id: str = Field(description="Id NPC-торговца (в scene_npcs с merchant).")


class Service(Request):
    """Платная услуга NPC в локации героя: еда, питьё, лечение. Цену считает движок."""

    type: Literal["service"]
    npc_id: str = Field(description="Id NPC с услугами (в scene_npcs с services).")
    direction: Literal["buy", "list"] = Field(
        description="buy герой платит за услугу, list: показать услуги NPC с ценами (без оплаты)."
    )
    service_id: str = Field(description="Id услуги из services NPC; для list пусто.")
    qty: int = Field(description="Сколько раз (порций, кружек, лечений); для list 0.")


class Gold(Request):
    """Деньги героя: явная сумма, добыча с побеждённых по таблице или клад логова."""

    type: Literal["gold"]
    direction: Literal["gain", "lose"] = Field(description="gain: получить, lose: потерять.")
    kind: Literal["explicit", "loot_individual", "hoard"] = Field(
        description="explicit: сумма amount_cp; loot_individual: добыча с врагов последнего боя; "
        "hoard: клад логова, где был последний бой."
    )
    amount_cp: int = Field(0, description="Сумма в медных монетах для explicit; иначе 0.")
    cr: str = Field("", description="Не используется: всегда пустая строка.")
    NEUTRAL: ClassVar[dict] = {"amount_cp": 0, "cr": ""}


class AwardXp(Request):
    """Опыт за квест или находку. Мастер называет масштаб, объём считает движок."""

    type: Literal["award_xp"]
    scale: Literal["minor", "medium", "major"] = Field(description="Масштаб награды.")
    reason: str = Field(description="Повод награды.")


class AdvanceTime(Request):
    """Сдвинуть время на категорию, до цели или перевезти героя в локацию (путь по карте).

    Нужно ровно одно из category, travel_to и until.
    """

    type: Literal["advance_time"]
    category: Literal["none", "minute", "hour", "day", "week", "month"] = Field(
        "none", description="На сколько сдвинуть время; none, если идёт путь."
    )
    travel_to: str = Field(
        "",
        description=(
            "Id локации из locations или known_locations; путь по карте считает движок; "
            'пусто = нет (не "none").'
        ),
    )
    until: Literal["none", "morning", "long_rest", "hour"] = Field(
        "none",
        description=(
            "Сдвиг до цели: morning (утро), long_rest (пока снова можно длинный отдых), "
            "hour (час until_hour); none, если не до цели."
        ),
    )
    until_hour: int = Field(-1, description="Час 0-23 для until=hour; иначе -1.")
    pace: Literal["slow", "normal", "fast"] = Field("normal", description="Темп пути.")
    NEUTRAL: ClassVar[dict] = {
        "category": "none", "travel_to": "", "until": "none", "until_hour": -1,
    }

    @field_validator("until_hour")
    @classmethod
    def until_hour_in_day(cls, value):
        # ge/le в strict-схему не попадают -- диапазон проверяем здесь
        if not -1 <= value <= 23:
            raise ValueError("until_hour: час 0-23 (-1 = нет)")
        return value

    @field_validator("travel_to", mode="before")
    @classmethod
    def none_travel_is_empty(cls, value):
        # модель по аналогии с category пишет "none" вместо пустой строки
        return "" if value == "none" else value


class Rest(Request):
    """Отдых героя."""

    type: Literal["rest"]
    kind: Literal["short", "long"] = Field(description="short: короткий, long: длинный.")
    hit_dice: int = Field(0, description="Сколько костей хитов потратить (короткий); 0 = нет.")
    prepared_swap: PreparedSwapSpec = Field(
        default_factory=PreparedSwapSpec,
        description="Смена подготовленных после длинного отдыха; без неё оба списка пусты.",
    )
    prey_swap: str = Field(
        "",
        description="Смена приёма Добычи охотника после отдыха (следопыт 3+): id варианта "
        "colossus_slayer или horde_breaker; пусто = без смены.",
    )
    NEUTRAL: ClassVar[dict] = {"hit_dice": 0, "prey_swap": ""}

    @model_validator(mode="after")
    def cut_swap(self):
        spec = self.prepared_swap
        if not spec.drop and not spec.take:
            self.prepared_swap = None
        return self


class SetFlag(Request):
    """Поставить флаг мира."""

    type: Literal["set_flag"]
    name: str = Field(description="Имя флага.")
    value: str = Field(description="Значение флага: true или false для да/нет, иначе текст.")


class NpcCreate(Request):
    """Создать нового NPC."""

    type: Literal["npc_create"]
    id: str = Field(description="Уникальный id NPC.")
    name: str = Field(description="Имя; у именованных NPC уникально.")
    means: list[str] = Field(description="Средства NPC, от одного до трёх.")
    named: bool = Field(False, description="Именованный NPC.")
    key: bool = Field(False, description="Ключевой NPC.")
    motive: str = Field("", description="Мотив NPC; пусто = нет.")
    location_id: str = Field("", description="Id локации, где NPC находится; пусто = нет.")
    trade_kind: str = Field(
        "none", description="Тип торговца (пресет ассортимента), если NPC торгует; none = нет."
    )
    gender: GenderOrNone = Field(
        "none", description="Пол NPC: male, female, other; none = не известен."
    )
    pronouns: str = Field(
        "", description="Местоимения/обращение, если отличаются от пола или важны; пусто = нет."
    )
    services: list[str] = Field(
        [], description="Id платных услуг NPC (ночлег, еда, лечение); пусто = нет."
    )
    NEUTRAL: ClassVar[dict] = {
        "motive": "", "location_id": "", "trade_kind": "none", "gender": "none", "pronouns": "",
        "services": [],
    }


class LocationCreate(Request):
    """Создать новую локацию."""

    type: Literal["location_create"]
    id: str = Field(description="Уникальный id локации.")
    name: str = Field(description="Название; в одном родителе уникально.")
    parent_id: str = Field("", description="Id родительской локации; пусто = нет.")
    description: str = Field("", description="Описание локации; пусто = нет.")
    connections: list[ConnectionSpec] = Field(
        [], description="Связи с другими локациями; пусто = нет."
    )
    NEUTRAL: ClassVar[dict] = {"parent_id": "", "description": ""}


class NpcUpdateBase(Request):
    type: Literal["npc_update"]
    npc_id: str = Field(description="Id NPC.")
    attitude_delta: int = Field(0, description="Изменение отношения к герою; 0 = не менять.")
    status: Literal["none", "dead", "gone"] = Field(
        "none", description="Смерть или уход из игры; none = не менять."
    )
    cause: Literal["none", "goal", "hazard", "chance", "old_age"] = Field(
        "none", description="Причина смерти; мастеру доступны goal и hazard; none без смерти."
    )
    evidence_ref: str = Field("", description="roll_ref броска этого хода; пусто = нет.")
    by: str = Field("", description="Кто виновник (id существа); пусто = нет.")
    text: str = Field("", description="Краткое описание обстоятельств; пусто = нет.")
    # Gemini не принимает пустую строку в enum -- нейтральное значение keep
    follows: Literal["hero", "none", "keep"] = Field(
        "keep", description="hero = NPC присоединился к герою и идёт с ним; none = отстал; "
        "keep = без изменений."
    )
    gender: GenderUpdate = Field(
        "none", description="Пол NPC: male, female, other; none = не менять; unset = сбросить."
    )
    pronouns: str = Field(
        "", description="Местоимения/обращение NPC; пусто = не менять; - = сбросить."
    )
    goal_kind: GoalKindOrNone = Field(
        "none", description="Долгая цель NPC: поставить или (с goal_status) закрыть; none = нет."
    )
    goal_target: str = Field(
        "", description="Id героя или NPC, на кого направлена цель; пусто = герой."
    )
    goal_text: str = Field("", description="Суть цели при постановке; пусто = типовой текст.")
    goal_status: Literal["none", "done", "dropped"] = Field(
        "none", description="Закрыть активную цель goal_kind/goal_target: done или dropped; "
        "none = поставить цель."
    )
    NEUTRAL: ClassVar[dict] = {
        "attitude_delta": 0, "status": "none", "cause": "none", "evidence_ref": "", "by": "",
        "text": "", "follows": "keep", "gender": "none", "pronouns": "", "goal_kind": "none",
        "goal_target": "", "goal_text": "", "goal_status": "none",
    }


class NpcUpdate(NpcUpdateBase):
    """Изменить NPC: отношение к герою, смерть или уход (только с причиной и доказательством)."""

    trade_kind: str = Field(
        "none", description="Сделать NPC торговцем типа (пресет ассортимента); none = не менять."
    )
    memory_kind: MemoryKindOrNone = Field(
        "none",
        description="Вид события между героем и NPC (поступок или тёплый момент); none = нет.",
    )
    memory_text: str = Field(
        "", description="Коротко, что сделал герой (до 120 знаков); только вместе с memory_kind."
    )
    name: str = Field(
        "", description="Настоящее имя безымянного выжившего боя (в состоянии unnamed); "
        "один раз; пусто = не менять."
    )
    services: list[str] = Field(
        [], description="Добавить NPC платные услуги (id видов); пусто = не менять."
    )
    NEUTRAL: ClassVar[dict] = {
        **NpcUpdateBase.NEUTRAL, "trade_kind": "none", "memory_kind": "none", "memory_text": "",
        "name": "", "services": [],
    }


class CompanionUpdate(Request):
    """Зверь-спутник героя (Повелитель зверей): появление зверя, его гибель или уход."""

    type: Literal["companion_update"]
    action: Literal["join", "dead", "gone"] = Field(
        description="join = зверь появился; dead = погиб; gone = ушёл."
    )
    name: str = Field("", description="Имя зверя; обязательно при join.")
    kind: str = Field("", description="Вид словами: волк, капибара; обязательно при join.")
    notes: str = Field("", description="Откуда, повадки; пусто = нет.")
    NEUTRAL: ClassVar[dict] = {"name": "", "kind": "", "notes": ""}


class KnowledgeNote(Request):
    """Записать в журнал знаний героя, что он узнал: слова NPC, слух, записка, вывод."""

    type: Literal["knowledge_note"]
    kind: Literal[KNOWLEDGE_KINDS] = Field(description="О ком запись.")
    ref: str = Field(
        description="npc/location/faction/god: id; creature: id монстра; situation: слаг a-z0-9_."
    )
    text: str = Field(description="Что узнал герой, коротко (до 160 знаков).")
    source: Literal[KNOWLEDGE_SOURCES] = Field(
        description="seen = видел сам; told = рассказал NPC (from_ref); rumor = слух; "
        "read = прочитал; deduced = понял сам."
    )
    from_ref: str = Field("", description="Id рассказавшего NPC, обязателен при told; иначе пусто.")
    NEUTRAL: ClassVar[dict] = {"from_ref": ""}


class SceneMood(Request):
    """Настроение текущей сцены для музыки: romance по сюжету или none, чтобы снять."""

    type: Literal["scene_mood"]
    mood: Literal["romance", "none"] = Field(
        description="romance = романтическая сцена; none = снять."
    )
    NEUTRAL: ClassVar[dict] = {"mood": "none"}


class WarnDanger(Request):
    """Предупреждение об опасности в локации."""

    type: Literal["warn_danger"]
    location_id: str = Field(description="Id локации.")
    text: str = Field(description="Текст предупреждения.")


class FavorChange(Request):
    """Изменить благосклонность бога к герою. Движок урежет шаг до ±2 и ±3 к богу за сцену."""

    type: Literal["favor_change"]
    target: str = Field(description="Кому: hero (рассказчику) или id NPC (роли world).")
    god_id: str = Field(description="Id бога.")
    delta: int = Field(description="Изменение благосклонности.")
    reason: str = Field(description="Короткая причина: чем угодил или прогневал бога.")


class Pray(Request):
    """Игрок молится богу: при благосклонности 6 и выше даёт преимущество на день."""

    type: Literal["pray"]
    god_id: str = Field(description="Id бога, которому молится герой.")


class ChangeDeity(Request):
    """Герой сменил бога после сделки или квеста: новому богу +1 благосклонности."""

    type: Literal["change_deity"]
    god_id: str = Field(description="Id нового бога.")
    reason: str = Field(description="Короткая причина смены бога.")


class RevealSecret(Request):
    """Раскрыть секрет NPC."""

    type: Literal["reveal_secret"]
    npc_id: str = Field(description="Id NPC.")
    secret_id: str = Field(description="Id секрета.")


class EventStart(Request):
    """Начать глобальное событие."""

    type: Literal["event_start"]
    id: str = Field(description="Id события.")
    event_type: str = Field(description="Вид события: war, plague и т.п.")
    cause: str = Field("", description="Причина (сработавший триггер); пусто = нет.")
    regions: list[str] = Field(
        [], description="Регионы (id локаций); пусто = весь мир; у war и plague обязательны."
    )
    NEUTRAL: ClassVar[dict] = {"cause": ""}


class EventEnd(Request):
    """Закончить глобальное событие."""

    type: Literal["event_end"]
    id: str = Field(description="Id события.")


class OfferChoices(Request):
    """Предложить игроку два-три варианта ответа."""

    type: Literal["offer_choices"]
    choices: list[str] = Field(description="Варианты ответа, два или три.")


class EndScene(Request):
    """Закрыть сцену."""

    type: Literal["end_scene"]
    summary: str = Field("", description="Краткая выжимка сцены; пусто = нет.")
    NEUTRAL: ClassVar[dict] = {"summary": ""}


class EndChapter(Request):
    """Закрыть главу."""

    type: Literal["end_chapter"]
    title: str = Field("", description="Название главы; пусто = нет.")
    NEUTRAL: ClassVar[dict] = {"title": ""}


class AfterlifeAction(Request):
    """Действие героя в посмертии."""

    type: Literal["afterlife_action"]
    kind: Literal["short", "long", "epic"] = Field(description="Тип действия.")


class UnsupportedAction(Request):
    """Игрок хочет то, чего в механике нет: движок запишет это в авто-репорт."""

    type: Literal["unsupported_action"]
    description: str = Field(description="Что хочет сделать игрок.")


# запросы роли world (режим "world"): служебные и версии запросов 2.1 с закадровыми полями

class WorldSkillCheck(SkillCheck):
    """Закадровая проверка навыка: бросает NPC (actor) или герой; движок бросает кубик."""

    actor: str = Field("", description="Id NPC, который бросает; пусто = герой.")
    NEUTRAL: ClassVar[dict] = {**SkillCheck.NEUTRAL, "actor": ""}


class WorldSavingThrow(SavingThrow):
    """Закадровый спасбросок: бросает NPC (actor) или герой; движок бросает кубик."""

    actor: str = Field("", description="Id NPC, который бросает; пусто = герой.")
    NEUTRAL: ClassVar[dict] = {**SavingThrow.NEUTRAL, "actor": ""}


class WorldNpcUpdate(NpcUpdateBase):
    """Закадровое изменение NPC: перемещение, отношение, смерть или уход (с причиной и броском)."""

    location_id: str = Field("", description="Id локации, куда NPC перемещается; пусто = нет.")
    then_ref: str = Field(description="ref кандидата, чьё then исполняется этим запросом.")
    NEUTRAL: ClassVar[dict] = {**NpcUpdateBase.NEUTRAL, "location_id": ""}


class VerdictItem(Request):
    ref: str = Field(description="ref кандидата verdict.")
    holds: bool = Field(description="Нарративное условие выполнено.")
    reason: str = Field(description="Короткая причина решения.")


class WorldVerdict(Request):
    """Вердикты по всем кандидатам verdict: по одному элементу на каждый ref, без лишних."""

    type: Literal["world_verdict"]
    items: list[VerdictItem] = Field(description="Вердикты по кандидатам verdict.")


class WorldNotice(Request):
    """Закадровая заметка: что герой может заметить, услышать или узнать."""

    type: Literal["world_notice"]
    text: str = Field(description="Текст заметки для игрока.")
    visibility: Literal["visible", "rumor", "hidden"] = Field(
        description="visible: заметно сразу, rumor: слух, hidden: только в хронике."
    )
    delay: Literal["none", "day", "week"] = Field(description="Когда доставить игроку.")
    refs: list[str] = Field([], description="ref кандидатов, о которых заметка; пусто = нет.")
    then_ref: str = Field("", description="ref кандидата, чьё then исполняется; пусто = нет.")
    NEUTRAL: ClassVar[dict] = {"then_ref": ""}


class WorldSetFlag(SetFlag):
    """Поставить флаг мира."""

    then_ref: str = Field("", description="ref кандидата, чьё then исполняется; пусто = нет.")
    NEUTRAL: ClassVar[dict] = {"then_ref": ""}


# служебные запросы роли summarizer (режимы summarize_*), вне закрытого списка 2.1
class SceneSummaryRequest(Request):
    """Выжимка закрытой сцены: что произошло, кто что обещал и решил."""

    type: Literal["scene_summary"]
    title: str = Field(description="Название сцены; пусто = нет.")
    summary: str = Field(description="Выжимка сцены, не пустая.")
    NEUTRAL: ClassVar[dict] = {"title": ""}


class ChapterSummaryRequest(Request):
    """Выжимка закрытой главы: что произошло, кто что обещал, какие нити открыты."""

    type: Literal["chapter_summary"]
    title: str = Field(description="Название главы; пусто = нет.")
    summary: str = Field(description="Выжимка главы, не пустая.")
    NEUTRAL: ClassVar[dict] = {"title": ""}


class GameSummaryRequest(Request):
    """Свёртка всей игры: прежний game_summary и глава переписываются целиком."""

    type: Literal["game_summary"]
    summary: str = Field(description="Новый game_summary целиком, не пустой.")


# служебные запросы режимов hero_background и hero_sheet: создание героя
class BackgroundFields(Request):
    name: str = Field(description="Название предыстории.")
    abilities: list[Ability] = Field(description="Ровно три разные характеристики.")
    skills: list[Skill] = Field(description="Ровно два разных навыка.")
    tool: str = Field(description="id инструмента из справочника.")
    feat: str = Field(description="id черты категории origin из справочника.")
    equipment: list[str] = Field(
        description="id предметов набора; повтор id = количество; вместе с gold_cp не дороже 50 зм."
    )
    gold_cp: int = Field(description="Золото набора в медяках.")
    description: str = Field(description="Краткая предыстория героя, до 300 символов; пусто = нет.")
    NEUTRAL: ClassVar[dict] = {"description": ""}


class BackgroundSpecRequest(BackgroundFields):
    """Предыстория героя по описанию игрока: характеристики, навыки, инструмент, черта, набор."""

    type: Literal["background_spec"]


class AbilityScores(Request):
    str_: int = Field(alias="str", description="Сила.")
    dex: int = Field(description="Ловкость.")
    con: int = Field(description="Телосложение.")
    int_: int = Field(alias="int", description="Интеллект.")
    wis: int = Field(description="Мудрость.")
    cha: int = Field(description="Харизма.")


class HeroTriggerSpec(Request):
    id: str = Field(description="Уникальный id возможности героя.")
    then: str = Field(description="Намерение: что произойдёт, когда условие выполнится.")
    kind: Literal[
        "narrative", "flag", "hero_has", "hero_at", "npc_status", "attitude", "favor"
    ] = Field(description="Вид единственного условия.")
    ref: str = Field(
        description="narrative: текст условия словами; flag: имя флага; hero_has: id предмета; "
        "hero_at: id локации; npc_status, attitude: id NPC; favor: id бога."
    )
    status: str = Field("", description="Только npc_status: нужный статус NPC; пусто = alive.")
    gte: int = Field(0, description="Только attitude и favor: порог не ниже; 0 = не задан.")
    NEUTRAL: ClassVar[dict] = {"status": "", "gte": 0}


class HeroSheetRequest(Request):
    """Лист героя 1 уровня по описанию игрока: выборы, предыстория, мотив, средства, возможности."""

    type: Literal["hero_sheet"]
    name: str = Field(description="Имя героя; не из taken_names.")
    gender: GenderOrNone = Field(
        "none", description="Пол героя по описанию игрока; не ясно -- по имени; none = не известен."
    )
    pronouns: str = Field(
        "", description="Местоимения героя, только если игрок их назвал; пусто = нет."
    )
    species_id: str = Field(description="id вида из справочника.")
    class_id: str = Field(description="id класса из справочника.")
    ability_method: Literal["standard_array", "point_buy", "explicit"] = Field(
        description="Метод характеристик: стандартный набор, покупка очков или свободные значения."
    )
    ability_scores: AbilityScores = Field(description="Характеристики до бонуса предыстории.")
    bonus_plus2: AbilityOrNone = Field(
        "none", description="Характеристика с бонусом +2; none = схема +1/+1/+1."
    )
    bonus_plus1: list[Ability] = Field(
        description="Характеристики с бонусом +1: одна при +2, три при +1/+1/+1."
    )
    class_skills: list[Skill] = Field(description="Навыки класса из skill_options класса.")
    weapon_masteries: list[str] = Field(description="id оружия для мастерства, mastery_count штук.")
    fighting_style: str = Field("", description="id боевого стиля, если он есть у класса.")
    class_kit: str = Field(description="id стартового набора класса из kits класса.")
    spells: list[str] = Field(description="id заговоров и заклинаний 1 круга класса; пусто = нет.")
    prepared: list[str] = Field(description="id подготовленных заклинаний из spells; пусто = нет.")
    species_skill: SkillOrNone = Field("none", description="Навык вида (Умелость); none = нет.")
    species_feat: str = Field("", description="id черты вида (Универсальность); пусто = нет.")
    feat_skills: list[str] = Field(
        description="Выборы черты предыстории (Одарённый: три навыка или инструмента); пусто = нет."
    )
    species_feat_skills: list[str] = Field(
        description="Выборы черты Универсальности (Одарённый: три); пусто = нет."
    )
    background: BackgroundFields = Field(description="Предыстория героя.")
    background_gear: Literal["equipment", "gold"] = Field(
        description="Вариант предыстории: equipment (набор и золото) или gold (50 зм)."
    )
    motive: str = Field(description="Мотив героя одним предложением.")
    means: list[str] = Field(description="Средства героя, от одного до трёх.")
    opportunity: list[HeroTriggerSpec] = Field(
        description="Возможности героя, от нуля до двух; пусто = нет."
    )
    NEUTRAL: ClassVar[dict] = {"fighting_style": "", "species_feat": "", "species_skill": "none",
                               "bonus_plus2": "none", "gender": "none", "pronouns": ""}


class SecretSpec(Request):
    id: str = Field(description="Уникальный id секрета NPC.")
    text: str = Field(description="Что скрыто: сам секрет.")
    kind: Literal[
        "narrative", "flag", "hero_has", "hero_at", "npc_status", "attitude", "favor"
    ] = Field(description="Вид единственного условия раскрытия.")
    ref: str = Field(
        description="narrative: текст условия словами; flag: имя флага; hero_has: id предмета; "
        "hero_at: id локации; npc_status, attitude: id NPC; favor: id бога."
    )
    status: str = Field("", description="Только npc_status: нужный статус NPC; пусто = alive.")
    gte: int = Field(0, description="Только attitude и favor: порог не ниже; 0 = не задан.")
    NEUTRAL: ClassVar[dict] = {"status": "", "gte": 0}


class PackLocation(Request):
    id: str = Field(description="Уникальный id локации, латиницей.")
    name: str = Field(description="Название; в одном родителе уникально.")
    parent_id: str = Field("", description="Id родительской локации пака; пусто = нет.")
    description: str = Field("", description="Описание локации; пусто = нет.")
    connections: list[ConnectionSpec] = Field(
        [], description="Связи с другими локациями пака; пусто = нет."
    )
    NEUTRAL: ClassVar[dict] = {"parent_id": "", "description": ""}


class PackNpc(Request):
    id: str = Field(description="Уникальный id NPC, латиницей.")
    name: str = Field(description="Имя; у именованных NPC уникально.")
    means: list[str] = Field(description="Средства NPC, от одного до трёх.")
    named: bool = Field(False, description="Именованный NPC.")
    key: bool = Field(False, description="Ключевой NPC.")
    motive: str = Field("", description="Мотив NPC; пусто = нет.")
    location_id: str = Field("", description="Id локации пака, где NPC находится; пусто = нет.")
    trade_kind: str = Field(
        "none", description="Тип торговца (пресет ассортимента), если NPC торгует; none = нет."
    )
    species_id: str = Field("", description="Id вида из справочника; пусто = не задан.")
    gender: GenderOrNone = Field(
        "none", description="Пол NPC: male, female, other; none = не известен."
    )
    pronouns: str = Field(
        "", description="Местоимения/обращение, если отличаются от пола или важны; пусто = нет."
    )
    opportunity: list[HeroTriggerSpec] = Field(
        [], description="Возможности NPC: что он сделает при условии; пусто = нет."
    )
    secrets: list[SecretSpec] = Field([], description="Секреты NPC и раскрытие; пусто = нет.")
    NEUTRAL: ClassVar[dict] = {
        "motive": "", "location_id": "", "trade_kind": "none", "species_id": "",
        "gender": "none", "pronouns": ""
    }


class PackFaction(Request):
    id: str = Field(description="Уникальный id фракции, латиницей.")
    name: str = Field(description="Название; уникально.")
    motive: str = Field("", description="Мотив фракции; пусто = нет.")
    means: list[str] = Field([], description="Средства фракции; пусто = нет.")
    members: list[str] = Field([], description="Id NPC пака, входящих во фракцию; пусто = нет.")
    regions: list[str] = Field([], description="Id локаций пака, где фракция действует.")
    opportunity: list[HeroTriggerSpec] = Field([], description="Возможности фракции; пусто = нет.")
    NEUTRAL: ClassVar[dict] = {"motive": ""}


class PackGod(Request):
    id: str = Field(description="Уникальный id бога, латиницей.")
    name: str = Field(description="Имя; уникально.")
    domains: list[str] = Field([], description="Домены бога; пусто = нет.")
    role: str = Field("", description="Роль в пантеоне; пусто = нет.")
    motive: str = Field("", description="Мотив бога; пусто = нет.")
    pleased_by: list[str] = Field([], description="Что нравится богу; пусто = нет.")
    angered_by: list[str] = Field([], description="Что гневит бога; пусто = нет.")
    rivals: list[str] = Field([], description="Id богов-соперников пака; пусто = нет.")
    means: list[str] = Field([], description="Средства бога; пусто = нет.")
    realm: str = Field("", description="Обитель бога; пусто = нет.")
    servants: list[str] = Field([], description="Id NPC пака, служащих богу; пусто = нет.")
    opportunity: list[HeroTriggerSpec] = Field([], description="Возможности бога; пусто = нет.")
    NEUTRAL: ClassVar[dict] = {"role": "", "motive": "", "realm": ""}


class PackStart(Request):
    date: str = Field(description="Дата начала YYYY-MM-DD в календаре 12 месяцев по 30 дней.")
    time: str = Field("08:00", description="Время начала HH:MM.")
    hero_location: str = Field(description="Id локации пака, где стартует герой.")
    chapter_number: int = Field(1, description="Номер стартовой главы.")
    chapter_title: str = Field("", description="Название стартовой главы; пусто = нет.")
    scene_summary: str = Field("", description="Положение дел на старте (стартовая сцена).")
    NEUTRAL: ClassVar[dict] = {"chapter_title": "", "scene_summary": ""}


def tone_axis(name):
    # значения оси тона из Tone (один источник) без пустого: пусто = none (в enum нет "")
    values = [value for value in get_args(Tone.model_fields[name].annotation) if value]
    return Literal[(*values, "none")]


class PackTone(Request):
    mood: str = Field("", description="Настроение, жанр одной фразой; пусто = нет.")
    violence: tone_axis("violence") = Field("none", description="Насилие; none = не задано.")
    horror: tone_axis("horror") = Field("none", description="Ужас; none = не задано.")
    romance: tone_axis("romance") = Field("none", description="Романтика; none = не задано.")
    language: tone_axis("language") = Field("none", description="Язык; none = не задано.")
    hard_limits: list[str] = Field([], description="Чего в игре не будет; пусто = нет.")
    soft_limits: list[str] = Field([], description="Чего лучше избегать; пусто = нет.")
    notes: str = Field("", description="Свободный текст стиля; пусто = нет.")
    NEUTRAL: ClassVar[dict] = {
        "violence": "none", "horror": "none", "romance": "none", "language": "none"
    }

    @field_validator("violence", "horror", "romance", "language", mode="before")
    @classmethod
    def empty_axis_is_none(cls, value):
        # в схеме пустой оси нет (Gemini не принимает "" в enum), но "" как «не задано» принимается
        return "none" if value == "" else value


class PackRequest(Request):
    """Пак кампании по текстовой выжимке: мир, локации, NPC, фракции, пантеон, старт и тон."""

    type: Literal["pack"]
    name: str = Field(description="Название кампании.")
    start: PackStart = Field(description="Старт кампании.")
    tone: PackTone = Field(description="Тон кампании.")
    world_text: str = Field(description="Описание мира: история, атмосфера.")
    truths: str = Field("", description="Неизменные факты мира; пусто = нет.")
    locations: list[PackLocation] = Field(description="Локации пака, не меньше одной.")
    npcs: list[PackNpc] = Field([], description="NPC пака; пусто = нет.")
    factions: list[PackFaction] = Field([], description="Фракции пака; пусто = нет.")
    pantheon: list[PackGod] = Field([], description="Боги пака; пусто = нет.")
    NEUTRAL: ClassVar[dict] = {"truths": ""}


REQUEST_MODELS = {
    "skill_check": SkillCheck,
    "saving_throw": SavingThrow,
    "start_combat": StartCombat,
    "player_action": PlayerAction,
    "npc_action": NpcAction,
    "defeat_outcome": DefeatOutcome,
    "end_combat": EndCombat,
    "damage": Damage,
    "curse": Curse,
    "give_item": GiveItem,
    "give_custom_item": GiveCustomItem,
    "use_item": UseItem,
    "cast_spell": CastSpell,
    "take_item": TakeItem,
    "trade": Trade,
    "haggle": Haggle,
    "service": Service,
    "gold": Gold,
    "award_xp": AwardXp,
    "advance_time": AdvanceTime,
    "rest": Rest,
    "warn_danger": WarnDanger,
    "set_flag": SetFlag,
    "npc_create": NpcCreate,
    "location_create": LocationCreate,
    "npc_update": NpcUpdate,
    "favor_change": FavorChange,
    "pray": Pray,
    "change_deity": ChangeDeity,
    "companion_update": CompanionUpdate,
    "reveal_secret": RevealSecret,
    "knowledge_note": KnowledgeNote,
    "scene_mood": SceneMood,
    "event_start": EventStart,
    "event_end": EventEnd,
    "offer_choices": OfferChoices,
    "end_scene": EndScene,
    "end_chapter": EndChapter,
    "afterlife_action": AfterlifeAction,
    "unsupported_action": UnsupportedAction,
}

ALL_TYPES = tuple(REQUEST_MODELS)

# модели режима world: служебные (world_verdict, world_notice) и версии запросов 2.1
WORLD_MODELS = {
    "world_verdict": WorldVerdict,
    "world_notice": WorldNotice,
    "skill_check": WorldSkillCheck,
    "saving_throw": WorldSavingThrow,
    "npc_update": WorldNpcUpdate,
    "set_flag": WorldSetFlag,
    "favor_change": FavorChange,
    "event_start": EventStart,
    "event_end": EventEnd,
    "warn_danger": WarnDanger,
}

SUMMARY_MODELS = {
    "scene_summary": SceneSummaryRequest,
    "chapter_summary": ChapterSummaryRequest,
    "game_summary": GameSummaryRequest,
}

HERO_MODELS = {
    "hero_background": {"background_spec": BackgroundSpecRequest},
    "hero_sheet": {"hero_sheet": HeroSheetRequest},
}

IMPORT_MODELS = {"pack": PackRequest}

HIDDEN_TYPES = ("afterlife_action",)
NPC_ONLY_TYPES = ("npc_action",)
VISIBLE_TYPES = tuple(
    name for name in ALL_TYPES if name not in HIDDEN_TYPES and name not in NPC_ONLY_TYPES
)

MasterRequest = Annotated[
    SkillCheck | SavingThrow | StartCombat | PlayerAction | NpcAction | DefeatOutcome | EndCombat
    | Damage | Curse | GiveItem | GiveCustomItem | UseItem | CastSpell | TakeItem | Trade | Haggle
    | Service | Gold | AwardXp
    | AdvanceTime | Rest
    | WarnDanger
    | SetFlag | NpcCreate | LocationCreate | NpcUpdate | FavorChange | Pray | ChangeDeity
    | CompanionUpdate | RevealSecret | KnowledgeNote | SceneMood | EventStart | EventEnd
    | OfferChoices | EndScene | EndChapter | AfterlifeAction | UnsupportedAction,
    Field(discriminator="type"),
]

REQUEST_ADAPTER = TypeAdapter(MasterRequest)

WorldRequest = Annotated[
    WorldVerdict | WorldNotice | WorldSkillCheck | WorldSavingThrow | WorldNpcUpdate | WorldSetFlag
    | FavorChange | NpcCreate | LocationCreate | EventStart | EventEnd | WarnDanger,
    Field(discriminator="type"),
]

WORLD_ADAPTER = TypeAdapter(WorldRequest)

SummaryRequest = Annotated[
    SceneSummaryRequest | ChapterSummaryRequest | GameSummaryRequest,
    Field(discriminator="type"),
]

SUMMARY_ADAPTER = TypeAdapter(SummaryRequest)

HERO_MODES = ("hero_background", "hero_sheet")

HERO_ADAPTERS = {
    "hero_background": TypeAdapter(BackgroundSpecRequest),
    "hero_sheet": TypeAdapter(HeroSheetRequest),
}


IMPORT_MODE = "pack_import"

IMPORT_ADAPTER = TypeAdapter(PackRequest)


def parse_request(data: dict, mode: str = "explore"):
    if mode == IMPORT_MODE:
        return IMPORT_ADAPTER.validate_python(data)
    if mode in HERO_MODES:
        return HERO_ADAPTERS[mode].validate_python(data)
    if mode.startswith("summarize_"):
        return SUMMARY_ADAPTER.validate_python(data)
    if mode == "world":
        return WORLD_ADAPTER.validate_python(data)
    return REQUEST_ADAPTER.validate_python(data)
