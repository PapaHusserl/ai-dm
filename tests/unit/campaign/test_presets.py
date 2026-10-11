# Лёгкий пресет мира (Б0-П2, B0-PLAN A6, A7, Q3, Q5). Ожидаемый API:
#   ai_dm.campaign.presets.WorldPreset(id, name, description, tone: Tone), extra="forbid";
#   load_presets() -> dict[str, WorldPreset] (presets.yaml: heroic, grim, romantic, fairytale);
#   PACK_TONE == "pack" (служебное значение «как в паке», не пресет каталога);
#   apply_preset(pack_tone, preset) -> Tone: оси, mood и notes -- из пресета; hard_limits и
#   soft_limits -- объединение пака и пресета без дублей, пак первым; pack_tone не меняется.
import pytest
from pydantic import ValidationError

from ai_dm.state.world import Tone

IDS = ["fairytale", "grim", "heroic", "romantic"]


def preset_of(**tone):
    from ai_dm.campaign.presets import WorldPreset

    return WorldPreset(id="x", name="Икс", description="Описание", tone=Tone(**tone))


def test_catalog_has_four_presets():
    from ai_dm.campaign.presets import load_presets

    assert sorted(load_presets()) == IDS


def test_catalog_keys_match_preset_ids():
    from ai_dm.campaign.presets import load_presets

    for key, preset in load_presets().items():
        assert preset.id == key


def test_pack_tone_marker_is_not_in_catalog():
    from ai_dm.campaign.presets import PACK_TONE, load_presets

    assert PACK_TONE == "pack"
    assert PACK_TONE not in load_presets()


@pytest.mark.parametrize("preset_id", IDS)
def test_every_preset_has_name_description_and_voice(preset_id):
    from ai_dm.campaign.presets import load_presets

    preset = load_presets()[preset_id]
    assert preset.name.strip()
    assert preset.description.strip()
    assert preset.tone.notes.strip()


@pytest.mark.parametrize("preset_id", IDS)
def test_every_preset_has_all_axes_and_mood(preset_id):
    from ai_dm.campaign.presets import load_presets

    tone = load_presets()[preset_id].tone
    assert tone.mood.strip()
    assert tone.violence
    assert tone.horror
    assert tone.romance
    assert tone.language


@pytest.mark.parametrize("preset_id", IDS)
def test_preset_tone_is_valid_tone(preset_id):
    from ai_dm.campaign.presets import load_presets

    tone = load_presets()[preset_id].tone
    assert Tone.model_validate(tone.model_dump()) == tone


@pytest.mark.parametrize("preset_id", IDS)
def test_preset_has_no_limits(preset_id):
    from ai_dm.campaign.presets import load_presets

    tone = load_presets()[preset_id].tone
    assert tone.hard_limits == []
    assert tone.soft_limits == []


def test_romance_never_above_explicit():
    from ai_dm.campaign.presets import load_presets

    allowed = {"нет", "намёки", "чувственно", "откровенно"}
    assert {p.tone.romance for p in load_presets().values()} <= allowed


@pytest.mark.parametrize(
    "preset_id, violence, horror, romance, language",
    [
        ("heroic", "реалистично", "умеренно", "намёки", "сдержанно"),
        ("grim", "жестоко", "сильно", "откровенно", "грубо"),
        ("romantic", "мягко", "умеренно", "чувственно", "сдержанно"),
        ("fairytale", "мягко", "нет", "нет", "сдержанно"),
    ],
)
def test_catalog_axes_match_plan(preset_id, violence, horror, romance, language):
    from ai_dm.campaign.presets import load_presets

    tone = load_presets()[preset_id].tone
    assert (tone.violence, tone.horror, tone.romance, tone.language) == (
        violence, horror, romance, language,
    )


def test_voices_are_different():
    from ai_dm.campaign.presets import load_presets

    voices = [p.tone.notes for p in load_presets().values()]
    assert len(set(voices)) == 4


def test_names_are_different():
    from ai_dm.campaign.presets import load_presets

    names = [p.name for p in load_presets().values()]
    assert len(set(names)) == 4


def test_load_presets_returns_equal_catalog_each_time():
    from ai_dm.campaign.presets import load_presets

    assert load_presets() == load_presets()


def test_preset_rejects_extra_field():
    from ai_dm.campaign.presets import WorldPreset

    with pytest.raises(ValidationError):
        WorldPreset(id="x", name="Икс", description="д", tone=Tone(), colour="red")


def test_preset_rejects_bad_axis_value():
    with pytest.raises(ValidationError):
        preset_of(romance="есть")


# apply_preset

def pack_tone():
    return Tone(
        mood="авторский", violence="жестоко", horror="нет", romance="намёки", language="грубо",
        hard_limits=["a", "b"], soft_limits=["s1"], notes="голос пака",
    )


def test_apply_takes_axes_from_preset():
    from ai_dm.campaign.presets import apply_preset

    preset = preset_of(
        violence="мягко", horror="сильно", romance="откровенно", language="сдержанно",
    )
    result = apply_preset(pack_tone(), preset)
    assert result.violence == "мягко"
    assert result.horror == "сильно"
    assert result.romance == "откровенно"
    assert result.language == "сдержанно"


def test_apply_takes_mood_from_preset():
    from ai_dm.campaign.presets import apply_preset

    result = apply_preset(pack_tone(), preset_of(mood="светло"))
    assert result.mood == "светло"


def test_apply_voice_replaces_pack_notes():
    from ai_dm.campaign.presets import apply_preset

    result = apply_preset(pack_tone(), preset_of(notes="голос пресета"))
    assert result.notes == "голос пресета"
    assert "голос пака" not in result.notes


