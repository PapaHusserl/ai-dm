from pydantic import field_validator, model_validator

from ai_dm.content.models.common import ABILITIES, Ability, ContentModel, ContentObject


class MonsterAction(ContentModel):
    name: str
    description: str = ""
    kind: str = "melee"
    attack_bonus: int | None = None
    damage_dice: str | None = None
    damage_type: str | None = None
    # дополнительный урон того же типа, если бросок атаки был с преимуществом
    advantage_damage_dice: str | None = None
    reach_ft: int | None = None
    range_normal_ft: int | None = None
    range_long_ft: int | None = None
    # оружие из srd/data/weapons, если действие -- удар предметом (его можно выбить)
    weapon_id: str | None = None


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
