# Ожидаемый API контента (контракт для реализации).
#
# ai_dm.content.loader
#   load_registry(content_dirs: Sequence[Path] = (), *, include_srd: bool = True) -> ContentRegistry
#       слои по порядку: встроенный SRD (srd/data) -> каждый каталог из content_dirs.
#       Совпадение (kind, id) между слоями -> ContentConflictError со списком конфликтов.
#   ContentError(Exception)                  -- база; str(err) содержит путь файла и поле/значение
#   ContentConflictError(ContentError)       -- .conflicts: list[tuple[str, str]], пары (kind, id)
#
# Раскладка каталога слоя (имя папки зависит от вида; один YAML-файл = один объект-mapping):
#   weapon -> weapons/    armor -> armor/    class -> classes/    species -> species/
#   background -> backgrounds/    feat -> feats/    feature -> features/    item -> items/
#   spell -> spells/    condition -> conditions/    monster -> monsters/    mastery -> masteries/
#   table -> tables/ (xp, proficiency, dc, cr_xp в SRD)
#   subclass -> subclasses/<class_id>/*.yaml
#
# ai_dm.content.registry.ContentRegistry
#   get(kind, id) -> модель; неизвестный id или вид -> KeyError
#   has(kind, id) -> bool
#   ids(kind) -> list[str]                   -- отсортирован
#   all(kind) -> list[модель]                -- отсортирован по id
#   subclasses_of(class_id) -> list[Subclass]
#
# Загрузка собирает ошибки ВСЕХ файлов (а не падает на первом): ContentError, в str(err) --
# путь и поле каждого битого файла.
# Проверки ссылок и закрытых значений (любая -- ContentError с именем значения в тексте):
#   effect.condition -> существующее состояние; навыки (skill_choices.options, background.skills)
#   -- из Skill (18 навыков, content.models.common); background.feat -- черта категории origin;
#   background.equipment -- существующие предметы (weapon/armor/item);
#   effect.add in {proficiency_bonus, spellcasting_modifier, class_level}; при add == class_level
#   обязателен class_id существующего класса; effect.target/when/mode/shape -- закрытые Literal;
#   spell.range_kind in {self, touch, ranged}; spell.duration -- формат Duration ("1m") или
#   instant/instantaneous (-> duration_s = None); Monster.abilities -- ровно шесть ключей Ability.
#
# ai_dm.content.handlers
#   HANDLERS: dict[str, Callable]            -- реестр именованных обработчиков
#   is_known_handler(name: str) -> bool
#
# Минимальные YAML (обязательные поля; остальное -- с умолчаниями, source="custom", license=""):
#   weapon:   id, name, category (simple|martial), kind (melee|ranged), damage_dice, damage_type,
#             cost_cp;  необязательные: properties, mastery, versatile_dice,
#             range_normal_ft, range_long_ft
#   armor:    id, name, category (light|medium|heavy|shield), ac, cost_cp;
#             dex_cap=None, strength_min=0
#   mastery:  id, name
#   feature:  id, name; необязательные: effects, handler {name, params}
#   class:    id, name, hit_die, saving_throws; features: [{level, feature}] (feature -- id умения)
#   item:     id, name, cost_cp
#   subclass: id, class_id, name, features: [{level, feature}]
# Id: lowercase snake_case; extra="forbid" на всех моделях контента.
import pytest

from ai_dm.content import handlers
from ai_dm.content.loader import ContentConflictError, ContentError, load_registry

WEAPON = """\
id: {id}
name: Тестовое оружие
category: martial
kind: melee
damage_dice: 1d8
damage_type: slashing
cost_cp: 1500
"""


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_builtin_srd_loads_without_errors():
    registry = load_registry()
    assert registry.has("weapon", "longsword")


def test_registry_get_returns_model_with_id():
    registry = load_registry()
    assert registry.get("weapon", "longsword").id == "longsword"


def test_registry_get_unknown_id_raises_key_error():
    registry = load_registry()
    with pytest.raises(KeyError):
        registry.get("weapon", "no_such_weapon")


def test_registry_get_unknown_kind_raises_key_error():
    registry = load_registry()
    with pytest.raises(KeyError):
        registry.get("no_such_kind", "longsword")