def test_apply_hard_limits_are_union_pack_first():
    from ai_dm.campaign.presets import apply_preset

    result = apply_preset(pack_tone(), preset_of(hard_limits=["c", "d"]))
    assert result.hard_limits == ["a", "b", "c", "d"]


def test_apply_soft_limits_are_union_pack_first():
    from ai_dm.campaign.presets import apply_preset

    result = apply_preset(pack_tone(), preset_of(soft_limits=["s2"]))
    assert result.soft_limits == ["s1", "s2"]


def test_apply_hard_limits_without_duplicates():
    from ai_dm.campaign.presets import apply_preset

    result = apply_preset(pack_tone(), preset_of(hard_limits=["b", "c", "a"]))
    assert result.hard_limits == ["a", "b", "c"]


def test_apply_soft_limits_without_duplicates():
    from ai_dm.campaign.presets import apply_preset

    result = apply_preset(pack_tone(), preset_of(soft_limits=["s1", "s1"]))
    assert result.soft_limits == ["s1"]


def test_apply_empty_preset_limits_keep_pack_limits():
    from ai_dm.campaign.presets import apply_preset

    result = apply_preset(pack_tone(), preset_of())
    assert result.hard_limits == ["a", "b"]
    assert result.soft_limits == ["s1"]


def test_apply_to_empty_pack_limits_gives_preset_limits():
    from ai_dm.campaign.presets import apply_preset

    result = apply_preset(Tone(), preset_of(hard_limits=["c"], soft_limits=["s2"]))
    assert result.hard_limits == ["c"]
    assert result.soft_limits == ["s2"]


def test_apply_does_not_mutate_pack_tone():
    from ai_dm.campaign.presets import apply_preset

    pack = pack_tone()
    apply_preset(pack, preset_of(mood="m", hard_limits=["c"], soft_limits=["s2"], notes="n"))
    assert pack == pack_tone()


def test_apply_does_not_mutate_preset():
    from ai_dm.campaign.presets import apply_preset

    preset = preset_of(mood="m", hard_limits=["c"], notes="n")
    before = preset.model_copy(deep=True)
    apply_preset(pack_tone(), preset)
    assert preset == before


def test_apply_result_is_independent_from_inputs():
    from ai_dm.campaign.presets import apply_preset

    pack = pack_tone()
    preset = preset_of(hard_limits=["c"], soft_limits=["s2"])
    result = apply_preset(pack, preset)
    result.hard_limits.append("zzz")
    result.soft_limits.append("zzz")
    assert pack.hard_limits == ["a", "b"]
    assert pack.soft_limits == ["s1"]
    assert preset.tone.hard_limits == ["c"]
    assert preset.tone.soft_limits == ["s2"]


def test_apply_catalog_grim_over_pack_tone():
    from ai_dm.campaign.presets import apply_preset, load_presets

    grim = load_presets()["grim"]
    result = apply_preset(pack_tone(), grim)
    assert result.model_dump(exclude={"hard_limits", "soft_limits"}) == grim.tone.model_dump(
        exclude={"hard_limits", "soft_limits"}
    )
    assert result.hard_limits == ["a", "b"]


# load_presets: проверки каталога (подмена источника данных)

def catalog_text(*items):
    import yaml

    return yaml.safe_dump(list(items), allow_unicode=True)


def item(preset_id="a", notes="голос"):
    return {"id": preset_id, "name": "Имя", "description": "д", "tone": {"notes": notes}}


def use_catalog(monkeypatch, tmp_path, text):
    from importlib import resources

    (tmp_path / "presets.yaml").write_text(text, encoding="utf-8")
    monkeypatch.setattr(resources, "files", lambda package: tmp_path)


def test_load_presets_reads_substituted_catalog(monkeypatch, tmp_path):
    from ai_dm.campaign.presets import load_presets

    use_catalog(monkeypatch, tmp_path, catalog_text(item("a"), item("b")))
    assert list(load_presets()) == ["a", "b"]


def test_load_presets_duplicate_id_is_error(monkeypatch, tmp_path):
    from ai_dm.campaign.presets import load_presets

    use_catalog(monkeypatch, tmp_path, catalog_text(item("a"), item("a")))
    with pytest.raises(ValueError):
        load_presets()


def test_load_presets_empty_voice_is_error(monkeypatch, tmp_path):
    from ai_dm.campaign.presets import load_presets

    use_catalog(monkeypatch, tmp_path, catalog_text(item("a", notes="")))
    with pytest.raises(ValueError):
        load_presets()


def test_load_presets_bad_axis_is_error(monkeypatch, tmp_path):
    from ai_dm.campaign.presets import load_presets

    bad = item("a")
    bad["tone"]["romance"] = "есть"
    use_catalog(monkeypatch, tmp_path, catalog_text(bad))
    with pytest.raises(ValidationError):
        load_presets()


# кодовое имя пресета (необязательное поле codename: только для экрана выбора)

CODENAMES = {
    "heroic": "Властелин колец", "grim": "Ведьмак", "romantic": "Сумерки",
    "fairytale": "Хроники Нарнии",
}


@pytest.mark.parametrize("preset_id", IDS)
def test_catalog_preset_has_codename(preset_id):
    from ai_dm.campaign.presets import load_presets

    assert load_presets()[preset_id].codename == CODENAMES[preset_id]


def test_preset_codename_is_optional():
    assert not preset_of().codename


def test_codename_is_not_in_tone():
    from ai_dm.campaign.presets import load_presets

    for preset in load_presets().values():
        assert preset.codename not in preset.tone.model_dump_json()


def test_apply_preset_does_not_put_codename_into_tone():
    from ai_dm.campaign.presets import apply_preset, load_presets

    for preset in load_presets().values():
        tone = apply_preset(Tone(), preset)
        assert preset.codename not in tone.model_dump_json()
