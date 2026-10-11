from typing import Literal

from ai_dm.content.models.common import Ability, ContentModel, ContentObject, FeatureRef, Skill


class SkillChoices(ContentModel):
    count: int
    options: list[Skill]


class Spellcasting(ContentModel):
    ability: Ability
    progression: Literal["full", "half"]
    # при создании героя; None = без ограничения
    cantrips: int | None = None
    spells: int | None = None
    prepared: int | None = None
    # сколько заклинаний подготовлено на уровне героя (ключ -- уровень); None = только prepared
    prepared_by_level: dict[int, int] | None = None


class StartingKit(ContentModel):
    id: str
    # повтор id = количество
    items: list[str]
    equip: list[str] = []
    gold_cp: int = 0


class CharacterClass(ContentObject):
    hit_die: int
    saving_throws: list[Ability]
    skill_choices: SkillChoices = SkillChoices(count=0, options=[])
    armor_training: list[Literal["light", "medium", "heavy", "shield"]] = []
    weapon_training: list[Literal["simple", "martial"]] = []
    # воинское оружие с любым из этих свойств (плут)
    weapon_training_properties: list[Literal["finesse", "light"]] = []
    weapon_mastery_count: int = 0
    spellcasting: Spellcasting | None = None
    features: list[FeatureRef] = []
    # стартовые наборы класса (SRD 5.2: варианты A/B/C); пусто = нет
    starting_kits: list[StartingKit] = []


class Subclass(ContentObject):
    class_id: str
    features: list[FeatureRef] = []
