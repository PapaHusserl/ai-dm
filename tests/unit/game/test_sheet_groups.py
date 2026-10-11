# /inv по группам, полный /sheet, /spells, /abilities (stage3-live-sheet.md, S1-S4, T).
# Грей из пака campaigns/drunk_dragon (3 ур., Повелитель зверей). Ширина строк <= 80.
import re
from pathlib import Path

import pytest
from game_kit import ReactiveAdapter, make_app

from ai_dm.campaign.loader import load_pack, pack_content_dir
from ai_dm.content.loader import load_registry
from ai_dm.game.starter import new_world_from_pack

DRAGON = Path(__file__).resolve().parents[3] / "campaigns" / "drunk_dragon"


@pytest.fixture
def dragon_app(cfg, tmp_path):
    registry = load_registry([pack_content_dir(DRAGON)])
    bundle = new_world_from_pack(
        registry, cfg, load_pack(DRAGON, registry), hero="grey", seed=1, world_id="w1",
        saved_at="2026-01-01T00:00:00",
    )
    return make_app(registry, tmp_path, ReactiveAdapter(), bundle=bundle)


def lines_of(app, command):
    return app.handle(command).lines


def text_of(app, command):
    return "\n".join(lines_of(app, command))


def group_of(app, title):
    # строки группы: от заголовка до следующей строки без отступа
    lines = [line for text in lines_of(app, "/inv") for line in text.split("\n")]
    start = next(i for i, line in enumerate(lines) if line.startswith(title))
    rest = []
    for line in lines[start + 1:]:
        if not line.startswith(" "):
            break
        rest.append(line)
    return "\n".join(rest)


# /inv

def test_inv_has_groups_in_order(dragon_app):
    text = text_of(dragon_app, "/inv")
    titles = ["Оружие", "Доспехи и одежда", "Боеприпасы", "Зелья и расходники",
              "Снаряжение и инструменты", "Ценности и прочее", "Деньги"]
    positions = [text.index(title) for title in titles]
    assert positions == sorted(positions)


def test_inv_weapons_group_marks_weapon_in_hand(dragon_app):
    group = group_of(dragon_app, "Оружие")
    assert "★" in next(x for x in group.split("\n") if "Клинок Северного Ветра" in x)
    assert "Композитный лук следопыта" in group
    assert "Охотничий кортик" in group


def test_inv_bow_not_marked_when_not_in_hands(dragon_app):
    group = group_of(dragon_app, "Оружие")
    assert "★" not in next(x for x in group.split("\n") if "Композитный лук" in x)


def test_inv_armor_group_marks_worn_shirt(dragon_app):
    group = group_of(dragon_app, "Доспехи и одежда")
    assert "★" in next(x for x in group.split("\n") if "Мифриловая кольчужная рубаха" in x)


def test_inv_ammo_group_lists_special_arrows_with_qty(dragon_app):
    group = group_of(dragon_app, "Боеприпасы")
    for name, qty in [("Бронебойная стрела", 20), ("Морозная стрела", 10),
                      ("Зажигательная стрела", 10), ("Серебряная стрела", 10)]:
        assert str(qty) in next(x for x in group.split("\n") if name in x)


def test_inv_potions_group_has_elixir_with_effect(dragon_app):
    group = group_of(dragon_app, "Зелья и расходники")
    line = next(x for x in group.split("\n") if "Каменная Кожа" in x)
    assert "2" in line
    assert "КД" in line


def test_inv_valuables_group_has_key_and_ring(dragon_app):
    group = group_of(dragon_app, "Ценности и прочее")
    assert "Мастер-ключ Ратуши" in group
    assert "Перстень-печатка Казначея Ольбрехта" in group


def test_inv_key_and_ring_are_not_in_gear_group(dragon_app):
    group = group_of(dragon_app, "Снаряжение и инструменты")
    assert "Мастер-ключ" not in group
    assert "Перстень" not in group


def test_inv_money_is_last_line(dragon_app):
    assert lines_of(dragon_app, "/inv")[-1].startswith("Деньги:")


def test_inv_empty_groups_are_not_printed(dragon_app):
    hero = dragon_app.bundle.heroes[0]
    hero.inventory = [e for e in hero.inventory if not e.item_id.startswith("arrow_")]
    text = text_of(dragon_app, "/inv")
    assert "Боеприпасы" not in text
    assert "Оружие" in text


def test_inv_width_within_80(dragon_app):
    for line in lines_of(dragon_app, "/inv"):
        assert len(line) <= 80


# /sheet

def test_sheet_header_uses_russian_names(dragon_app):
    text = text_of(dragon_app, "/sheet")
    assert "Грей" in text
    assert "человек" in text.lower()
    assert "следопыт" in text.lower()
    assert "3 ур." in text
    assert "Повелитель зверей" in text
    assert "ranger" not in text
    assert "beast_master" not in text


def test_sheet_shows_xp(dragon_app):
    assert "900" in text_of(dragon_app, "/sheet")


def test_sheet_abilities_with_modifiers(dragon_app):
    text = text_of(dragon_app, "/sheet")
    assert "Лов 17 (+3)" in text
    assert "Сил 12 (+1)" in text
    assert "Мдр 15 (+2)" in text


