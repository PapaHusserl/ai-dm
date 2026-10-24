# Ожидаемый API: ai_dm.config.settings (+ ai_dm/config/defaults.toml в пакете)
#   RulesConfig(BaseModel, extra="forbid") с вложенными секциями (все тоже extra="forbid"):
#     .time:   round_s=6, short_rest_s=3600, long_rest_s=28800, min_advance_s=600,
#              advance_categories: dict[str, int] -- секунды для "minute", "hour", "day", "week"
#              ("month" в конфиге нет: длина месяца берётся из календаря)
#     .combat: max_rounds=100
#     .defeat: robbery_gold_percent=50, left_to_die_hours_dice="1d8", left_to_die_hp=1
#     .saves:  autosave_keep=3 (сколько автосейвов хранить, кроме текущего auto)
#     .xp:     quest_minor_percent=10, quest_medium_percent=25, quest_major_percent=50
#   load_rules_config(toml_text: str | None = None, path: Path | None = None) -> RulesConfig
#     -- defaults.toml + (необязательно) пользовательский toml (строка или файл) поверх,
#        слияние по ключам вглубь: переопределённый ключ меняется, остальные остаются из defaults.
#        Неизвестный ключ (в любой секции, и на верхнем уровне) -> pydantic.ValidationError.
#   Глобального состояния нет: каждый вызов возвращает новый объект.
import pytest
from pydantic import ValidationError

from ai_dm.config.settings import LEVEL_CAP, RulesConfig, load_rules_config


def test_defaults_load():
    assert isinstance(load_rules_config(), RulesConfig)


def test_default_time_values():
    t = load_rules_config().time
    assert t.round_s == 6
    assert t.short_rest_s == 3600
    assert t.long_rest_s == 8 * 3600
    assert t.min_advance_s == 600


def test_default_advance_categories():
    cats = load_rules_config().time.advance_categories
    assert set(cats) == {"minute", "hour", "day", "week"}
    assert cats["day"] == 86400
    assert cats["week"] == 7 * 86400
    assert cats["minute"] == 900
    assert cats["hour"] == 3600
    assert 0 < cats["minute"] < cats["hour"] < cats["day"]


def test_default_round_limit():
    assert load_rules_config().combat.max_rounds == 100


def test_default_robbery_percent():
    assert load_rules_config().defeat.robbery_gold_percent == 50


def test_default_left_to_die():
    d = load_rules_config().defeat
    assert d.left_to_die_hours_dice == "1d8"
    assert d.left_to_die_hp == 1


def test_default_xp_shares():
    xp = load_rules_config().xp
    assert xp.quest_minor_percent == 10
    assert xp.quest_medium_percent == 25
    assert xp.quest_major_percent == 50


def test_override_from_string():
    cfg = load_rules_config(toml_text="[combat]\nmax_rounds = 30\n")
    assert cfg.combat.max_rounds == 30


def test_override_keeps_other_keys():
    cfg = load_rules_config(toml_text="[combat]\nmax_rounds = 30\n")
    assert cfg.time.round_s == 6
    assert cfg.defeat.robbery_gold_percent == 50


def test_override_single_key_inside_section_keeps_siblings():
    cfg = load_rules_config(toml_text="[time]\nmin_advance_s = 60\n")
    assert cfg.time.min_advance_s == 60
    assert cfg.time.long_rest_s == 8 * 3600


def test_override_one_advance_category_keeps_others():
    cfg = load_rules_config(toml_text="[time.advance_categories]\nminute = 300\n")
    assert cfg.time.advance_categories["minute"] == 300
    assert cfg.time.advance_categories["day"] == 86400


def test_override_from_file(tmp_path):
    p = tmp_path / "ai-dm.toml"
    p.write_text("[defeat]\nrobbery_gold_percent = 25\n", encoding="utf-8")
    assert load_rules_config(path=p).defeat.robbery_gold_percent == 25


def test_override_does_not_leak_between_calls():
    load_rules_config(toml_text="[combat]\nmax_rounds = 5\n")
    assert load_rules_config().combat.max_rounds == 100


def test_unknown_top_level_key_is_error():
    with pytest.raises(ValidationError):
        load_rules_config(toml_text="bogus = 1\n")


def test_unknown_key_in_section_is_error():
    with pytest.raises(ValidationError):
        load_rules_config(toml_text="[combat]\nmax_roundz = 5\n")


