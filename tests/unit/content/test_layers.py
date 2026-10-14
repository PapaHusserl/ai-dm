# Партия К7х, п. 8 (BACKLOG 51, docs/K7X-PLAN.md): слой content не зависит от rules.
#   DAMAGE_TYPE_WORDS живёт в content/models/common.py; rules.roll_pipeline импортирует его оттуда
#     под тем
#   же именем (один и тот же объект); content/loader.py берёт его из content.models.common.
#   Страж: ни один файл src/ai_dm/content/ не импортирует ai_dm.rules (ни `import`, ни `from`).
import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[3] / "src" / "ai_dm"
CONTENT = SRC / "content"


def imported_modules(path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            module = node.module or ""
            names.append(module)
            names += [f"{module}.{a.name}" for a in node.names]
    return names


def test_content_package_has_files():
    assert len(list(CONTENT.rglob("*.py"))) > 5


def test_content_does_not_import_rules():
    bad = []
    for path in sorted(CONTENT.rglob("*.py")):
        for name in imported_modules(path):
            if name == "ai_dm.rules" or name.startswith("ai_dm.rules."):
                bad.append(f"{path.relative_to(SRC)}: {name}")
    assert bad == []


def test_content_does_not_import_rules_by_a_grep():
    bad = [
        str(path.relative_to(SRC))
        for path in sorted(CONTENT.rglob("*.py"))
        if "from ai_dm.rules" in path.read_text(encoding="utf-8")
        or "import ai_dm.rules" in path.read_text(encoding="utf-8")
    ]
    assert bad == []


def test_damage_type_words_live_in_content_models_common():
    from ai_dm.content.models import common

    assert common.DAMAGE_TYPE_WORDS["bludgeoning"] == "дробящий"


def test_roll_pipeline_shares_the_same_object():
    from ai_dm.content.models import common
    from ai_dm.rules import roll_pipeline

    assert roll_pipeline.DAMAGE_TYPE_WORDS is common.DAMAGE_TYPE_WORDS


def test_attack_module_still_imports_it_from_roll_pipeline():
    import ai_dm.combat.engine  # noqa: F401  (attack в одиночку не импортируется и до К7х)
    from ai_dm.combat.actions import attack
    from ai_dm.content.models import common

    assert attack.DAMAGE_TYPE_WORDS is common.DAMAGE_TYPE_WORDS


def test_loader_uses_the_common_constant():
    from ai_dm.content import loader
    from ai_dm.content.models import common

    assert loader.DAMAGE_TYPE_WORDS is common.DAMAGE_TYPE_WORDS


def test_common_module_defines_the_constant_itself():
    tree = ast.parse((CONTENT / "models" / "common.py").read_text(encoding="utf-8"))
    targets = [
        t.id for node in tree.body if isinstance(node, ast.Assign)
        for t in node.targets if isinstance(t, ast.Name)
    ]
    assert "DAMAGE_TYPE_WORDS" in targets
