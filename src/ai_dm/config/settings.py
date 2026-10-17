import tomllib
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ai_dm.content.models.items import Rarity
from ai_dm.core.dice import parse_dice
from ai_dm.core.duration import Duration

DEFAULTS_PATH = Path(__file__).parent / "defaults.toml"
# потолок уровня героя; сторож: равен max_level(registry) (старший уровень таблицы xp)
LEVEL_CAP = 20


class TimeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    round_s: int
    short_rest_s: int
    long_rest_s: int
    min_advance_s: int
    advance_categories: dict[str, int]
    travel_pace: dict[str, int]


class CombatConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    max_rounds: int
    improvise_damage_dice: str
    # ступень elevation зоны в футах (падение: 1d6 за 10 фт)
    fall_step_ft: int = 10

    @field_validator("improvise_damage_dice")
    @classmethod
    def check_dice(cls, value: str) -> str:
        parse_dice(value)
        return value


class ParleyConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # СЛ переговоров: база (SRD Influence); если Инт цели выше -- Инт цели
    base_dc: int = 15
    # отношение NPC: от friendly -- дружелюбный (СЛ ниже), до hostile -- враждебный (помеха)
    friendly_attitude: int = 30
    hostile_attitude: int = -30
    friendly_bonus: int = 5
    # цель при HP не больше половины / четверти: СЛ ниже
    hp_half_bonus: int = 2
    hp_quarter_bonus: int = 5
    # выбыла половина группы цели / выбыл лидер группы: СЛ ниже
    losses_bonus: int = 3
    leader_down_bonus: int = 3
    # героев боеспособных вдвое больше врагов: СЛ ниже (только Запугивание)
    overwhelm_bonus: int = 2
    # надбавки к СЛ за исход и за ключевого NPC
    defect_penalty: int = 5
    waver_bonus: int = 2
    key_penalty: int = 5
    # не отвечают на переговоры: Инт не больше min_int и типы существ из списка
    min_int: int = 3
    immune_types: list[str] = ["construct", "ooze", "plant"]
    # провал «переходит» на столько и больше: цель оскорблена
    offended_margin: int = 5
    # отношение именованного NPC после боя (в пределах [attitude] per_scene)
    surrender_attitude: int = 10
    defect_attitude: int = 20
    offended_attitude: int = -10
    # цель обезоружена: СЛ ниже
    disarmed_bonus: int = 2
    # мораль группы при сильном успехе (на будущее, пока не используется)
    spread_morale: bool = False


class DisarmConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # типы существ, у которых остаётся безоружный удар, когда оружие отобрано
    unarmed_types: list[str] = ["humanoid", "fey"]
    # бонус мастерства монстра в безоружном ударе
    unarmed_proficiency: int = 2
    # check -- состязание DMG (бросок атаки против проверки цели);
    # save -- спасбросок цели Сил/Лов против СЛ 8 + Сил/Лов + мастерство атакующего
    mode: Literal["check", "save"] = "check"
    # шанс (%) монстра без тега disarmer получить роль обезоруживающего при старте боя, раз за бой
    enemy_chance: int = Field(0, ge=0, le=100)


class CustomItemsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name_max: int = 40
    description_max: int = 200
    # новых сюжетных предметов за сцену
    per_scene: int = 5
    # предел цены сюжетного предмета (мм): до уровня high_from_level и с него
    cost_cap_cp: int = 5000
    cost_cap_high_cp: int = 50000
    high_from_level: int = 5


class DefeatConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    robbery_gold_percent: int
    left_to_die_hours_dice: str
    left_to_die_hp: int

    @field_validator("left_to_die_hours_dice")
    @classmethod
    def check_dice(cls, value: str) -> str:
        parse_dice(value)
        return value


class XpConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    quest_minor_percent: int
    quest_medium_percent: int
    quest_major_percent: int


class SavesConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    autosave_keep: int = 3


class SceneConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    max_player_turns: int
    max_time_jump_s: int
    max_per_chapter: int


class AttitudeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    step: int
    per_scene: int


class NpcMemoryConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # сцен в памяти одного NPC о герое; новая сцена вытесняет сцену с наименьшим весом
    max_scenes: int = Field(default=20, gt=0)
    max_events_per_scene: int = Field(default=5, gt=0)


class FavorConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # ТЗ 4.2: шаг ±2 за поступок, ±3 к одному богу за сцену
    step: int = 2
    per_scene: int = 3
    # шанс вмешательства при благосклонности 9 и 10, процентов
    intervention_percent_9: int = 50
    intervention_percent_10: int = 75
    # шаблон then триггера-долга; {god} и {hero} подставляются
    debt_then: str = "{god} требует от {hero} услугу за спасение от смерти"
    servant_cooldown: str = "30d"

    @field_validator("servant_cooldown")
    @classmethod
    def check_cooldown(cls, value: str) -> str:
        Duration.parse(value)
        return value


class LimitsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    give_item_max_qty: int
    max_enemies: int
    consumables_per_scene: int
    gold_explicit_max_cp_by_level: dict[int, int]
    # окно последних ходов, где повтор той же суммы explicit gain отклоняется; 0 -- выкл.
    gold_repeat_turns: int = Field(default=3, ge=0)
    # наград опыта за сцену; сверх лимита award_xp отклоняется; 0 -- выкл.
    xp_awards_per_scene: int = Field(default=1, ge=0)
    # окно последних ходов, где повтор часа без пути и дела отклоняется; 0 -- выкл.
    time_repeat_turns: int = Field(default=2, ge=0)
    # кулдаун повторного длинного отдыха от конца предыдущего (строка Duration)
    long_rest_cooldown: str = "12h"

    @field_validator("long_rest_cooldown")
    @classmethod
    def check_cooldown(cls, value: str) -> str:
        Duration.parse(value)
        return value

    @field_validator("gold_explicit_max_cp_by_level")
    @classmethod
    def check_levels(cls, value: dict[int, int]) -> dict[int, int]:
        if sorted(value) != list(range(1, LEVEL_CAP + 1)):
            raise ValueError(
                f"ключи gold_explicit_max_cp_by_level должны быть ровно 1..{LEVEL_CAP}"
            )
        return value


class EncounterConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # потолок бюджета боя: low, moderate или high (решение G2а: moderate; сложность пака 1.0)
    tier: Literal["low", "moderate", "high"] = "moderate"