def test_rules_config_direct_unknown_key_is_error():
    with pytest.raises(ValidationError):
        RulesConfig.model_validate({"bogus": 1})


def test_default_travel_pace():
    assert load_rules_config().time.travel_pace == {"slow": 3200, "normal": 4800, "fast": 6400}


def test_invalid_left_to_die_dice_is_error():
    with pytest.raises(ValidationError):
        load_rules_config(toml_text='[defeat]\nleft_to_die_hours_dice = "abc"\n')


def test_default_autosave_keep():
    assert load_rules_config().saves.autosave_keep == 3


def test_override_autosave_keep():
    assert load_rules_config(toml_text="[saves]\nautosave_keep = 5\n").saves.autosave_keep == 5


# этап 2: новые секции RulesConfig. Значения give_item / gold -- в конфиге, выбраны тестировщиком
#   .scene:  max_player_turns=30, max_time_jump_s=3600 (скачок времени больше -- закрывает сцену)
#   .attitude: step=10 (за один npc_update), per_scene=20 (суммарно за сцену)
#   .limits: give_item_max_qty=20, max_enemies=6,
#            gold_explicit_max_cp_by_level: dict[int, int] -- потолок явной награды золотом в
#            медных (мм) по уровню героя 1..5: 5_000 / 10_000 / 25_000 / 50_000 / 100_000

def test_default_scene_section():
    scene = load_rules_config().scene
    assert scene.max_player_turns == 30
    assert scene.max_time_jump_s == 3600


def test_default_attitude_section():
    attitude = load_rules_config().attitude
    assert attitude.step == 10
    assert attitude.per_scene == 30


def test_default_locations_section():
    assert load_rules_config().locations.inside_max_m == 500


def test_default_limits_section():
    limits = load_rules_config().limits
    assert limits.give_item_max_qty == 20
    assert limits.max_enemies == 6


def test_default_gold_limits_by_level():
    gold = load_rules_config().limits.gold_explicit_max_cp_by_level
    assert gold == {
        1: 5_000, 2: 10_000, 3: 25_000, 4: 50_000, 5: 100_000,
        6: 150_000, 7: 200_000, 8: 300_000, 9: 400_000, 10: 500_000,
        11: 750_000, 12: 1_000_000, 13: 1_250_000, 14: 1_500_000, 15: 2_000_000,
        16: 2_500_000, 17: 3_500_000, 18: 5_000_000, 19: 7_500_000, 20: 10_000_000,
    }


def test_gold_limits_grow_with_level():
    gold = load_rules_config().limits.gold_explicit_max_cp_by_level
    values = [gold[level] for level in range(1, 21)]
    assert values == sorted(values)


def test_override_gold_limit_for_one_level_keeps_others():
    text = "[limits.gold_explicit_max_cp_by_level]\n3 = 99\n"
    gold = load_rules_config(text).limits.gold_explicit_max_cp_by_level
    assert gold[3] == 99
    assert gold[1] == 5_000


@pytest.mark.parametrize("section", ["scene", "attitude", "limits"])
def test_unknown_key_in_new_rules_section_is_rejected(section):
    with pytest.raises(ValidationError):
        load_rules_config(f"[{section}]\nbogus = 1\n")


# ключи потолка золота -- ровно 1..LEVEL_CAP (ревью партии 1, п.5; К0б: 1..20)

def test_gold_limits_extra_level_is_rejected():
    text = "[limits.gold_explicit_max_cp_by_level]\n21 = 500000\n"
    with pytest.raises(ValidationError):
        load_rules_config(text)


def test_gold_limits_extra_level_zero_is_rejected():
    text = "[limits.gold_explicit_max_cp_by_level]\n0 = 1\n"
    with pytest.raises(ValidationError):
        load_rules_config(text)


def test_gold_limits_missing_level_is_rejected():
    data = load_rules_config().model_dump()
    del data["limits"]["gold_explicit_max_cp_by_level"][4]
    with pytest.raises(ValidationError):
        RulesConfig.model_validate(data)


def test_gold_limits_missing_level_20_is_rejected():
    data = load_rules_config().model_dump()
    del data["limits"]["gold_explicit_max_cp_by_level"][20]
    with pytest.raises(ValidationError):
        RulesConfig.model_validate(data)


