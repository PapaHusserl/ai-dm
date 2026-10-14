from typing import Literal

from pydantic import field_validator, model_validator

from ai_dm.content.models.common import ABILITIES, Ability, ContentModel, ContentObject


class HitRider(ContentModel):
    # эффект при попадании: спасбросок цели (без save -- сразу), состояние, урон при провале
    condition: str
    save: Ability | None = None
    dc: int | None = None
    # цель крупнее -- эффекта нет
    max_size: Literal["tiny", "small", "medium", "large", "huge", "gargantuan"] | None = None
    # target_turn -- до конца следующего хода цели, source_turn -- до конца следующего хода
    # бьющего, minute -- 10 раундов; None -- пока не снимут (лежит)
    duration: Literal["target_turn", "source_turn", "minute"] | None = None
    dice: str | None = None
    damage_type: str | None = None
    # на кого не действует: тип существа монстра или id вида героя (упырь: нежить и эльфы)
    exempt: list[str] = []

    @model_validator(mode="after")
    def check_pairs(self):
        if (self.save is None) != (self.dc is None):
            raise ValueError("on_hit: save и dc вместе")
        if (self.dice is None) != (self.damage_type is None):
            raise ValueError("on_hit: dice и damage_type вместе")
        return self


class MonsterAction(ContentModel):
    name: str
    description: str = ""
    kind: str = "melee"
    attack_bonus: int | None = None
    damage_dice: str | None = None
    damage_type: str | None = None
    # дополнительный урон того же типа, если бросок атаки был с преимуществом
    advantage_damage_dice: str | None = None
    # доп. урон другого типа при каждом попадании (укус упыря: колющий и некротический)
    extra_damage_dice: str | None = None
    extra_damage_type: str | None = None
    on_hit: HitRider | None = None
    reach_ft: int | None = None
    range_normal_ft: int | None = None
    range_long_ft: int | None = None
    # оружие из srd/data/weapons, если действие -- удар предметом (его можно выбить)
    weapon_id: str | None = None

    @model_validator(mode="after")
    def check_extra(self):
        if (self.extra_damage_dice is None) != (self.extra_damage_type is None):
            raise ValueError("extra_damage_dice и extra_damage_type вместе")
        return self


class DeathBurst(ContentModel):
    # предсмертный взрыв: все в зоне, спасбросок, половина урона при успехе
    save: Ability = "dex"
    dc: int
    dice: str
    damage_type: str


class MultiattackStep(ContentModel):
    action: str
    count: int


class Monster(ContentObject):
    ac: int
    hp: int
    cr: str
    abilities: dict[Ability, int]
    hp_dice: str | None = None
    size: str = "medium"
    creature_type: str = ""
    speed_ft: int = 30
    # скорость полёта; парит и не падает, пока дееспособен
    fly_ft: int = 0
    traits: list[str] = []
    # теги вроде mor (твари Мора)
    tags: list[str] = []
    actions: list[MonsterAction] = []
    multiattack: list[MultiattackStep] = []
    damage_immunities: list[str] = []
    damage_resistances: list[str] = []
    damage_vulnerabilities: list[str] = []
    condition_immunities: list[str] = []
    # что надето по SRD; equipment участника/NPC переопределяет вклад доспеха и щита
    armor: str | None = None
    shield: str | None = None
    death_burst: DeathBurst | None = None

    @field_validator("abilities")
    @classmethod
    def check_abilities(cls, value):
        if set(value) != set(ABILITIES):
            raise ValueError("abilities: нужны все шесть характеристик")
        return value

    @field_validator("damage_immunities", "damage_resistances", "damage_vulnerabilities")
    @classmethod
    def check_duplicates(cls, value):
        if len(set(value)) != len(value):
            raise ValueError("повторы типов урона")
        return value

    @model_validator(mode="after")
    def check_multiattack(self):
        names = [a.name for a in self.actions]
        for step in self.multiattack:
            if step.action not in names:
                raise ValueError(f"multiattack: нет действия '{step.action}'")
        return self
