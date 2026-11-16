# К8с П2 (docs/plan-k8s.md, «Тесты» П2): заклинания следопыта 3 круга и общие 1-2 круга (пункт 250).
#   * следопыт получает 12 заклинаний 3 круга (SRD 5.2.1, open5e srd-2024, сверка 2026-11-15) и 25
#     заклинаний 1-2 круга (13 были, +12); четыре новых файла: Призыв животных (аура Лов, 3d10
#     рубящего, +1d10 за круг), Стена ветра (область Сил, 4d8 дробящего, половина), Рост
#     растений и Разговор с растениями (utility со строкой эффекта, Р-К8с-5 = а, Р-К8с-7);
#   * Метка охотника: upcast.duration_by_circle {3: 8 ч, 5: 24 ч};
#   * пять effect_text (Р-К8с-7) начинаются со слова «Заклинатель», без «Маг» и «Жрец»;
#   * следопыт 10 со всеми своими заклинаниями: inert_spells пуст, меню боя строится без ошибок.
import copy
import re

import game_kit  # noqa: F401  (добавляет в sys.path соседние kit-ы)
import pytest
from combat_kit import make_engine, mon
from ranger_kit import ranger_at

from ai_dm.combat.actions.cast import inert_spells
from ai_dm.core.rng import Rng
from ai_dm.rules.results import Rejected

THIRD_CIRCLE = {
    "conjure_animals", "daylight", "dispel_magic", "meld_into_stone", "nondetection",
    "plant_growth", "protection_from_energy", "revivify", "speak_with_plants", "water_breathing",
    "water_walk", "wind_wall",
}
NEW_SPELLS = ["conjure_animals", "plant_growth", "speak_with_plants", "wind_wall"]
GAINED_LOW = [
    "detect_magic", "detect_poison_and_disease", "jump", "aid", "darkvision", "enhance_ability",
    "find_traps", "gust_of_wind", "locate_object", "protection_from_poison", "silence",
    "magic_weapon",
]
REPERTOIRE_24 = set(GAINED_LOW) | THIRD_CIRCLE
EFFECT_TEXT_FIXED = ["detect_magic", "detect_poison_and_disease", "find_traps", "locate_object",
                     "meld_into_stone"]


def ranger_spells(registry):
    return [s for s in registry.all("spell") if "ranger" in s.classes]


def circle(registry, level):
    return {s.id for s in ranger_spells(registry) if s.level == level}


def test_ranger_has_exactly_twelve_third_circle_spells(registry):
    assert circle(registry, 3) == THIRD_CIRCLE


def test_ranger_has_twenty_five_spells_of_circles_one_and_two(registry):
    assert len(circle(registry, 1) | circle(registry, 2)) == 25


@pytest.mark.parametrize("spell_id", GAINED_LOW)
def test_shared_low_spell_now_belongs_to_ranger(registry, spell_id):
    assert "ranger" in registry.get("spell", spell_id).classes


@pytest.mark.parametrize("spell_id", ["detect_magic", "meld_into_stone", "dispel_magic"])
def test_ranger_spell_keeps_its_old_classes(registry, spell_id):
    classes = set(registry.get("spell", spell_id).classes)
    assert "ranger" in classes
    assert classes & {"cleric", "wizard"}


@pytest.mark.parametrize("spell_id", NEW_SPELLS)
def test_new_spell_is_third_circle_for_ranger(registry, spell_id):
    spell = registry.get("spell", spell_id)
    assert spell.level == 3
    assert "ranger" in spell.classes


@pytest.mark.parametrize("spell_id, name", [
    ("conjure_animals", "Призыв животных"), ("plant_growth", "Рост растений"),
    ("speak_with_plants", "Разговор с растениями"), ("wind_wall", "Стена ветра"),
])
def test_new_spell_has_the_russian_name(registry, spell_id, name):
    assert registry.get("spell", spell_id).name == name


def test_conjure_animals_is_a_dex_save_aura_of_slashing(registry):
    spell = registry.get("spell", "conjure_animals")
    (effect,) = [e for e in spell.effects if e.type == "aura"]
    assert (effect.dice, effect.ability, effect.damage_type) == ("3d10", "dex", "slashing")


def test_conjure_animals_grows_by_one_d10_per_circle(registry):
    spell = registry.get("spell", "conjure_animals")
    assert spell.upcast.per_slot_level.dice == "1d10"


def test_conjure_animals_needs_concentration(registry):
    assert registry.get("spell", "conjure_animals").concentration


def test_wind_wall_is_a_strength_save_area_with_half_damage(registry):
    spell = registry.get("spell", "wind_wall")
    kinds = {e.type: e for e in spell.effects}
    assert (kinds["save_effect"].ability, kinds["save_effect"].mode) == ("str", "half")
    assert (kinds["damage"].dice, kinds["damage"].damage_type) == ("4d8", "bludgeoning")


@pytest.mark.parametrize("spell_id, text", [
    ("plant_growth", "Растения в выбранном месте буйно разрастаются: идти там вчетверо труднее."),
    ("speak_with_plants", "Растения в 30 фт. десять минут отвечают на вопросы о последних сутках "
                          "и слушаются простых просьб."),
])
def test_plant_spells_are_utility_with_the_agreed_text(registry, spell_id, text):
    spell = registry.get("spell", spell_id)
    assert [e.type for e in spell.effects] == ["utility"]
    assert spell.effect_text == text