def test_registry_has_is_false_for_unknown_id():
    registry = load_registry()
    assert registry.has("weapon", "no_such_weapon") is False


def test_registry_ids_are_sorted():
    registry = load_registry()
    ids = registry.ids("weapon")
    assert ids == sorted(ids)


def test_registry_all_returns_models_in_id_order():
    registry = load_registry()
    assert [m.id for m in registry.all("weapon")] == registry.ids("weapon")


def test_second_layer_adds_new_item(tmp_path):
    write(tmp_path / "items" / "ruby.yaml", "id: ruby\nname: Рубин\ncost_cp: 5000\n")
    registry = load_registry([tmp_path])
    assert registry.get("item", "ruby").cost_cp == 5000


def test_second_layer_keeps_srd_content(tmp_path):
    write(tmp_path / "items" / "ruby.yaml", "id: ruby\nname: Рубин\ncost_cp: 5000\n")
    registry = load_registry([tmp_path])
    assert registry.has("weapon", "longsword")


def test_without_srd_layer_srd_content_is_absent(tmp_path):
    write(tmp_path / "items" / "ruby.yaml", "id: ruby\nname: Рубин\ncost_cp: 5000\n")
    registry = load_registry([tmp_path], include_srd=False)
    assert registry.has("weapon", "longsword") is False


def test_same_id_in_two_layers_raises_conflict_error(tmp_path):
    write(tmp_path / "weapons" / "my_sword.yaml", WEAPON.format(id="longsword"))
    with pytest.raises(ContentConflictError):
        load_registry([tmp_path])


def test_conflict_error_lists_kind_and_id(tmp_path):
    write(tmp_path / "weapons" / "my_sword.yaml", WEAPON.format(id="longsword"))
    with pytest.raises(ContentConflictError) as exc:
        load_registry([tmp_path])
    assert ("weapon", "longsword") in exc.value.conflicts


def test_conflict_error_lists_all_conflicts_not_only_first(tmp_path):
    write(tmp_path / "weapons" / "my_sword.yaml", WEAPON.format(id="longsword"))
    write(
        tmp_path / "armor" / "my_shield.yaml",
        "id: shield\nname: Мой щит\ncategory: shield\nac: 2\ncost_cp: 1000\n",
    )
    with pytest.raises(ContentConflictError) as exc:
        load_registry([tmp_path])
    assert ("weapon", "longsword") in exc.value.conflicts
    assert ("armor", "shield") in exc.value.conflicts


def test_conflict_error_message_contains_id(tmp_path):
    write(tmp_path / "weapons" / "my_sword.yaml", WEAPON.format(id="longsword"))
    with pytest.raises(ContentConflictError) as exc:
        load_registry([tmp_path])
    assert "longsword" in str(exc.value)


def test_conflict_error_is_content_error(tmp_path):
    write(tmp_path / "weapons" / "my_sword.yaml", WEAPON.format(id="longsword"))
    with pytest.raises(ContentError):
        load_registry([tmp_path])


