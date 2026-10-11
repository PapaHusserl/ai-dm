from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ai_dm.state.creature import CreatureState
from ai_dm.state.death import DeathRecord
from ai_dm.state.triggers import Trigger


class BackgroundSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    abilities: list[str]
    skills: list[str]
    tool: str
    feat: str
    equipment: list[str] = Field(default_factory=list)
    gold_cp: int = 0
    gold_option_cp: int = 5000
    description: str = ""


class ClassLevel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    class_id: str
    level: int = Field(default=1, ge=1)
    subclass_id: str | None = None


class GrantedSpell(BaseModel):
    model_config = ConfigDict(extra="forbid")
    spell_id: str
    source: str
    class_id: str | None = None
    ability: str | None = None
    pool: str | None = None


class CharacterSheet(BaseModel):
    model_config = ConfigDict(extra="forbid")
    species_id: str
    # первый класс -- стартовый
    classes: list[ClassLevel] = Field(min_length=1)
    # class_id на каждом уровне персонажа
    level_history: list[str]
    background: BackgroundSpec
    abilities: dict[str, int]
    skill_proficiencies: list[str] = Field(default_factory=list)
    tool_proficiencies: list[str] = Field(default_factory=list)
    feats: list[str] = Field(default_factory=list)
    weapon_masteries: list[str] = Field(default_factory=list)
    # class_id -> заклинания
    spells_known: dict[str, list[str]] = Field(default_factory=dict)
    spells_prepared: dict[str, list[str]] = Field(default_factory=dict)
    spells_always_prepared: list[GrantedSpell] = Field(default_factory=list)
    xp: int = 0
    # навыки с экспертизой (бонус мастерства удваивается)
    skill_expertise: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    # выбор умения с вариантами: id умения -> id вариантов (hunters_prey -> [colossus_slayer])
    feature_choices: dict[str, list[str]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def check_classes(self):
        # проверка только при создании и загрузке: validate_assignment не включать --
        # apply_level меняет level и level_history по очереди
        ids = [c.class_id for c in self.classes]
        if len(set(ids)) != len(ids):
            raise ValueError("классы героя повторяются")
        if len(self.level_history) != self.level:
            raise ValueError("level_history не равна уровню")
        return self

    @property
    def primary(self) -> ClassLevel:
        return self.classes[0]

    @property
    def class_id(self) -> str:
        return self.classes[0].class_id

    @property
    def subclass_id(self) -> str | None:
        return self.classes[0].subclass_id

    @property
    def level(self) -> int:
        return sum(c.level for c in self.classes)

    def class_level(self, class_id: str) -> int:
        for entry in self.classes:
            if entry.class_id == class_id:
                return entry.level
        return 0

    def prepared_of(self, class_id: str | None = None) -> list[str]:
        return self.spells_prepared.setdefault(class_id or self.class_id, [])

    def known_of(self, class_id: str | None = None) -> list[str]:
        return self.spells_known.setdefault(class_id or self.class_id, [])


class LevelChoices(BaseModel):
    # выборы героя на одном уровне; пустые поля -- «не выбирается»
    model_config = ConfigDict(extra="forbid")
    level: int
    fighting_style: str | None = None
    expertise: list[str] = Field(default_factory=list)
    subclass_id: str | None = None
    # id умения с вариантами -> id вариантов (hunters_prey -> [colossus_slayer])
    feature_choices: dict[str, list[str]] = Field(default_factory=dict)
    # повышение характеристик: {"dex": 2} или {"dex": 1, "wis": 1}
    asi: dict[str, int] | None = None
    feat: str | None = None
    spells_add: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)

    @field_validator("expertise", "languages", mode="before")
    @classmethod
    def one_to_list(cls, value):
        if isinstance(value, str):
            return [value]
        return value


class PendingLevel(BaseModel):
    # уровень, начатый в меню, но ещё не применённый (уровень и HP меняются при commit)
    model_config = ConfigDict(extra="forbid")
    class_id: str
    hp_gain: int = Field(ge=1)
    draft: LevelChoices


class Companion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    kind: str
    notes: str = ""


class InventoryEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    item_id: str
    qty: int = 1
    # цена одной вещи этого стека; стек = одинаковые (item_id, cost_cp, quality)
    cost_cp: int
    quality: Literal["junk", "worn", "used"] | None = None


class Equipped(BaseModel):
    model_config = ConfigDict(extra="forbid")
    armor: str | None = None
    shield: str | None = None
    main_hand: str | None = None
    off_hand: str | None = None


class DivineState(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # боги, чья благосклонность заморожена до выплаты долга
    frozen: list[str] = Field(default_factory=list)
    debts: list[str] = Field(default_factory=list)
    # id главы, где бог уже вмешался (раз за главу), и бог, который вмешался последним
    intervention_chapter: str | None = None
    intervention_god: str | None = None
    # id долга -> id сцены вмешательства: в ней долг снять нельзя
    debt_scene: dict[str, str] = Field(default_factory=dict)
    # бог, которому герой молился (преимущество только от него)
    prayer_god: str | None = None
    prayer_day: int | None = None
    prayer_used_day: int | None = None
    curse_day_used: int | None = None


class HeroState(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    ordinal: int
    name: str
    sheet: CharacterSheet
    creature: CreatureState
    status: Literal["active", "dead", "retired", "in_afterlife", "ascended", "gone"] = "active"
    fate: str | None = None
    death: DeathRecord | None = None
    inventory: list[InventoryEntry] = Field(default_factory=list)
    equipped: Equipped = Field(default_factory=Equipped)
    money_cp: int = 0
    motive: str = ""
    means: list[str] = Field(default_factory=list)
    opportunity: list[Trigger] = Field(default_factory=list)
    favor: dict[str, int] = Field(default_factory=dict)
    deity_id: str | None = None
    divine: DivineState = Field(default_factory=DivineState)
    birth_s: int | None = None
    scars: list[str] = Field(default_factory=list)
    heroic_inspiration: bool = False
    location_id: str | None = None
    afterlife: dict | None = None
    legacy_links: list[str] = Field(default_factory=list)
    # звери-спутники (Повелитель зверей)
    companions: list[Companion] = Field(default_factory=list)
    attuned: list[str] = Field(default_factory=list)
    pending_level: PendingLevel | None = None

    @field_validator("favor")
    @classmethod
    def check_favor(cls, value):
        for god, number in value.items():
            if not -10 <= number <= 10:
                raise ValueError(f"благосклонность {god!r}: {number} вне -10..10")
        return value
