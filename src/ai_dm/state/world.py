from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ai_dm.content.models.common import Ability, DcCategory
from ai_dm.core.clock import GameClock
from ai_dm.core.duration import Duration
from ai_dm.core.rng import RngState
from ai_dm.state.creature import CreatureState, Equipment
from ai_dm.state.death import DeathRecord
from ai_dm.state.gender import Gender
from ai_dm.state.hero import InventoryEntry
from ai_dm.state.relations import FamilyLink, NpcGoal, NpcSceneMemory
from ai_dm.state.triggers import Condition, Secret, Trigger


class Tone(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # "" = не задано
    mood: str = ""
    violence: Literal["", "мягко", "реалистично", "жестоко"] = ""
    horror: Literal["", "нет", "умеренно", "сильно"] = ""
    romance: Literal["", "нет", "намёки", "чувственно", "откровенно"] = ""
    language: Literal["", "сдержанно", "грубо"] = ""
    hard_limits: list[str] = Field(default_factory=list)
    soft_limits: list[str] = Field(default_factory=list)
    # свободный текст стиля
    notes: str = ""


class EventHazard(BaseModel):
    model_config = ConfigDict(extra="forbid")
    save: Ability
    dc_category: DcCategory


class GlobalEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    type: str
    regions: list[str] = Field(default_factory=list)
    affects: list[str] = Field(default_factory=list)
    mortality_multiplier: int = Field(default=1, ge=0)
    hazard: EventHazard | None = None
    started_s: int | None = None
    ends_at_s: int | None = None
    ends_when: Condition | None = None
    cause: str | None = None
    kind: Literal["natural", "caused"] = "caused"


class TradeProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # пресет ассортимента из конфига ([trade.presets.<kind>])
    kind: str
    # деньги торговца на скупку; пополняются при restock_at_s <= now
    purse_cp: int = Field(default=0, ge=0)
    restock_at_s: int = 0
    # купленное у героя (перепродаётся по цене экземпляра); сюжетные сюда не кладутся
    stock: list[InventoryEntry] = Field(default_factory=list)
    # торг Убеждением: поправка цены в процентах до конца игрового дня haggle_day
    haggle_percent: int = 0
    # номер игрового дня последнего торга; None -- не торговались
    haggle_day: int | None = None


class NPC(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    name: str
    named: bool = False
    key: bool = False
    status: Literal["alive", "dead", "gone", "changed"] = "alive"
    death: DeathRecord | None = None
    motive: str = ""
    means: list[str] = Field(min_length=1, max_length=3)
    opportunity: list[Trigger] = Field(default_factory=list)
    attitude: int = Field(default=0, ge=-100, le=100)
    known_to_player: list[str] = Field(default_factory=list)
    secrets: list[Secret] = Field(default_factory=list)
    combat: dict | None = None
    creature: CreatureState | None = None
    location_id: str | None = None
    # id героя, с которым NPC идёт (путь героя переносит и его); None -- сам по себе
    follows: str | None = None
    species_id: str | None = None
    # None -- пол не известен; pronouns -- местоимения/обращение, если важны ("" = нет)
    gender: Gender | None = None
    pronouns: str = ""
    birth_s: int | None = None
    # группы для affects событий; боевая группа совпадает с группой мира
    groups: list[str] = Field(default_factory=list)
    aging_steps: int = 0
    favor: dict[str, int] = Field(default_factory=dict)
    # память о герое: сцены с событиями (до лимита, у каждой вес) и долгие цели
    memory: list[NpcSceneMemory] = Field(default_factory=list)
    goals: list[NpcGoal] = Field(default_factory=list)
    # имя, под которым NPC известен герою; None -- не представился
    known_name: str | None = None
    family: list[FamilyLink] = Field(default_factory=list)
    # заметки о NPC для рассказчика (свободный текст; бывший relations_text)
    notes: str = ""
    # id услуг (код -- У0)
    services: list[str] = Field(default_factory=list)
    # теги существа (mor -- тварь Мора)
    tags: list[str] = Field(default_factory=list)
    origin: Literal["pack", "ai", "engine"] = "pack"
    # торговец: None -- не торгует
    trade: TradeProfile | None = None
    # None -- не задано, по статблоку
    equipment: Equipment | None = None

    @field_validator("favor")
    @classmethod
    def check_favor(cls, value):
        for god, number in value.items():
            if not -10 <= number <= 10:
                raise ValueError(f"благосклонность {god!r}: {number} вне -10..10")
        return value


class Faction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    name: str
    motive: str = ""
    means: list[str] = Field(default_factory=list)
    opportunity: list[Trigger] = Field(default_factory=list)
    members: list[str] = Field(default_factory=list)
    regions: list[str] = Field(default_factory=list)


class God(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    name: str
    domains: list[str] = Field(default_factory=list)
    role: str = ""
    motive: str = ""
    pleased_by: list[str] = Field(default_factory=list)
    angered_by: list[str] = Field(default_factory=list)
    rivals: list[str] = Field(default_factory=list)
    means: list[str] = Field(default_factory=list)
    opportunity: list[Trigger] = Field(default_factory=list)
    realm: str = ""
    # id NPC-слуг
    servants: list[str] = Field(default_factory=list)
    # как часто проверяются триггеры бога (ТЗ 4.2)
    check_every_days: int = Field(default=7, ge=1)
    # имя сезона календаря -> поправка шанса вмешательства в процентных пунктах
    season_power: dict[str, int] = Field(default_factory=dict)
    status: str = "alive"
    origin: Literal["pack", "ascended"] = "pack"


class Connection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    to: str
    distance_m: int = Field(ge=0)


class Location(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    name: str
    parent_id: str | None = None
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    connections: list[Connection] = Field(default_factory=list)
    visited: bool = False
    origin: str = "pack"


class NaturalEventKind(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: str
    mortality_multiplier: int = Field(default=1, ge=0)
    hazard: EventHazard | None = None
    duration: str = "30d"
    # id локаций
    regions: list[str] = Field(default_factory=list)

    @field_validator("duration")
    @classmethod
    def check_duration(cls, value):
        Duration.parse(value)
        return value


class NaturalEventsSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    chance_percent_per_season: int = Field(default=5, ge=0, le=100)
    kinds: list[NaturalEventKind] = Field(default_factory=list)


class Lore(BaseModel):
    model_config = ConfigDict(extra="forbid")
    world_text: str = ""
    truths: str = ""


class NudgeState(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scenes_off_main: int = 0
    stage: int = Field(default=0, ge=0, le=3)
    waiting: bool = True
    # NPC, который на ступени 2 выходит на героя (сигнал нарратору); пусто -- нет
    contact_npc: str = ""
    # значения флагов условий основной линии на прошлой границе (для касания по изменению флага)
    flags_seen: dict[str, bool | int | str | None] = Field(default_factory=dict)


class WorldSim(BaseModel):
    model_config = ConfigDict(extra="forbid")
    last_day: int = 0
    last_season: str = ""
    last_year: int = 0
    nudge: NudgeState = Field(default_factory=NudgeState)
    world_calls_today: int = 0
    # игровой день (now_s // 86400), к которому относится world_calls_today; -1 -- счёта нет
    world_calls_day: int = -1
    # god_id -> время (с) последней проверки триггеров бога (ТЗ 4.2: боги проверяются реже)
    god_checked_s: dict[str, int] = Field(default_factory=dict)
    # действия мира, отложенные до границы (46)
    pending_acts: list[str] = Field(default_factory=list)
    # время (с) последней проверки триггеров целей NPC; None -- ещё не проверялись (Ж2)
    goals_checked_s: int | None = None


class DangerMark(BaseModel):
    model_config = ConfigDict(extra="forbid")
    location_id: str
    text: str
    at_s: int


class Notice(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    at_s: int
    deliver_at_s: int
    visibility: Literal["visible", "rumor", "hidden"]
    text: str
    refs: list[str] = Field(default_factory=list)


class FiredTrigger(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ref: str
    at_s: int


class ItemHolder(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["npc", "band", "faction", "location"]
    # id NPC / фракции / локации; для band -- id лидера группы боя
    ref: str
    # как держателя видит мастер
    label: str = Field(max_length=80)
    # где искать: логово группы или локация боя
    location_id: str | None = None
    since_s: int
    qty: int = 1
    # цена одной вещи: вернуть с той же ценой
    cost_cp: int = 0


class CustomItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    name: str
    description: str = ""
    # вес в сотых долях фунта (в сейве нет float): 0.5 фнт = 50
    weight_centilb: int | None = None
    cost_cp: int = 0
    quest: bool = False
    created_s: int
    # None -- предмет у героя или в обороте
    holder: ItemHolder | None = None


class WorldState(BaseModel):
    model_config = ConfigDict(extra="forbid")
    world_id: str
    rng: RngState
    campaign_id: str | None = None
    campaign_version: str | None = None
    clock: GameClock = Field(default_factory=GameClock)
    npcs: dict[str, NPC] = Field(default_factory=dict)
    factions: dict[str, Faction] = Field(default_factory=dict)
    pantheon: dict[str, God] = Field(default_factory=dict)
    locations: dict[str, Location] = Field(default_factory=dict)
    flags: dict[str, bool | int | str] = Field(default_factory=dict)
    events: list[GlobalEvent] = Field(default_factory=list)
    tone: Tone = Field(default_factory=Tone)
    settings: dict[str, int | str | bool] = Field(default_factory=dict)
    lore: Lore = Field(default_factory=Lore)
    sim: WorldSim = Field(default_factory=WorldSim)
    mortality_per_day: int = Field(default=20000, ge=1)
    natural: NaturalEventsSpec = Field(default_factory=NaturalEventsSpec)
    nudge_scenes: int = Field(default=8, ge=1)
    dangers: list[DangerMark] = Field(default_factory=list)
    notices: list[Notice] = Field(default_factory=list)
    fired: list[FiredTrigger] = Field(default_factory=list)
    custom_items: dict[str, CustomItem] = Field(default_factory=dict)
    custom_item_seq: int = 0

    @field_validator("npcs", "factions", "pantheon", "locations", "custom_items")
    @classmethod
    def check_keys(cls, value):
        for key, obj in value.items():
            if key != obj.id:
                raise ValueError(f"ключ {key!r} не совпадает с id {obj.id!r}")
        return value