class TrophyBand(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # трофей с тела с ПО до max_cr включительно: качество и цена в процентах от SRD
    max_cr: float
    quality: Literal["junk", "worn", "used"]
    percent: int


class LootConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # полосы качества трофеев по возрастанию ПО; выше последней -- исходное оружие по полной цене
    trophy_quality: list[TrophyBand] = [
        TrophyBand(max_cr=0.25, quality="junk", percent=10),
        TrophyBand(max_cr=2, quality="worn", percent=25),
        TrophyBand(max_cr=4, quality="used", percent=50),
    ]
    # уровень героя -> наивысшая редкость магического предмета, которую можно выдать
    rarity_cap_by_level: dict[int, Rarity] = {
        1: "uncommon", 2: "uncommon", 3: "uncommon", 4: "uncommon",
        5: "rare", 6: "rare", 7: "rare", 8: "rare", 9: "rare", 10: "rare",
        11: "very_rare", 12: "very_rare", 13: "very_rare", 14: "very_rare", 15: "very_rare",
        16: "very_rare",
        17: "legendary", 18: "legendary", 19: "legendary", 20: "legendary",
    }

    @field_validator("rarity_cap_by_level")
    @classmethod
    def check_levels(cls, value):
        if sorted(value) != list(range(1, LEVEL_CAP + 1)):
            raise ValueError(f"ключи rarity_cap_by_level должны быть ровно 1..{LEVEL_CAP}")
        return value


# категория предмета в торговле: weapon/armor -- по виду модели реестра (Weapon/Armor),
# ammo -- по непустому ammo_for, прочие -- по Item.category
TradeCategory = Literal["weapon", "armor", "ammo", "gear", "consumable", "clothing", "valuable"]


class TradePreset(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # что торговец продаёт (категории предметов реестра)
    categories: list[TradeCategory]
    # продаёт ли магические предметы (в пределах редкости по уровню героя)
    magic: bool = False
    # деньги на скупку (мм)
    purse_cp: int = Field(default=5000, ge=0)
    # что скупает у героя
    buys: list[TradeCategory]


class TradeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # покупка = цена экземпляра * buy_factor, продажа = * sell_factor (в пользу торговца)
    buy_factor: float = Field(default=1.0, gt=0)
    sell_factor: float = Field(default=0.5, ge=0)
    # хорошее отношение (attitude >= attitude_good_from): свои коэффициенты
    attitude_good_from: int = Field(default=50, ge=-100, le=100)
    attitude_good_buy_factor: float = Field(default=0.9, gt=0)
    attitude_good_sell_factor: float = Field(default=0.6, ge=0)
    # плохое отношение (attitude <= attitude_refuse_at): торговец отказывается
    attitude_refuse_at: int = Field(default=-50, ge=-100, le=100)
    ops_per_scene: int = Field(default=20, ge=1)
    new_merchants_per_scene: int = Field(default=1, ge=0)
    restock_days: int = Field(default=7, ge=1)
    # торг Убеждением (партия Т5): поправка цены в процентах по исходу проверки
    haggle_success_percent: int = -10
    haggle_strong_percent: int = -20
    haggle_fail_percent: int = 10
    haggle_dc: int = 15
    haggle_good_dc: int = 10
    haggle_strong_margin: int = Field(default=5, ge=1)
    # attitude ниже порога: бросок торга с помехой
    haggle_hostile_below: int = 0
    # потолок суммарной скидки/наценки (отношение + торг), проценты
    price_mod_cap_percent: int = Field(default=20, ge=0, le=99)
    # цена покупки героем при максимальной скидке >= лучшая цена продажи героем * min_margin
    min_margin: float = Field(default=1.3, ge=1)
    presets: dict[str, TradePreset] = {}

    @model_validator(mode="after")
    def check_no_arbitrage(self):
        if self.attitude_refuse_at >= self.attitude_good_from:
            raise ValueError("attitude_refuse_at должен быть меньше attitude_good_from")
        if self.attitude_good_sell_factor < self.sell_factor:
            raise ValueError("attitude_good_sell_factor не может быть меньше sell_factor")
        if self.attitude_good_buy_factor > self.buy_factor:
            raise ValueError("attitude_good_buy_factor не может быть больше buy_factor")
        strong, success = self.haggle_strong_percent, self.haggle_success_percent
        if not strong <= success <= 0 <= self.haggle_fail_percent:
            raise ValueError("торг: strong <= success <= 0 <= fail")
        # худший случай: герой покупает с макс. скидкой, а продаёт по лучшей цене
        cheapest_buy = self.buy_factor * (100 - self.price_mod_cap_percent) / 100
        dearest_sell = max(self.sell_factor, self.attitude_good_sell_factor)
        if cheapest_buy < dearest_sell * self.min_margin:
            raise ValueError(
                f"арбитраж: покупка со скидкой {cheapest_buy:.3f} ниже продажи "
                f"{dearest_sell:.3f} * min_margin {self.min_margin}"
            )
        return self


class AgingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    step_percent: int = 10


class WorldConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mortality_presets: dict[str, int]
    max_tick_days: int = 400
    aging: AgingConfig = AgingConfig()
    # множитель смертности событий от модели по event_type; прочие типы -- 1
    event_multipliers: dict[str, int] = {"plague": 20, "war": 5, "famine": 5}


class RulesConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    time: TimeConfig
    combat: CombatConfig
    defeat: DefeatConfig
    xp: XpConfig
    saves: SavesConfig
    scene: SceneConfig
    attitude: AttitudeConfig
    npc_memory: NpcMemoryConfig = NpcMemoryConfig()
    favor: FavorConfig = FavorConfig()
    parley: ParleyConfig = ParleyConfig()
    disarm: DisarmConfig = DisarmConfig()
    limits: LimitsConfig
    custom_items: CustomItemsConfig = CustomItemsConfig()
    encounter: EncounterConfig = EncounterConfig()
    loot: LootConfig = LootConfig()
    trade: TradeConfig = TradeConfig()
    world: WorldConfig


def deep_merge(base: dict, override: dict) -> dict:
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


# внутренний загрузчик для devtools; игра использует load_settings
def load_rules_config(toml_text: str | None = None, path: Path | None = None) -> RulesConfig:
    data = tomllib.loads(DEFAULTS_PATH.read_text(encoding="utf-8"))
    if toml_text is not None:
        data = deep_merge(data, tomllib.loads(toml_text))
    if path is not None:
        data = deep_merge(data, tomllib.loads(path.read_text(encoding="utf-8")))
    return RulesConfig.model_validate(data)