def test_gold_limits_missing_level_6_is_rejected():
    data = load_rules_config().model_dump()
    del data["limits"]["gold_explicit_max_cp_by_level"][6]
    with pytest.raises(ValidationError):
        RulesConfig.model_validate(data)


def test_gold_limits_level_5_cap_is_no_longer_enough():
    data = load_rules_config().model_dump()
    gold = data["limits"]["gold_explicit_max_cp_by_level"]
    data["limits"]["gold_explicit_max_cp_by_level"] = {k: v for k, v in gold.items() if k <= 5}
    with pytest.raises(ValidationError):
        RulesConfig.model_validate(data)


# потолок уровня в конфиге и предел редкости по уровням

def test_level_cap_is_20():
    assert LEVEL_CAP == 20


def test_level_cap_equals_max_level_of_xp_table(registry):
    from ai_dm.rules.progression import max_level

    assert max_level(registry) == LEVEL_CAP


def test_default_rarity_cap_by_level():
    cap = load_rules_config().loot.rarity_cap_by_level
    assert sorted(cap) == list(range(1, 21))
    assert [cap[level] for level in range(1, 5)] == ["uncommon"] * 4
    assert [cap[level] for level in range(5, 11)] == ["rare"] * 6
    assert [cap[level] for level in range(11, 17)] == ["very_rare"] * 6
    assert [cap[level] for level in range(17, 21)] == ["legendary"] * 4


def test_rarity_cap_extra_level_is_rejected():
    data = load_rules_config().model_dump()
    data["loot"]["rarity_cap_by_level"][21] = "legendary"
    with pytest.raises(ValidationError):
        RulesConfig.model_validate(data)


def test_rarity_cap_missing_level_is_rejected():
    data = load_rules_config().model_dump()
    del data["loot"]["rarity_cap_by_level"][19]
    with pytest.raises(ValidationError):
        RulesConfig.model_validate(data)


def test_rarity_cap_level_zero_is_rejected():
    data = load_rules_config().model_dump()
    data["loot"]["rarity_cap_by_level"][0] = "common"
    with pytest.raises(ValidationError):
        RulesConfig.model_validate(data)


def test_rarity_cap_only_five_levels_is_rejected():
    data = load_rules_config().model_dump()
    cap = data["loot"]["rarity_cap_by_level"]
    data["loot"]["rarity_cap_by_level"] = {k: v for k, v in cap.items() if k <= 5}
    with pytest.raises(ValidationError):
        RulesConfig.model_validate(data)


# К7х: [combat].fall_step_ft и [disarm].mode / enemy_chance

def test_default_fall_step_is_ten_feet():
    assert load_rules_config().combat.fall_step_ft == 10


def test_fall_step_can_be_overridden():
    assert load_rules_config(toml_text="[combat]\nfall_step_ft = 5\n").combat.fall_step_ft == 5


def test_fall_step_override_keeps_the_other_combat_keys():
    cfg = load_rules_config(toml_text="[combat]\nfall_step_ft = 5\n")
    assert cfg.combat.max_rounds == 100


def test_fall_step_must_be_an_integer():
    with pytest.raises(ValidationError):
        load_rules_config(toml_text='[combat]\nfall_step_ft = "ten"\n')


def test_default_disarm_mode_and_chance():
    cfg = load_rules_config()
    assert (cfg.disarm.mode, cfg.disarm.enemy_chance) == ("check", 0)


def test_disarm_mode_save_is_allowed():
    assert load_rules_config(toml_text='[disarm]\nmode = "save"\n').disarm.mode == "save"


def test_disarm_mode_unknown_value_is_rejected():
    with pytest.raises(ValidationError):
        load_rules_config(toml_text='[disarm]\nmode = "foo"\n')


@pytest.mark.parametrize("value", [0, 1, 50, 100])
def test_enemy_chance_in_range_is_allowed(value):
    cfg = load_rules_config(toml_text=f"[disarm]\nenemy_chance = {value}\n")
    assert cfg.disarm.enemy_chance == value


@pytest.mark.parametrize("value", [-1, 101, 1000])
def test_enemy_chance_out_of_range_is_rejected(value):
    with pytest.raises(ValidationError):
        load_rules_config(toml_text=f"[disarm]\nenemy_chance = {value}\n")


def test_disarm_override_keeps_the_unarmed_types():
    cfg = load_rules_config(toml_text="[disarm]\nenemy_chance = 10\n")
    assert cfg.disarm.unarmed_types == ["humanoid", "fey"]