def test_same_id_in_two_custom_layers_raises_conflict_error(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    write(first / "items" / "ruby.yaml", "id: ruby\nname: Рубин\ncost_cp: 5000\n")
    write(second / "items" / "ruby.yaml", "id: ruby\nname: Другой рубин\ncost_cp: 1\n")
    with pytest.raises(ContentConflictError):
        load_registry([first, second], include_srd=False)


def test_same_id_in_different_kinds_is_not_a_conflict(tmp_path):
    write(tmp_path / "items" / "longsword.yaml", "id: longsword\nname: Меч-предмет\ncost_cp: 1\n")
    registry = load_registry([tmp_path])
    assert registry.get("item", "longsword").cost_cp == 1


def test_weapon_with_unknown_mastery_raises_error(tmp_path):
    text = WEAPON.format(id="odd_sword") + "mastery: no_such_mastery\n"
    write(tmp_path / "weapons" / "odd_sword.yaml", text)
    with pytest.raises(ContentError) as exc:
        load_registry([tmp_path])
    assert "no_such_mastery" in str(exc.value)


def test_weapon_with_known_mastery_loads(tmp_path):
    text = WEAPON.format(id="odd_sword") + "mastery: sap\n"
    write(tmp_path / "weapons" / "odd_sword.yaml", text)
    registry = load_registry([tmp_path])
    assert registry.get("weapon", "odd_sword").mastery == "sap"


def test_feature_with_unknown_handler_raises_error(tmp_path):
    text = "id: weird\nname: Странное\nhandler:\n  name: no_such_handler\n"
    write(tmp_path / "features" / "weird.yaml", text)
    with pytest.raises(ContentError) as exc:
        load_registry([tmp_path])
    assert "no_such_handler" in str(exc.value)


def test_feature_with_registered_handler_loads(tmp_path, monkeypatch):
    monkeypatch.setitem(handlers.HANDLERS, "test_noop", lambda *args, **kwargs: None)
    text = "id: weird\nname: Странное\nhandler:\n  name: test_noop\n"
    write(tmp_path / "features" / "weird.yaml", text)
    registry = load_registry([tmp_path])
    assert registry.get("feature", "weird").handler.name == "test_noop"


def test_is_known_handler_false_for_unknown_name():
    assert handlers.is_known_handler("no_such_handler") is False


def test_is_known_handler_true_for_registered_name(monkeypatch):
    monkeypatch.setitem(handlers.HANDLERS, "test_noop", lambda *args, **kwargs: None)
    assert handlers.is_known_handler("test_noop") is True


def test_class_with_unknown_feature_raises_error(tmp_path):
    text = (
        "id: test_class\nname: Тестовый\nhit_die: 8\nsaving_throws: [str, con]\n"
        "features:\n  - level: 1\n    feature: no_such_feature\n"
    )
    write(tmp_path / "classes" / "test_class.yaml", text)
    with pytest.raises(ContentError) as exc:
        load_registry([tmp_path])
    assert "no_such_feature" in str(exc.value)


def test_class_with_known_feature_loads(tmp_path):
    text = (
        "id: test_class\nname: Тестовый\nhit_die: 8\nsaving_throws: [str, con]\n"
        "features:\n  - level: 1\n    feature: second_wind\n"
    )
    write(tmp_path / "classes" / "test_class.yaml", text)
    registry = load_registry([tmp_path])
    assert registry.get("class", "test_class").hit_die == 8


def test_extra_field_in_yaml_raises_error(tmp_path):
    text = WEAPON.format(id="odd_sword") + "bogus_field: 1\n"
    write(tmp_path / "weapons" / "bad_weapon.yaml", text)
    with pytest.raises(ContentError):
        load_registry([tmp_path])


def test_extra_field_error_names_the_field(tmp_path):
    text = WEAPON.format(id="odd_sword") + "bogus_field: 1\n"
    write(tmp_path / "weapons" / "bad_weapon.yaml", text)
    with pytest.raises(ContentError) as exc:
        load_registry([tmp_path])
    assert "bogus_field" in str(exc.value)


def test_extra_field_error_names_the_file(tmp_path):
    text = WEAPON.format(id="odd_sword") + "bogus_field: 1\n"
    write(tmp_path / "weapons" / "bad_weapon.yaml", text)
    with pytest.raises(ContentError) as exc:
        load_registry([tmp_path])
    assert "bad_weapon.yaml" in str(exc.value)


def test_missing_required_field_raises_error_with_field_name(tmp_path):
    write(tmp_path / "weapons" / "bad_weapon.yaml", "id: odd_sword\nname: Без урона\n")
    with pytest.raises(ContentError) as exc:
        load_registry([tmp_path])
    assert "damage_dice" in str(exc.value)


def test_uppercase_id_raises_error(tmp_path):
    write(tmp_path / "weapons" / "bad_id.yaml", WEAPON.format(id="BigSword"))
    with pytest.raises(ContentError):
        load_registry([tmp_path])


def test_subclass_loads_from_class_folder(tmp_path):
    text = (
        "id: test_oath\nclass_id: fighter\nname: Тестовая клятва\n"
        "features:\n  - level: 3\n    feature: second_wind\n"
    )
    write(tmp_path / "subclasses" / "fighter" / "test_oath.yaml", text)
    registry = load_registry([tmp_path])
    assert registry.get("subclass", "test_oath").class_id == "fighter"


def test_subclass_keeps_feature_levels(tmp_path):
    text = (
        "id: test_oath\nclass_id: fighter\nname: Тестовая клятва\n"
        "features:\n  - level: 3\n    feature: second_wind\n"
    )
    write(tmp_path / "subclasses" / "fighter" / "test_oath.yaml", text)
    registry = load_registry([tmp_path])
    feature = registry.get("subclass", "test_oath").features[0]
    assert (feature.level, feature.feature) == (3, "second_wind")


def test_subclasses_of_returns_subclass_of_that_class(tmp_path):
    text = "id: test_oath\nclass_id: fighter\nname: Тестовая клятва\nfeatures: []\n"
    write(tmp_path / "subclasses" / "fighter" / "test_oath.yaml", text)
    registry = load_registry([tmp_path])
    assert "test_oath" in [s.id for s in registry.subclasses_of("fighter")]


def test_subclasses_of_other_class_does_not_include_it(tmp_path):
    text = "id: test_oath\nclass_id: fighter\nname: Тестовая клятва\nfeatures: []\n"
    write(tmp_path / "subclasses" / "fighter" / "test_oath.yaml", text)
    registry = load_registry([tmp_path])
    assert "test_oath" not in [s.id for s in registry.subclasses_of("wizard")]


def test_subclass_of_unknown_class_raises_error(tmp_path):
    text = "id: test_oath\nclass_id: no_such_class\nname: Тестовая клятва\nfeatures: []\n"
    write(tmp_path / "subclasses" / "no_such_class" / "test_oath.yaml", text)
    with pytest.raises(ContentError) as exc:
        load_registry([tmp_path])
    assert "no_such_class" in str(exc.value)


def test_subclass_with_unknown_feature_raises_error(tmp_path):
    text = (
        "id: test_oath\nclass_id: fighter\nname: Тестовая клятва\n"
        "features:\n  - level: 3\n    feature: no_such_feature\n"
    )
    write(tmp_path / "subclasses" / "fighter" / "test_oath.yaml", text)
    with pytest.raises(ContentError) as exc:
        load_registry([tmp_path])
    assert "no_such_feature" in str(exc.value)


# ошибки всех файлов собираются вместе

def test_errors_of_several_broken_files_are_reported_together(tmp_path):
    write(tmp_path / "weapons" / "bad_one.yaml", WEAPON.format(id="odd_one") + "bogus_one: 1\n")
    write(tmp_path / "weapons" / "bad_two.yaml", WEAPON.format(id="odd_two") + "bogus_two: 1\n")
    with pytest.raises(ContentError) as exc:
        load_registry([tmp_path])
    text = str(exc.value)
    assert "bad_one.yaml" in text
    assert "bad_two.yaml" in text
    assert "bogus_one" in text
    assert "bogus_two" in text


def test_errors_of_different_kinds_are_reported_together(tmp_path):
    write(tmp_path / "weapons" / "bad_weapon.yaml", "id: odd_sword\nname: Без урона\n")
    write(tmp_path / "items" / "bad_item.yaml", "id: odd_item\nname: Без цены\n")
    with pytest.raises(ContentError) as exc:
        load_registry([tmp_path])
    assert "bad_weapon.yaml" in str(exc.value)
    assert "bad_item.yaml" in str(exc.value)


def test_broken_yaml_and_broken_model_are_reported_together(tmp_path):
    write(tmp_path / "weapons" / "bad_yaml.yaml", "id: [unclosed\n")
    write(tmp_path / "weapons" / "bad_model.yaml", WEAPON.format(id="odd") + "bogus_field: 1\n")
    with pytest.raises(ContentError) as exc:
        load_registry([tmp_path])
    assert "bad_yaml.yaml" in str(exc.value)
    assert "bad_model.yaml" in str(exc.value)


def test_file_error_and_reference_error_are_reported_together(tmp_path):
    write(tmp_path / "weapons" / "bad_model.yaml", WEAPON.format(id="odd") + "bogus_field: 1\n")
    text = "id: odd_sword\nname: x\n" + WEAPON.split("\n", 2)[2] + "mastery: no_such_mastery\n"
    write(tmp_path / "weapons" / "odd_ref.yaml", text)
    with pytest.raises(ContentError) as exc:
        load_registry([tmp_path])
    assert "bogus_field" in str(exc.value)
    assert "no_such_mastery" in str(exc.value)


def test_several_reference_errors_are_reported_together(tmp_path):
    write(
        tmp_path / "classes" / "c1.yaml",
        "id: c_one\nname: Один\nhit_die: 8\nsaving_throws: [str]\n"
        "features:\n  - level: 1\n    feature: no_such_feature_one\n",
    )
    write(
        tmp_path / "classes" / "c2.yaml",
        "id: c_two\nname: Два\nhit_die: 8\nsaving_throws: [str]\n"
        "features:\n  - level: 1\n    feature: no_such_feature_two\n",
    )
    with pytest.raises(ContentError) as exc:
        load_registry([tmp_path])
    assert "no_such_feature_one" in str(exc.value)
    assert "no_such_feature_two" in str(exc.value)


# эффекты: ссылки и закрытые значения

def feature_with_effect(effect_lines):
    return "id: odd_feature\nname: Странное\neffects:\n" + effect_lines


def test_effect_condition_unknown_raises_error(tmp_path):
    text = feature_with_effect("  - type: apply_condition\n    condition: no_such_condition\n")
    write(tmp_path / "features" / "odd_feature.yaml", text)
    with pytest.raises(ContentError) as exc:
        load_registry([tmp_path])
    assert "no_such_condition" in str(exc.value)


def test_effect_condition_known_loads(tmp_path):
    text = feature_with_effect("  - type: apply_condition\n    condition: prone\n")
    write(tmp_path / "features" / "odd_feature.yaml", text)
    registry = load_registry([tmp_path])
    assert registry.get("feature", "odd_feature").effects[0].condition == "prone"


def test_effect_condition_in_spell_is_checked_too(tmp_path):
    text = (
        "id: odd_spell\nname: Странное\nlevel: 1\nschool: evocation\nrange_kind: self\n"
        "effects:\n  - type: apply_condition\n    condition: no_such_condition\n"
    )
    write(tmp_path / "spells" / "odd_spell.yaml", text)
    with pytest.raises(ContentError) as exc:
        load_registry([tmp_path])
    assert "no_such_condition" in str(exc.value)


def test_effect_add_class_level_without_class_id_raises_error(tmp_path):
    text = feature_with_effect("  - type: heal\n    dice: 1d10\n    add: class_level\n")
    write(tmp_path / "features" / "odd_feature.yaml", text)
    with pytest.raises(ContentError) as exc:
        load_registry([tmp_path])
    assert "class_id" in str(exc.value)


def test_effect_add_class_level_with_unknown_class_id_raises_error(tmp_path):
    text = feature_with_effect(
        "  - type: heal\n    dice: 1d10\n    add: class_level\n    class_id: no_such_class\n"
    )
    write(tmp_path / "features" / "odd_feature.yaml", text)
    with pytest.raises(ContentError) as exc:
        load_registry([tmp_path])
    assert "no_such_class" in str(exc.value)


def test_effect_add_class_level_with_known_class_id_loads(tmp_path):
    text = feature_with_effect(
        "  - type: heal\n    dice: 1d10\n    add: class_level\n    class_id: fighter\n"
    )
    write(tmp_path / "features" / "odd_feature.yaml", text)
    registry = load_registry([tmp_path])
    effect = registry.get("feature", "odd_feature").effects[0]
    assert (effect.add, effect.class_id) == ("class_level", "fighter")


@pytest.mark.parametrize("add", ["proficiency_bonus", "spellcasting_modifier"])
def test_effect_add_simple_values_load_without_class_id(tmp_path, add):
    text = feature_with_effect(f"  - type: heal\n    dice: 1d4\n    add: {add}\n")
    write(tmp_path / "features" / "odd_feature.yaml", text)
    registry = load_registry([tmp_path])
    assert registry.get("feature", "odd_feature").effects[0].add == add


def test_effect_add_unknown_value_raises_error(tmp_path):
    text = feature_with_effect("  - type: heal\n    dice: 1d4\n    add: banana\n")
    write(tmp_path / "features" / "odd_feature.yaml", text)
    with pytest.raises(ContentError) as exc:
        load_registry([tmp_path])
    assert "banana" in str(exc.value)


def test_effect_add_old_class_level_colon_form_raises_error(tmp_path):
    text = feature_with_effect("  - type: heal\n    dice: 1d10\n    add: class_level:fighter\n")
    write(tmp_path / "features" / "odd_feature.yaml", text)
    with pytest.raises(ContentError):
        load_registry([tmp_path])


def test_effect_unknown_target_raises_error(tmp_path):
    text = feature_with_effect("  - type: modifier\n    target: banana\n    value: 1\n")
    write(tmp_path / "features" / "odd_feature.yaml", text)
    with pytest.raises(ContentError) as exc:
        load_registry([tmp_path])
    assert "banana" in str(exc.value)


def test_effect_known_target_loads(tmp_path):
    text = feature_with_effect("  - type: modifier\n    target: initiative\n    value: 1\n")
    write(tmp_path / "features" / "odd_feature.yaml", text)
    registry = load_registry([tmp_path])
    assert registry.get("feature", "odd_feature").effects[0].target == "initiative"


def test_effect_unknown_when_raises_error(tmp_path):
    text = feature_with_effect(
        "  - type: modifier\n    target: ac\n    value: 1\n    when: banana\n"
    )
    write(tmp_path / "features" / "odd_feature.yaml", text)
    with pytest.raises(ContentError) as exc:
        load_registry([tmp_path])
    assert "banana" in str(exc.value)


def test_effect_known_when_loads(tmp_path):
    text = feature_with_effect(
        "  - type: modifier\n    target: ac\n    value: 1\n    when: wearing_armor\n"
    )
    write(tmp_path / "features" / "odd_feature.yaml", text)
    registry = load_registry([tmp_path])
    assert registry.get("feature", "odd_feature").effects[0].when == "wearing_armor"


def test_effect_unknown_mode_raises_error(tmp_path):
    text = feature_with_effect("  - type: save_effect\n    ability: dex\n    mode: banana\n")
    write(tmp_path / "features" / "odd_feature.yaml", text)
    with pytest.raises(ContentError) as exc:
        load_registry([tmp_path])
    assert "banana" in str(exc.value)


def test_effect_known_mode_loads(tmp_path):
    text = feature_with_effect("  - type: save_effect\n    ability: dex\n    mode: half\n")
    write(tmp_path / "features" / "odd_feature.yaml", text)
    registry = load_registry([tmp_path])
    assert registry.get("feature", "odd_feature").effects[0].mode == "half"


def test_effect_unknown_shape_raises_error(tmp_path):
    text = feature_with_effect("  - type: area\n    shape: banana\n    size_ft: 15\n")
    write(tmp_path / "features" / "odd_feature.yaml", text)
    with pytest.raises(ContentError) as exc:
        load_registry([tmp_path])
    assert "banana" in str(exc.value)


def test_effect_known_shape_loads(tmp_path):
    text = feature_with_effect("  - type: area\n    shape: cone\n    size_ft: 15\n")
    write(tmp_path / "features" / "odd_feature.yaml", text)
    registry = load_registry([tmp_path])
    assert registry.get("feature", "odd_feature").effects[0].shape == "cone"


def test_effect_targets_and_count_are_separate_fields(tmp_path):
    text = feature_with_effect("  - type: modifier\n    target: attack_roll\n    targets: 3\n")
    write(tmp_path / "features" / "odd_feature.yaml", text)
    effect = load_registry([tmp_path]).get("feature", "odd_feature").effects[0]
    assert effect.targets == 3
    assert effect.count is None


def test_resource_effect_with_pool_and_recover_loads(tmp_path):
    text = feature_with_effect(
        "  - type: resource\n    pool: odd_pool\n    max: 3\n    recover:\n"
        "      - \"on\": short_rest\n        amount: 1\n"
        "      - \"on\": long_rest\n        amount: all\n"
    )
    write(tmp_path / "features" / "odd_feature.yaml", text)
    effect = load_registry([tmp_path]).get("feature", "odd_feature").effects[0]
    assert effect.pool == "odd_pool"
    assert effect.max == 3
    assert len(effect.recover) == 2


def test_resource_effect_with_unknown_recover_event_raises_error(tmp_path):
    text = feature_with_effect(
        "  - type: resource\n    pool: odd_pool\n    max: 1\n    recover:\n"
        "      - \"on\": banana\n        amount: 1\n"
    )
    write(tmp_path / "features" / "odd_feature.yaml", text)
    with pytest.raises(ContentError) as exc:
        load_registry([tmp_path])
    assert "banana" in str(exc.value)


def test_resource_effect_with_unknown_recover_amount_raises_error(tmp_path):
    text = feature_with_effect(
        "  - type: resource\n    pool: odd_pool\n    max: 1\n    recover:\n"
        "      - \"on\": long_rest\n        amount: banana\n"
    )
    write(tmp_path / "features" / "odd_feature.yaml", text)
    with pytest.raises(ContentError):
        load_registry([tmp_path])


# навыки, предыстории, черты

def test_class_skill_option_outside_skill_list_raises_error(tmp_path):
    text = (
        "id: test_class\nname: Тестовый\nhit_die: 8\nsaving_throws: [str]\n"
        "skill_choices:\n  count: 1\n  options: [juggling]\n"
    )
    write(tmp_path / "classes" / "test_class.yaml", text)
    with pytest.raises(ContentError) as exc:
        load_registry([tmp_path])
    assert "juggling" in str(exc.value)


def test_class_skill_option_from_skill_list_loads(tmp_path):
    text = (
        "id: test_class\nname: Тестовый\nhit_die: 8\nsaving_throws: [str]\n"
        "skill_choices:\n  count: 1\n  options: [stealth, nature]\n"
    )
    write(tmp_path / "classes" / "test_class.yaml", text)
    registry = load_registry([tmp_path])
    assert registry.get("class", "test_class").skill_choices.options == ["stealth", "nature"]


BACKGROUND = """\
id: odd_background
name: Странная
abilities: [str, dex, con]
skills: [{skill_a}, {skill_b}]
tool: gaming_set
feat: {feat}
"""


def test_background_skill_outside_skill_list_raises_error(tmp_path):
    text = BACKGROUND.format(skill_a="stealth", skill_b="juggling", feat="alert")
    write(tmp_path / "backgrounds" / "odd_background.yaml", text)
    with pytest.raises(ContentError) as exc:
        load_registry([tmp_path])
    assert "juggling" in str(exc.value)


def test_background_with_known_skills_and_origin_feat_loads(tmp_path):
    text = BACKGROUND.format(skill_a="stealth", skill_b="nature", feat="alert")
    write(tmp_path / "backgrounds" / "odd_background.yaml", text)
    registry = load_registry([tmp_path])
    assert registry.get("background", "odd_background").feat == "alert"


def test_background_feat_not_origin_raises_error(tmp_path):
    text = BACKGROUND.format(skill_a="stealth", skill_b="nature", feat="defense")
    write(tmp_path / "backgrounds" / "odd_background.yaml", text)
    with pytest.raises(ContentError) as exc:
        load_registry([tmp_path])
    assert "defense" in str(exc.value)


def test_background_feat_unknown_raises_error(tmp_path):
    text = BACKGROUND.format(skill_a="stealth", skill_b="nature", feat="no_such_feat")
    write(tmp_path / "backgrounds" / "odd_background.yaml", text)
    with pytest.raises(ContentError) as exc:
        load_registry([tmp_path])
    assert "no_such_feat" in str(exc.value)


def test_background_equipment_and_gold_load(tmp_path):
    text = BACKGROUND.format(skill_a="stealth", skill_b="nature", feat="alert")
    write(
        tmp_path / "backgrounds" / "odd_background.yaml",
        text + "equipment: [dagger, shield]\ngold_cp: 1500\n",
    )
    background = load_registry([tmp_path]).get("background", "odd_background")
    assert background.equipment == ["dagger", "shield"]
    assert background.gold_cp == 1500


def test_background_equipment_unknown_item_raises_error(tmp_path):
    text = BACKGROUND.format(skill_a="stealth", skill_b="nature", feat="alert")
    write(
        tmp_path / "backgrounds" / "odd_background.yaml",
        text + "equipment: [no_such_item]\ngold_cp: 100\n",
    )
    with pytest.raises(ContentError) as exc:
        load_registry([tmp_path])
    assert "no_such_item" in str(exc.value)


# заклинания: дальность и длительность

SPELL = """\
id: odd_spell
name: Странное
level: 1
school: evocation
"""


def test_spell_range_kind_unknown_raises_error(tmp_path):
    write(tmp_path / "spells" / "odd_spell.yaml", SPELL + "range_kind: banana\n")
    with pytest.raises(ContentError) as exc:
        load_registry([tmp_path])
    assert "banana" in str(exc.value)


@pytest.mark.parametrize("kind", ["self", "touch"])
def test_spell_self_and_touch_load_without_range_ft(tmp_path, kind):
    write(tmp_path / "spells" / "odd_spell.yaml", SPELL + f"range_kind: {kind}\n")
    assert load_registry([tmp_path]).get("spell", "odd_spell").range_kind == kind


def test_spell_ranged_keeps_range_ft(tmp_path):
    write(tmp_path / "spells" / "odd_spell.yaml", SPELL + "range_kind: ranged\nrange_ft: 60\n")
    spell = load_registry([tmp_path]).get("spell", "odd_spell")
    assert (spell.range_kind, spell.range_ft) == ("ranged", 60)


@pytest.mark.parametrize(
    "duration, seconds",
    [("1m", 60), ("10m", 600), ("1h", 3600), ("instant", None), ("instantaneous", None)],
)
def test_spell_duration_is_converted_to_seconds(tmp_path, duration, seconds):
    write(
        tmp_path / "spells" / "odd_spell.yaml",
        SPELL + f"range_kind: self\nduration: {duration}\n",
    )
    assert load_registry([tmp_path]).get("spell", "odd_spell").duration_s == seconds


def test_spell_duration_in_words_raises_error(tmp_path):
    write(
        tmp_path / "spells" / "odd_spell.yaml",
        SPELL + "range_kind: self\nduration: 1 minute\n",
    )
    with pytest.raises(ContentError):
        load_registry([tmp_path])


def test_spell_duration_garbage_raises_error(tmp_path):
    write(
        tmp_path / "spells" / "odd_spell.yaml",
        SPELL + "range_kind: self\nduration: soon\n",
    )
    with pytest.raises(ContentError):
        load_registry([tmp_path])


# монстры и таблицы

MONSTER = """\
id: odd_monster
name: Странный
ac: 10
hp: 5
cr: 1/8
abilities:
  str: 10
  dex: 10
  con: 10
  int: 10
  wis: 10
  cha: 10
"""


def test_monster_with_all_six_abilities_loads(tmp_path):
    write(tmp_path / "monsters" / "odd_monster.yaml", MONSTER)
    assert load_registry([tmp_path]).get("monster", "odd_monster").hp == 5


def test_monster_with_xp_field_raises_error(tmp_path):
    # аудит 1 п. 2.11: опыт берётся из tables/cr_xp по cr, поля xp у монстра нет
    with_xp = MONSTER.replace("cr: 1/8\n", "cr: 1/8\nxp: 25\n")
    write(tmp_path / "monsters" / "odd_monster.yaml", with_xp)
    with pytest.raises(ContentError):
        load_registry([tmp_path])


def test_monster_with_unknown_ability_key_raises_error(tmp_path):
    write(tmp_path / "monsters" / "odd_monster.yaml", MONSTER.replace("  cha: 10", "  luck: 10"))
    with pytest.raises(ContentError):
        load_registry([tmp_path])


def test_monster_with_missing_ability_raises_error(tmp_path):
    write(tmp_path / "monsters" / "odd_monster.yaml", MONSTER.replace("  cha: 10\n", ""))
    with pytest.raises(ContentError):
        load_registry([tmp_path])


def test_table_from_second_layer_conflicts_with_srd_table(tmp_path):
    write(tmp_path / "tables" / "xp.yaml", "id: xp\nname: Опыт\n")
    with pytest.raises((ContentError, ContentConflictError)):
        load_registry([tmp_path])
