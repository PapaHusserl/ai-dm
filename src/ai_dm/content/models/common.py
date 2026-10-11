from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

Ability = Literal["str", "dex", "con", "int", "wis", "cha"]

ABILITIES = ("str", "dex", "con", "int", "wis", "cha")

DcCategory = Literal["very_easy", "easy", "medium", "hard", "very_hard", "nearly_impossible"]

# навык -> характеристика
SKILLS = {
    "acrobatics": "dex",
    "animal_handling": "wis",
    "arcana": "int",
    "athletics": "str",
    "deception": "cha",
    "history": "int",
    "insight": "wis",
    "intimidation": "cha",
    "investigation": "int",
    "medicine": "wis",
    "nature": "int",
    "perception": "wis",
    "performance": "cha",
    "persuasion": "cha",
    "religion": "int",
    "sleight_of_hand": "dex",
    "stealth": "dex",
    "survival": "wis",
}

Skill = Literal[
    "acrobatics",
    "animal_handling",
    "arcana",
    "athletics",
    "deception",
    "history",
    "insight",
    "intimidation",
    "investigation",
    "medicine",
    "nature",
    "perception",
    "performance",
    "persuasion",
    "religion",
    "sleight_of_hand",
    "stealth",
    "survival",
]

EffectType = Literal[
    "modifier",
    "resource",
    "action",
    "damage",
    "heal",
    "save_effect",
    "apply_condition",
    "area",
    "crit_range",
    "extra_damage",
    "proficiency",
    "spell_access",
    "reroll",
    "feat_choice",
    # особые стрелы, клинок, эликсир (пак Дракона)
    "burn",
    "slow",
    "pierce_armor",
    "silvered",
    "ignore_magic_ac",
    "ac_bonus",
    "resist",
    # заряд на следующее попадание оружием (Опутывающий удар)
    "rider",
]

# Закрытые значения полей эффектов: то, что читает движок. Новое значение = правка Literal.
EffectAdd = Literal["proficiency_bonus", "spellcasting_modifier", "class_level"]
EffectTarget = Literal[
    "saving_throw",
    "damage",
    "d20_test",
    "bonus_action",
    "weapon_damage",
    "skill",
    "skill_or_tool",
    "initiative",
    "ac",
    "attack_roll",
    "origin_feat",
]
EffectWhen = Literal[
    "natural_1", "once_per_turn", "wearing_armor", "long_rest", "ranged_weapon", "target_wounded",
    "on_weapon_hit",
]
EffectMode = Literal["advantage", "resistance", "half"]
EffectShape = Literal["cone"]


class ContentModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ContentObject(ContentModel):
    id: str
    name: str
    description: str = ""
    source: str = "custom"
    license: str = ""

    @field_validator("id")
    @classmethod
    def check_id(cls, value):
        if not value.isidentifier() or value != value.lower():
            raise ValueError("id: только строчные буквы, цифры и _, без пробелов")
        return value


class Recover(ContentModel):
    on: Literal["short_rest", "long_rest"]
    amount: int | Literal["all"]

    @model_validator(mode="before")
    @classmethod
    def yaml_on_key(cls, data):
        # в YAML 1.1 неквотированный ключ on читается как True
        if isinstance(data, dict) and True in data and "on" not in data:
            data = {("on" if k is True else k): v for k, v in data.items()}
        return data


class EffectSpec(ContentModel):
    type: EffectType
    dice: str | None = None
    value: int | None = None
    # количество (дротики, выборы)
    count: int | None = None
    # число целей (Благословение)
    targets: int | None = None
    add: EffectAdd | None = None
    # для add / max_add == "class_level"
    class_id: str | None = None
    target: EffectTarget | None = None
    mode: EffectMode | None = None
    ability: Ability | None = None
    skill: Skill | None = None
    damage_type: str | None = None
    condition: str | None = None
    resource: str | None = None
    amount: int | None = None
    shape: EffectShape | None = None
    size_ft: int | None = None
    when: EffectWhen | None = None
    # ресурс-пул (kind resource)
    pool: str | None = None
    max: int | None = None
    max_add: EffectAdd | None = None
    # максимум пула по уровню героя (ключ -- уровень); перекрывает max
    max_by_level: dict[int, int] | None = None
    # id заклинания (spell_access: всегда подготовлено, бесплатные касты из pool)
    spell: str | None = None
    recover: list[Recover] = []
    # доп. урон только по целям с одним из этих тегов (undead, mor)
    vs: list[str] = []
    # длительность эффекта в секундах мира (эликсир)
    duration_s: int | None = None

    @model_validator(mode="after")
    def check_class_id(self):
        if "class_level" in (self.add, self.max_add) and self.class_id is None:
            raise ValueError("class_id обязателен при add/max_add == class_level")
        return self


class HandlerSpec(ContentModel):
    name: str
    params: dict = {}


class Behavior(ContentObject):
    effects: list[EffectSpec] = []
    handler: HandlerSpec | None = None


class FeatureRef(ContentModel):
    level: int
    feature: str