@pytest.mark.parametrize("spell_id", EFFECT_TEXT_FIXED)
def test_effect_text_speaks_of_a_caster_not_of_a_mage_or_cleric(registry, spell_id):
    text = registry.get("spell", spell_id).effect_text
    assert text.startswith("Заклинатель")
    assert not {"Маг", "Жрец"} & set(re.findall(r"\w+", text))


def test_hunters_mark_duration_by_circle(registry):
    upcast = registry.get("spell", "hunters_mark").upcast
    assert upcast.duration_by_circle == {3: "8h", 5: "24h"}


def test_hunters_mark_still_has_no_dice_growth(registry):
    assert registry.get("spell", "hunters_mark").upcast.per_slot_level.dice is None


def full_ranger_engine(registry, cfg, seed=2):
    hero = ranger_at(registry, 10)
    hero.sheet.prepared_of().extend(
        s.id for s in ranger_spells(registry) if s.id not in hero.sheet.prepared_of()
    )
    return make_engine(
        registry, cfg, heroes=[hero], rng=Rng(seed),
        monsters=[mon("goblin_1", "goblin_warrior", "hall")],
    )


def test_ranger_ten_only_speak_with_animals_is_inert_with_every_spell_prepared(registry, cfg):
    engine = full_ranger_engine(registry, cfg)
    assert [s.id for s in inert_spells(engine, "hero")] == ["speak_with_animals"]


def test_ranger_ten_combat_menu_builds_with_every_ranger_spell_prepared(registry, cfg):
    engine = full_ranger_engine(registry, cfg)
    ids = [o.id for o in engine.available_actions("hero")]
    assert any(i.startswith("cast:conjure_animals:3:") for i in ids)


def test_ranger_ten_every_cast_option_can_be_performed(registry, cfg):
    engine = full_ranger_engine(registry, cfg)
    cast_ids = [o.id for o in engine.available_actions("hero") if o.kind == "cast"]
    rejected = []
    for option_id in cast_ids:
        trial = copy.deepcopy(engine)
        if isinstance(trial.perform("hero", option_id), Rejected):
            rejected.append(option_id)
    assert rejected == []


@pytest.mark.parametrize("spell_id", sorted(REPERTOIRE_24 - {"revivify"}))
def test_every_new_ranger_spell_has_a_cast_option(registry, cfg, spell_id):
    engine = full_ranger_engine(registry, cfg)
    ids = [o.id for o in engine.available_actions("hero")]
    assert any(i.startswith(f"cast:{spell_id}:") for i in ids)


def test_repertoire_is_twenty_four_spells():
    assert len(REPERTOIRE_24) == 24


def test_conjure_animals_lasts_ten_minutes(registry):
    assert registry.get("spell", "conjure_animals").duration_s == 600


def test_wind_wall_is_ranged_at_120_feet(registry):
    spell = registry.get("spell", "wind_wall")
    assert (spell.range_kind, spell.range_ft) == ("ranged", 120)


def test_wind_wall_is_one_chosen_zone_cube_like_web(registry):
    (area,) = [e for e in registry.get("spell", "wind_wall").effects if e.type == "area"]
    assert (area.shape, area.size_ft) == ("cube", 20)


def test_wind_wall_sheet_shows_120_feet(registry):
    from ai_dm.game.sheet_text import casting_text

    assert casting_text(registry.get("spell", "wind_wall")).endswith("120 фт.")


DESCRIPTIONS = {
    "conjure_animals": (
        "Вокруг вас до 10 минут (концентрация) кружится стая призрачных зверей. Враг, который "
        "входит в вашу зону или заканчивает в ней ход, совершает спасбросок Ловкости: при провале "
        "получает 3d10 рубящего урона, при успехе урона не получает. На каждый уровень ячейки "
        "выше 3-го — +1d10."
    ),
    "plant_growth": (
        "Растения в выбранном месте буйно разрастаются: идти там вчетверо труднее. Если творить "
        "заклинание 8 часов, оно вместо этого обогащает землю на полмили вокруг: год урожай "
        "вдвое больше."
    ),
    "speak_with_plants": (
        "В течение 10 минут вы в пределах 30 фт. общаетесь с растениями: они отвечают на вопросы "
        "о событиях последних суток (погода, кто проходил, что росло рядом) и слушаются простых "
        "просьб."
    ),
}


@pytest.mark.parametrize("spell_id", sorted(DESCRIPTIONS))
def test_new_spell_description_is_the_agreed_text(registry, spell_id):
    assert registry.get("spell", spell_id).description == DESCRIPTIONS[spell_id]


def test_wind_wall_description_starts_at_120_feet_and_keeps_the_tail(registry):
    text = registry.get("spell", "wind_wall").description
    assert text.startswith(
        "В выбранном месте в пределах 120 фт. встаёт стена сильного ветра длиной"
    )
    assert text.endswith(
        "Существа в этой области совершают спасбросок Силы и при провале получают 4d8 дробящего "
        "урона, при успехе — половину. Стена останавливает стрелы, газы и туман."
    )


def test_hunters_mark_description_tells_about_eight_and_twenty_four_hours(registry):
    text = registry.get("spell", "hunters_mark").description
    assert ("Ячейкой 3–4 круга концентрация держится до 8 часов, 5 круга и выше — "
            "до 24 часов.") in text
