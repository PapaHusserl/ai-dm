from typing import Literal

from ai_dm.content.models.common import Behavior, ContentObject, EffectSpec

Rarity = Literal["common", "uncommon", "rare", "very_rare", "legendary", "artifact"]


class Weapon(ContentObject):
    category: Literal["simple", "martial"]
    kind: Literal["melee", "ranged"]
    damage_dice: str
    damage_type: str
    cost_cp: int
    properties: list[str] = []
    mastery: str | None = None
    versatile_dice: str | None = None
    range_normal_ft: int | None = None
    range_long_ft: int | None = None
    # особые эффекты оружия (Клинок Северного Ветра)
    effects: list[EffectSpec] = []
    # id предмета-боеприпаса, который тратит выстрел (у оружия со свойством ammunition)
    ammo: str | None = None
    # огнестрел: не продаётся в лавках и не выбирается при создании героя (только пак или выдача)
    world_only: bool = False


class Armor(ContentObject):
    category: Literal["light", "medium", "heavy", "shield"]
    ac: int
    cost_cp: int
    dex_cap: int | None = None
    strength_min: int = 0


class Mastery(ContentObject):
    pass


class Item(Behavior):
    cost_cp: int
    # инструмент (владение им дают предыстории и черта Skilled)
    tool: bool = False
    # редкость магического предмета (SRD 5.2); у немагических не задаётся
    rarity: Rarity | None = None
    magic: bool = False
    # боеприпас: id оружия, которым он стреляется
    ammo_for: list[str] = []
    # название во множественном числе для строк лога боеприпасов («Зажигательные стрелы»); "" = name
    name_plural: str = ""
    # короткое название для пунктов действий («Каменная Кожа»)
    short_name: str = ""
    # группа в /inv для предметов без оружия/доспеха/боеприпаса/эффектов; "" = снаряжение
    category: Literal["", "consumable", "clothing", "gear", "valuable", "quest", "ammo"] = ""
    # вес в сотых долях фунта (задан только у сюжетных предметов мира)
    weight_centilb: int | None = None
