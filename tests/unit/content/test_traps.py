# Шаг 262 П1: реестр ловушек (kind "trap", srd/data/traps/*.yaml; решения 8, 17, 22, 24).
# Ожидание из docs/plan-262.md «Тесты» П1: 8 ловушек, имена дословно, severity из трёх значений,
# detect.skill -- perception|investigation, «Яма с кольями» dangerous, смертельной без save нет,
# неизвестное состояние/навык -> ContentError с путём файла. Числа с PDF не сверяются.
import pytest
import yaml

from ai_dm.content.loader import SRD_DIR, ContentError, load_registry

NAMES = {
    "Обрушение свода", "Падающая сеть", "Огненная статуя", "Скрытая яма",
    "Отравленные дротики", "Отравленная игла", "Катящийся камень", "Яма с кольями",
}


def traps(registry):
    return registry.all("trap")


def by_name(registry, name):
    return next(t for t in traps(registry) if t.name == name)


def test_registry_has_eight_traps(registry):
    assert len(registry.ids("trap")) == 8


def test_trap_names_are_exactly_the_agreed_eight(registry):
    assert {t.name for t in traps(registry)} == NAMES


def test_every_trap_severity_is_one_of_three(registry):
    assert {t.severity for t in traps(registry)} <= {"nuisance", "dangerous", "deadly"}


def test_every_trap_detect_skill_is_perception_or_investigation(registry):
    assert {t.detect.skill for t in traps(registry)} <= {"perception", "investigation"}


def test_spiked_pit_is_dangerous(registry):
    assert by_name(registry, "Яма с кольями").severity == "dangerous"


def test_no_deadly_trap_without_save(registry):
    assert [t.id for t in traps(registry) if t.severity == "deadly" and t.save is None] == []


def test_no_trap_without_save_has_deadly_in_severity_by_level(registry):
    bad = [
        t.id for t in traps(registry)
        if t.save is None and "deadly" in t.severity_by_level.values()
    ]
    assert bad == []


def test_rolling_stone_levels_eleven_to_twenty(registry):
    assert by_name(registry, "Катящийся камень").levels == [11, 20]


def test_rolling_stone_base_severity_is_dangerous(registry):
    assert by_name(registry, "Катящийся камень").severity == "dangerous"


def test_rolling_stone_is_nuisance_on_levels_17_to_20(registry):
    assert by_name(registry, "Катящийся камень").severity_by_level == {"17-20": "nuisance"}


def test_other_traps_have_empty_severity_by_level(registry):
    others = [t for t in traps(registry) if t.name != "Катящийся камень"]
    assert len(others) == 7
    assert [t.severity_by_level for t in others] == [{}] * 7


def test_fire_statue_is_detected_by_perception_dc_15(registry):
    statue = by_name(registry, "Огненная статуя")
    assert (statue.detect.skill, statue.detect.dc) == ("perception", 15)


def test_trap_ids_are_lowercase_snake_case(registry):
    assert all(i == i.lower() and " " not in i for i in registry.ids("trap"))


def write_variant(tmp_path, mutate, stem=None):
    # копия живой ловушки с другим id и правкой одного поля; форма данных берётся из репо
    source = (SRD_DIR / "traps" / f"{stem}.yaml") if stem else sorted(
        (SRD_DIR / "traps").glob("*.yaml")
    )[0]
    data = yaml.safe_load(source.read_text(encoding="utf-8"))
    data["id"] = "odd_trap"
    mutate(data)
    path = tmp_path / "traps" / "odd_trap.yaml"
    path.parent.mkdir(parents=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return path


def test_trap_with_unknown_condition_raises_content_error_with_path(tmp_path):
    path = write_variant(tmp_path, lambda d: d.update(condition="no_such_condition"))
    with pytest.raises(ContentError) as exc:
        load_registry([tmp_path])
    assert str(path) in str(exc.value)


def test_trap_with_unknown_condition_names_the_value(tmp_path):
    write_variant(tmp_path, lambda d: d.update(condition="no_such_condition"))
    with pytest.raises(ContentError) as exc:
        load_registry([tmp_path])
    assert "no_such_condition" in str(exc.value)


def test_trap_with_unknown_condition_error_line_has_kind_id_and_field(tmp_path):
    path = write_variant(tmp_path, lambda d: d.update(condition="no_such_condition"))
    with pytest.raises(ContentError) as exc:
        load_registry([tmp_path])
    assert (
        f"{path}: trap 'odd_trap', поле condition: неизвестное состояние 'no_such_condition'"
        in str(exc.value)
    )


def test_trap_with_unknown_damage_type_error_line_has_kind_id_and_field(tmp_path):
    path = write_variant(tmp_path, lambda d: d.update(damage_type="no_such_type"))
    with pytest.raises(ContentError) as exc:
        load_registry([tmp_path])
    assert (
        f"{path}: trap 'odd_trap', поле damage_type: неизвестный тип урона 'no_such_type'"
        in str(exc.value)
    )


def test_trap_with_unknown_skill_raises_content_error_with_path(tmp_path):
    def mutate(data):
        data["detect"]["skill"] = "no_such_skill"

    path = write_variant(tmp_path, mutate)
    with pytest.raises(ContentError) as exc:
        load_registry([tmp_path])
    assert str(path) in str(exc.value)


def test_trap_variant_without_changes_loads(tmp_path):
    write_variant(tmp_path, lambda d: None)
    assert load_registry([tmp_path]).has("trap", "odd_trap")


def test_attribution_has_traps_section_and_unverified_note():
    text = (SRD_DIR / "ATTRIBUTION.md").read_text(encoding="utf-8")
    section = text.split("## Ловушки", 1)[1]
    assert "с PDF не сверено" in section


def test_attribution_has_rolling_stone_line_with_dangerous():
    text = (SRD_DIR / "ATTRIBUTION.md").read_text(encoding="utf-8")
    section = text.split("## Ловушки", 1)[1].split("\n## ", 1)[0]
    assert any("Катящийся камень" in s and "dangerous" in s for s in section.splitlines())


def test_severity_by_level_with_bad_band_key_raises_content_error_with_path(tmp_path):
    path = write_variant(
        tmp_path, lambda d: d.update(severity_by_level={"3-9": "nuisance"}), "rolling_stone"
    )
    with pytest.raises(ContentError) as exc:
        load_registry([tmp_path])
    assert str(path) in str(exc.value)


def test_severity_by_level_with_bad_severity_raises_content_error_with_path(tmp_path):
    path = write_variant(
        tmp_path, lambda d: d.update(severity_by_level={"17-20": "harmless"}), "rolling_stone"
    )
    with pytest.raises(ContentError) as exc:
        load_registry([tmp_path])
    assert str(path) in str(exc.value)


def test_trap_bands_equal_hazard_bands():
    from ai_dm.content.models.traps import BANDS
    from ai_dm.rules.damage import HAZARD_BANDS

    assert BANDS == HAZARD_BANDS


def test_severity_by_level_with_valid_band_loads(tmp_path):
    write_variant(
        tmp_path, lambda d: d.update(severity_by_level={"17-20": "nuisance"}), "rolling_stone"
    )
    assert load_registry([tmp_path]).has("trap", "odd_trap")
