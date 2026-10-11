from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ai_dm.content.models.common import Ability
from ai_dm.core.dice import parse_dice
from ai_dm.state.creature import CreatureState, Equipment
from ai_dm.state.hero import InventoryEntry

Intent = Literal["kill", "capture", "rob", "drive_off", "spare"]
Outcome = Literal[
    "victory", "defeat_pending", "hero_dying", "hero_dead", "fled", "ended_by_master"
]


class ZoneFeature(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # механические: cover_half, cover_three_quarters, difficult, hazard; остальные -- без механики
    kind: str
    damage: str | None = None
    damage_type: str = "fire"
    save: Ability | None = None
    dc: int = 10

    @model_validator(mode="after")
    def check_hazard(self):
        if self.kind == "hazard":
            if self.damage is None or self.save is None:
                raise ValueError("hazard: нужны damage и save")
            parse_dice(self.damage)
        return self


class Zone(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    name: str
    adjacent: list[str]
    features: list[ZoneFeature] = Field(default_factory=list)
    exit: bool = False
    # высота: 0 -- земля, >0 -- выше (стена, крыша), <0 -- ниже (яма, овраг)
    elevation: int = 0
    # место на карте боя [ряд, колонка]; None -- раскладка по графу смежности
    pos: list[int] | None = None


class MoveRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ref: str
    from_zone: str
    to_zone: str
    # длина лога на момент перемещения: по ней движение привязывается к ходам
    log_index: int


class GroundItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    item_id: str
    zone_id: str
    # у кого выбили (герой или участник); None -- ничей
    owner_ref: str | None = None
    qty: int = 1
    cost_cp: int
    quality: Literal["junk", "worn", "used"] | None = None


class TurnState(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: bool = True
    bonus: bool = True
    reaction: bool = True
    # сколько зон ещё можно пройти
    move: int = 1
    disengaged: bool = False
    # сколько атак ещё можно сделать без траты действия (Дополнительная атака)
    attacks_left: int = 0
    # Убийца колоссов уже сработал в этом ходу
    colossus_used: bool = False
    # свободное взаимодействие с предметом (подобрать с земли) ещё не потрачено
    free_interaction: bool = True


class Participant(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ref: str
    side: Literal["heroes", "enemies"]
    group_id: str
    zone_id: str | None = None
    initiative: int | None = None
    turn: TurnState = Field(default_factory=TurnState)
    controller: Literal["engine", "auto_hero", "external"] = "engine"
    status: Literal["active", "down", "dead", "fled", "surrendered"] = "active"
    monster_id: str | None = None
    intent: Intent | None = None
    surprised: bool = False
    last_hit_by: str | None = None
    # состояние безымянного монстра (герой и именованный NPC хранят своё в другом месте)
    creature: CreatureState | None = None
    name: str = ""
    # None -- не задано, по статблоку
    equipment: Equipment | None = None


class Group(BaseModel):
    model_config = ConfigDict(extra="forbid")
    leader_id: str
    intent: Intent | None = None
    lair_location_id: str | None = None


class CombatState(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    zones: list[Zone]
    participants: list[Participant]
    groups: dict[str, Group]
    round: int = 0
    turn_index: int = 0
    initiative_order: list[str] = Field(default_factory=list)
    budget_override_reason: str | None = None
    outcome: Outcome | None = None
    log: list[str] = Field(default_factory=list)
    # перемещения участников между зонами (для строки «Движение» на карте боя)
    moves: list[MoveRecord] = Field(default_factory=list)
    # группа, чьё намерение применено при падении героя (последний удар)
    defeat_group_id: str | None = None
    # герои, уже бросавшие кубики Savage Attacker в этом ходу (раз за любой ход)
    savage_used: list[str] = Field(default_factory=list)
    # ключевые NPC, которых модель уже спрашивали про ход в этом бою (один раз за бой)
    consulted: list[str] = Field(default_factory=list)
    # чей ход уже начат (start_turn выполнен), но ещё не отыгран: step не начинает его заново
    turn_started_for: str | None = None
    # оружие на земле (выбитое), по зонам
    ground_items: list[GroundItem] = Field(default_factory=list)
    # оружие и квестовые вещи с тел врагов, считается при конце боя
    gear: list[InventoryEntry] = Field(default_factory=list)


class DecisionPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["turn_action", "intent_reconsider"]
    actor: str
    options: list[str]
    subject: str | None = None
    attacker: str | None = None
