# ТО (docs/TO-PLAN.md §1 п.7, Q6а): пак dusk_academy после правки текста 18+ грузится без ошибок;
# world.md и tone.notes говорят про совершеннолетних; «юных представителей» больше нет.
from campaign_kit import ROOT

from ai_dm.campaign.loader import load_pack, pack_content_dir
from ai_dm.content.loader import load_registry

DUSK_DIR = ROOT / "campaigns" / "dusk_academy"


def test_dusk_academy_pack_loads():
    content = pack_content_dir(DUSK_DIR)
    registry = load_registry([content] if content is not None else [])
    assert load_pack(DUSK_DIR, registry) is not None


def test_world_md_says_students_are_adults():
    text = (DUSK_DIR / "world.md").read_text(encoding="utf-8")
    assert "18+" in text


def test_world_md_has_no_young_representatives():
    text = (DUSK_DIR / "world.md").read_text(encoding="utf-8")
    assert "юных представителей" not in text
    assert "молодых на вид представителей" in text


def test_world_md_says_young_people_instead_of_human_children():
    text = (DUSK_DIR / "world.md").read_text(encoding="utf-8")
    assert "дети людей" not in text
    assert "молодые люди" in text


def test_campaign_yaml_tone_notes_say_adults_18plus():
    text = (DUSK_DIR / "campaign.yaml").read_text(encoding="utf-8")
    assert "Все персонажи — совершеннолетние (18+)" in text


def test_dormitory_location_is_kept():
    text = (DUSK_DIR / "locations.yaml").read_text(encoding="utf-8")
    assert "Общежитие первокурсников" in text
