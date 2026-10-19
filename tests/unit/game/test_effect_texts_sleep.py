# Шаг 93: /inv и лист показывают сонную стрелу: «сон: СЛ 12 Тел 1 мин» (sheet_text.effect_texts).
from ai_dm.content.models.common import EffectSpec
from ai_dm.game.sheet_text import effect_texts


def test_sleep_effect_text_has_dc_ability_and_duration():
    effect = EffectSpec(type="sleep", dc=12, duration_s=60)
    assert effect_texts([effect]) == "сон: СЛ 12 Тел 1 мин"


def test_sleep_text_takes_the_dc_from_the_effect():
    effect = EffectSpec(type="sleep", dc=15, duration_s=60)
    assert effect_texts([effect]).startswith("сон: СЛ 15 Тел")


def test_sleep_text_goes_after_poison_damage_text():
    damage = EffectSpec(type="extra_damage", dice="1d4", damage_type="poison")
    sleep = EffectSpec(type="sleep", dc=12, duration_s=60)
    text = effect_texts([damage, sleep])
    assert text.startswith("+1d4 ") and text.endswith("сон: СЛ 12 Тел 1 мин")