def test_sheet_proficiency_bonus(dragon_app):
    assert "+2" in text_of(dragon_app, "/sheet")
    assert "мастерств" in text_of(dragon_app, "/sheet").lower()


def test_sheet_skills_marked_proficient_and_expertise(dragon_app):
    text = text_of(dragon_app, "/sheet")
    assert "★★Выживание +6" in text
    assert "★Восприятие +4" in text
    assert "★Скрытность +5" in text
    assert "Акробатика +3" in text
    assert "★Акробатика" not in text


def test_sheet_has_feats_style_speed_passive_and_companion(dragon_app):
    text = text_of(dragon_app, "/sheet")
    assert "Бдительность" in text
    assert "Свирепый атакующий" in text
    assert "Стрельба" in text
    assert "Скорость" in text
    assert "Акела" in text


def test_sheet_keeps_ac_and_hp(dragon_app):
    text = text_of(dragon_app, "/sheet")
    assert "КД 15 = Мифриловая кольчужная рубаха 13" in text
    hero = dragon_app.bundle.heroes[0]
    assert f"{hero.creature.hp_current}/{hero.creature.hp_max}" in text


def test_sheet_has_spells_section(dragon_app):
    assert "1 круг: ●●● (3/3)" in text_of(dragon_app, "/sheet")


def test_sheet_width_within_80(dragon_app):
    for line in lines_of(dragon_app, "/sheet"):
        assert len(line) <= 80


# /spells

def test_spells_shows_slots(dragon_app):
    text = text_of(dragon_app, "/spells")
    assert re.search(r"1 круг: [●○]+ \(\d/\d\)", text)


def test_spells_lists_known_spells(dragon_app):
    text = text_of(dragon_app, "/spells")
    for name in ["Метка охотника", "Лечение ран"]:
        assert name in text


def test_spells_marks_concentration(dragon_app):
    line = next(x for x in text_of(dragon_app, "/spells").split("\n") if "Метка охотника" in x)
    assert "К" in line


def test_spells_hunters_mark_free_uses(dragon_app):
    text = text_of(dragon_app, "/spells")
    assert "без ячейки" in text
    assert re.search(r"\d/\d до долгого отдыха", text)


def test_spells_shows_cast_hint(dragon_app):
    assert "читаю" in text_of(dragon_app, "/spells")


def test_spells_width_within_80(dragon_app):
    for line in lines_of(dragon_app, "/spells"):
        assert len(line) <= 80


# /abilities

def test_abilities_class_features_levels_1_to_3(dragon_app):
    text = text_of(dragon_app, "/abilities")
    for name in ["Избранный враг", "Ловкий исследователь"]:
        assert name in text


def test_abilities_subclass_features(dragon_app):
    text = text_of(dragon_app, "/abilities")
    assert "Зверь-спутник" in text
    assert "Чутьё стаи" in text


def test_abilities_include_feats(dragon_app):
    text = text_of(dragon_app, "/abilities")
    assert "Бдительность" in text
    assert "Свирепый атакующий" in text


def test_abilities_do_not_show_higher_level_features(dragon_app):
    text = text_of(dragon_app, "/abilities")
    assert "Дополнительная атака" not in text


def test_abilities_shows_cast_hint(dragon_app):
    assert "читаю" in text_of(dragon_app, "/abilities") or "мастер" in text_of(
        dragon_app, "/abilities")


def test_abilities_width_within_80(dragon_app):
    for line in lines_of(dragon_app, "/abilities"):
        assert len(line) <= 80


# /help

def test_help_lists_spells_and_abilities(dragon_app):
    text = text_of(dragon_app, "/help")
    assert "/spells" in text
    assert "/abilities" in text


# К0а: несколько спутников и «Настроено»

def test_sheet_has_a_line_for_each_companion(dragon_app):
    from ai_dm.state.hero import Companion

    dragon_app.bundle.heroes[0].companions.append(Companion(name="Мунин", kind="ворон", notes=""))
    lines = lines_of(dragon_app, "/sheet")
    assert "Зверь-спутник: Акела (волк)" in lines
    assert "Зверь-спутник: Мунин (ворон)" in lines


def test_sheet_without_companions_has_no_companion_line(dragon_app):
    dragon_app.bundle.heroes[0].companions.clear()
    assert "Зверь-спутник" not in text_of(dragon_app, "/sheet")


def test_sheet_attuned_line_appears_only_when_not_empty(dragon_app):
    assert "Настроено" not in text_of(dragon_app, "/sheet")
    dragon_app.bundle.heroes[0].attuned.append("flame_tongue")
    assert "Настроено: flame_tongue" in lines_of(dragon_app, "/sheet")


def test_feature_groups_put_each_chosen_option_after_its_feature(dragon_app):
    from ai_dm.game.sheet_text import feature_groups

    hero = dragon_app.bundle.heroes[0]
    hero.sheet.primary.subclass_id = "hunter"
    hero.sheet.feature_choices = {"hunters_prey": ["colossus_slayer"]}
    subclass_ids = feature_groups(hero, dragon_app.registry)[1][1]
    at = subclass_ids.index("hunters_prey")
    assert subclass_ids[at + 1] == "colossus_slayer"


def test_sheet_title_uses_primary_class_and_total_level(dragon_app):
    assert lines_of(dragon_app, "/sheet")[0].startswith("Грей — человек, следопыт 3 ур.")
