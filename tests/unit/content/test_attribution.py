# Партия К7д, п. 8: атрибуция данных монстров (docs/K7D-PLAN.md, В10, критерий 2).
#   srd/data/ATTRIBUTION.md называет SRD 5.2 и лицензию CC BY 4.0 и пишет про монстров;
#   README ссылается на этот файл; скрипта импорта в дереве репозитория нет (одноразовый, вне него).
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ATTRIBUTION = ROOT / "src" / "ai_dm" / "srd" / "data" / "ATTRIBUTION.md"


def test_attribution_names_the_source_and_the_license():
    text = ATTRIBUTION.read_text(encoding="utf-8")
    assert "SRD 5.2" in text and "Creative Commons Attribution 4.0" in text


def test_attribution_has_a_monsters_section():
    assert "Монстры" in ATTRIBUTION.read_text(encoding="utf-8")


def test_readme_links_the_attribution():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "src/ai_dm/srd/data/ATTRIBUTION.md" in readme


def test_no_import_script_in_the_source_tree():
    names = [p.name.lower() for p in (ROOT / "src").rglob("*.py")]
    assert not [n for n in names if "open5e" in n or n == "convert.py"]
