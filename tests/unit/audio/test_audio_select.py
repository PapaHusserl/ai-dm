# Му-а (MU-PLAN B1): ai_dm.audio.select.pick_theme(index, state) -> id темы | None.
# Приоритет (В1в): бой > точный id локации > первый известный тег > тон мира (horror сильно -> dark,
# иначе explore). Романтика на выбор не влияет (Q1а). Теги в state уже с тегами родителей.
import pytest
from audio_kit import index, state

from ai_dm.audio.select import pick_theme


def test_combat_wins_over_everything():
    st = state(in_combat=True, location_id="vault", tags=("таверна",), horror="сильно")
    assert pick_theme(index(), st) == "combat"


def test_combat_theme_comes_from_index():
    assert pick_theme(index(combat="dark"), state(in_combat=True)) == "dark"


def test_exact_location_id_wins_over_tags():
    assert pick_theme(index(), state(location_id="vault", tags=("таверна",))) == "dungeon"


def test_exact_location_id_wins_over_tone():
    assert pick_theme(index(), state(location_id="vault", horror="сильно")) == "dungeon"


def test_first_known_tag_gives_theme():
    assert pick_theme(index(), state(tags=("таверна",))) == "tavern"


def test_tag_wins_over_strong_horror():
    assert pick_theme(index(), state(tags=("город",), horror="сильно")) == "town"


def test_tag_order_is_priority():
    assert pick_theme(index(), state(tags=("руины", "город"))) == "dungeon"
    assert pick_theme(index(), state(tags=("город", "руины"))) == "town"


def test_unknown_tags_are_skipped():
    assert pick_theme(index(), state(tags=("нечто", "лес"))) == "nature"


def test_parent_tag_works_when_own_tags_are_unknown():
    # свои теги первыми, теги родителей следом
    assert pick_theme(index(), state(tags=("зачищено", "город"))) == "town"


def test_location_id_without_entry_falls_to_tags():
    assert pick_theme(index(), state(location_id="nowhere", tags=("лес",))) == "nature"


def test_location_id_none_falls_to_tags():
    assert pick_theme(index(), state(location_id=None, tags=("лес",))) == "nature"


def test_no_tags_and_strong_horror_gives_dark():
    assert pick_theme(index(), state(horror="сильно")) == "dark"


def test_horror_theme_comes_from_index():
    idx = index(tone={"horror_strong": "nature", "default": "explore"})
    assert pick_theme(idx, state(horror="сильно")) == "nature"


@pytest.mark.parametrize("horror", ["", "нет", "умеренно"])
def test_other_horror_gives_explore(horror):
    assert pick_theme(index(), state(horror=horror)) == "explore"


def test_default_theme_comes_from_index():
    idx = index(tone={"horror_strong": "dark", "default": "town"})
    assert pick_theme(idx, state()) == "town"


@pytest.mark.parametrize("romance", ["", "нет", "намёки", "чувственно", "откровенно"])
def test_romance_does_not_change_the_choice(romance):
    assert pick_theme(index(), state(tags=("лес",), romance=romance)) == "nature"
    assert pick_theme(index(), state(romance=romance)) == "explore"
    assert pick_theme(index(), state(horror="сильно", romance=romance)) == "dark"


# решения 6-7 ревью Му-б: варианты тем по тону (horror_variants, romance_variants)

def varied(**kw):
    from audio_kit import index_dict

    tone = {
        "horror_strong": "dark", "default": "explore",
        "horror_variants": {"nature": "wilds"},
        "romance_variants": {"откровенно": {"romance": "romance_sensual"}},
    }
    data = index_dict()
    data["themes"]["wilds"] = {"music": "wilds.ogg"}
    data["themes"]["romance_sensual"] = {"music": "romance_sensual.ogg"}
    data["location_tags"]["чаща"] = "wilds"
    data["location_tags"]["любовь"] = "romance"
    return index(themes=data["themes"], location_tags=data["location_tags"], tone={**tone, **kw})


def test_strong_horror_turns_nature_into_wilds():
    assert pick_theme(varied(), state(tags=("лес",), horror="сильно")) == "wilds"


def test_no_horror_keeps_nature():
    assert pick_theme(varied(), state(tags=("лес",))) == "nature"


def test_weak_horror_keeps_nature():
    assert pick_theme(varied(), state(tags=("лес",), horror="слабо")) == "nature"


def test_strong_horror_leaves_theme_without_variant_alone():
    assert pick_theme(varied(), state(tags=("город",), horror="сильно")) == "town"


def test_wilds_tag_gives_wilds_without_horror():
    assert pick_theme(varied(), state(tags=("чаща",))) == "wilds"


def test_strong_horror_variant_applies_to_exact_location_theme():
    idx = varied(horror_variants={"dungeon": "dark"})
    assert pick_theme(idx, state(location_id="vault", horror="сильно")) == "dark"


def test_explicit_romance_turns_romance_into_sensual():
    st = state(tags=("любовь",), romance="откровенно")
    assert pick_theme(varied(), st) == "romance_sensual"


def test_other_romance_level_keeps_romance():
    st = state(tags=("любовь",), romance="мягко")
    assert pick_theme(varied(), st) == "romance"


def test_explicit_romance_does_not_change_other_themes():
    assert pick_theme(varied(), state(tags=("город",), romance="откровенно")) == "town"


def test_romance_variant_applies_to_tone_default_theme():
    idx = varied(default="romance")
    assert pick_theme(idx, state(romance="откровенно")) == "romance_sensual"


def test_strong_horror_and_explicit_romance_apply_in_turn():
    idx = varied(horror_variants={"nature": "romance"})
    st = state(tags=("лес",), horror="сильно", romance="откровенно")
    assert pick_theme(idx, st) == "romance_sensual"


def test_combat_wins_over_variants():
    st = state(in_combat=True, tags=("лес",), horror="сильно", romance="откровенно")
    assert pick_theme(varied(), st) == "combat"


def test_strong_horror_without_tag_gives_dark_not_variant():
    assert pick_theme(varied(), state(horror="сильно")) == "dark"


def test_tone_theme_and_variant_helpers():
    from ai_dm.audio.select import tone_theme, tone_variant

    idx = varied()
    assert tone_theme(idx, state(horror="сильно")) == "dark"
    assert tone_theme(idx, state()) == "explore"
    assert tone_variant(idx, state(horror="сильно"), "nature") == "wilds"
    assert tone_variant(idx, state(), "nature") == "nature"
    assert tone_variant(idx, state(romance="откровенно"), "romance") == "romance_sensual"
    assert tone_variant(idx, state(romance="откровенно"), "town") == "town"
