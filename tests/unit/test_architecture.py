# Сторож архитектуры (ARCHITECTURE.md A1): движок не знает про protocol/llm/master/ui,
# не использует random и time.time(). Ожидаемый API: нет, только исходники src/ai_dm/<пакет>.
import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src" / "ai_dm"
ENGINE_PACKAGES = ["core", "config", "content", "srd", "state", "rules", "combat"]
FORBIDDEN_LAYERS = [
    "protocol", "llm", "master", "ui", "game", "world_sim", "campaign", "reports", "persistence",
]


def engine_files():
    files = []
    for package in ENGINE_PACKAGES:
        folder = SRC / package
        if folder.is_dir():
            files.extend(sorted(folder.rglob("*.py")))
    return files


def parse(path):
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def test_engine_does_not_import_upper_layers():
    bad = []
    for path in engine_files():
        for node in ast.walk(parse(path)):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if node.level == 0:
                    names = [module]
                    if module == "ai_dm":
                        names += ["ai_dm." + a.name for a in node.names]
                else:
                    names = ["ai_dm." + module]
                    names += ["ai_dm." + a.name for a in node.names if not module]
            for name in names:
                for layer in FORBIDDEN_LAYERS:
                    if name == "ai_dm." + layer or name.startswith("ai_dm." + layer + "."):
                        bad.append(f"{path}: {name}")
    assert bad == []


def test_engine_does_not_import_random():
    bad = []
    for path in engine_files():
        for node in ast.walk(parse(path)):
            if isinstance(node, ast.Import):
                for a in node.names:
                    if a.name == "random" or a.name.startswith("random."):
                        bad.append(f"{path}: import {a.name}")
            elif (
                isinstance(node, ast.ImportFrom)
                and node.level == 0
                and (node.module == "random" or (node.module or "").startswith("random."))
            ):
                bad.append(f"{path}: from {node.module}")
    assert bad == []


def test_engine_does_not_call_time_time():
    bad = []
    for path in engine_files():
        tree = parse(path)
        time_aliases = {"time"}
        func_aliases = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    if a.name == "time":
                        time_aliases.add(a.asname or "time")
            elif isinstance(node, ast.ImportFrom) and node.module == "time" and node.level == 0:
                for a in node.names:
                    if a.name == "time":
                        func_aliases.add(a.asname or "time")
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            f = node.func
            if isinstance(f, ast.Attribute) and f.attr == "time" \
                    and isinstance(f.value, ast.Name) and f.value.id in time_aliases:
                bad.append(f"{path}:{node.lineno}: time.time()")
            if isinstance(f, ast.Name) and f.id in func_aliases:
                bad.append(f"{path}:{node.lineno}: time()")
    assert bad == []


def test_engine_does_not_call_builtin_hash():
    bad = []
    for path in engine_files():
        for node in ast.walk(parse(path)):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Name) and node.func.id == "hash":
                bad.append(f"{path}:{node.lineno}: hash()")
    assert bad == []


def test_core_imports_only_core():
    bad = []
    for path in sorted((SRC / "core").rglob("*.py")):
        # пакет модуля относительно ai_dm, например ["core"] или ["core", "sub"]
        package = list(path.relative_to(SRC).parts[:-1])
        for node in ast.walk(parse(path)):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level == 0:
                    module = node.module or ""
                    names = [module]
                    if module == "ai_dm":
                        names += ["ai_dm." + a.name for a in node.names]
                else:
                    base = package[: len(package) - (node.level - 1)]
                    parts = ["ai_dm"] + base + ([node.module] if node.module else [])
                    full = ".".join(parts)
                    names = [full]
                    if not node.module:
                        names += [full + "." + a.name for a in node.names]
            for name in names:
                if name == "ai_dm" and isinstance(node, ast.ImportFrom):
                    continue
                inside_ai_dm = name == "ai_dm" or name.startswith("ai_dm.")
                inside_core = name == "ai_dm.core" or name.startswith("ai_dm.core.")
                if inside_ai_dm and not inside_core:
                    bad.append(f"{path}: {name}")
    assert bad == []


# дубли и отложенные импорты партии 3 (D2, D7, B6)

def top_level_names(path):
    # имена, определяемые на верхнем уровне модуля: def / class / присваивание
    names = []
    for node in parse(path).body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            names.append(node.name)
        elif isinstance(node, ast.Assign):
            names += [t.id for t in node.targets if isinstance(t, ast.Name)]
    return names


def test_d20_kinds_is_declared_once():
    owners = [p.name for p in engine_files() if "D20_KINDS" in top_level_names(p)]
    assert owners == ["creatures.py"]


def test_remove_zero_hp_unconscious_is_defined_once():
    owners = [p.name for p in engine_files() if "remove_zero_hp_unconscious" in top_level_names(p)]
    assert len(owners) == 1


def test_mark_dead_is_defined_once_in_mortality_guard():
    owners = [p.name for p in engine_files() if "mark_dead" in top_level_names(p)]
    assert owners == ["mortality_guard.py"]


def test_roll_pipeline_has_no_deferred_imports():
    path = SRC / "rules" / "roll_pipeline.py"
    bad = []
    for node in ast.walk(parse(path)):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for inner in ast.walk(node):
                if isinstance(inner, (ast.Import, ast.ImportFrom)):
                    bad.append(f"{path}:{inner.lineno}")
    assert bad == []


# ревью партии 1, п.7: движок не знает про SDK провайдеров

FORBIDDEN_SDKS = ["anthropic", "google"]


def test_engine_does_not_import_llm_sdks():
    bad = []
    for path in engine_files():
        for node in ast.walk(parse(path)):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                names = [node.module or ""]
            for name in names:
                for sdk in FORBIDDEN_SDKS:
                    if name == sdk or name.startswith(sdk + "."):
                        bad.append(f"{path}: {name}")
    assert bad == []


def test_engine_packages_include_config():
    assert "config" in ENGINE_PACKAGES
    assert any(p.parent.name == "config" for p in engine_files())


# партия 2 этапа 2: protocol -- граница движок <-> мастер (STAGE2-PLAN A1)
# protocol не импортирует llm, master, game, ui (и SDK провайдеров)

PROTOCOL_FORBIDDEN = ["llm", "master", "game", "ui"]


def test_protocol_does_not_import_upper_layers():
    folder = SRC / "protocol"
    assert folder.is_dir()
    bad = []
    for path in sorted(folder.rglob("*.py")):
        for node in ast.walk(parse(path)):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if node.level == 0:
                    names = [module]
                    if module == "ai_dm":
                        names += ["ai_dm." + a.name for a in node.names]
                else:
                    names = ["ai_dm." + module]
                    names += ["ai_dm." + a.name for a in node.names if not module]
            for name in names:
                for layer in PROTOCOL_FORBIDDEN:
                    if name == "ai_dm." + layer or name.startswith("ai_dm." + layer + "."):
                        bad.append(f"{path}: {name}")
                for sdk in FORBIDDEN_SDKS:
                    if name == sdk or name.startswith(sdk + "."):
                        bad.append(f"{path}: {name}")
    assert bad == []


def test_protocol_does_not_use_random_or_wall_clock():
    folder = SRC / "protocol"
    assert folder.is_dir()
    bad = []
    for path in sorted(folder.rglob("*.py")):
        for node in ast.walk(parse(path)):
            if isinstance(node, ast.Import):
                bad += [f"{path}: import {a.name}" for a in node.names
                        if a.name in ("random", "time", "datetime")]
            elif (
                isinstance(node, ast.ImportFrom)
                and node.level == 0
                and (node.module or "") in ("random", "time", "datetime")
            ):
                bad.append(f"{path}: from {node.module}")
    assert bad == []


# партия 3 этапа 2: llm -- нижний слой (STAGE2-PLAN A1: «llm: только pydantic/SDK»)
# llm не импортирует protocol, master, game, ui, persistence и пакеты движка (config -- можно:
# фабрике и учёту нужны AppConfig / ModelPrice); SDK провайдеров -- только внутри функций
# (отложенный импорт), в окне модуля их нет.

LLM_FORBIDDEN = [
    "protocol", "master", "game", "ui", "persistence", "world_sim", "campaign", "reports",
    "core", "content", "srd", "state", "rules", "combat",
]


def llm_files():
    folder = SRC / "llm"
    assert folder.is_dir()
    return sorted(folder.rglob("*.py"))


def test_llm_does_not_import_upper_layers_or_engine():
    bad = []
    for path in llm_files():
        for node in ast.walk(parse(path)):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if node.level == 0:
                    names = [module]
                    if module == "ai_dm":
                        names += ["ai_dm." + a.name for a in node.names]
                else:
                    names = ["ai_dm." + module]
                    names += ["ai_dm." + a.name for a in node.names if not module]
            for name in names:
                for layer in LLM_FORBIDDEN:
                    if name == "ai_dm." + layer or name.startswith("ai_dm." + layer + "."):
                        bad.append(f"{path}: {name}")
    assert bad == []


def test_llm_imports_sdks_only_lazily_inside_adapters():
    bad = []
    for path in llm_files():
        for node in parse(path).body:
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                names = [node.module or ""]
            for name in names:
                for sdk in FORBIDDEN_SDKS:
                    if name == sdk or name.startswith(sdk + "."):
                        bad.append(f"{path}: {name}")
    assert bad == []


def test_llm_sdk_imports_live_only_in_adapter_modules():
    bad = []
    for path in llm_files():
        if path.name in ("anthropic_adapter.py", "gemini_adapter.py"):
            continue
        for node in ast.walk(parse(path)):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                names = [node.module or ""]
            for name in names:
                for sdk in FORBIDDEN_SDKS:
                    if name == sdk or name.startswith(sdk + "."):
                        bad.append(f"{path}: {name}")
    assert bad == []


def test_llm_does_not_use_random_or_builtin_hash():
    bad = []
    for path in llm_files():
        for node in ast.walk(parse(path)):
            if isinstance(node, ast.Import):
                bad += [f"{path}: import {a.name}" for a in node.names if a.name == "random"]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module == "random":
                bad.append(f"{path}: from random")
            elif (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "hash"
            ):
                bad.append(f"{path}:{node.lineno}: hash()")
    assert bad == []


# партия 4 этапа 2: master -- над protocol и llm, под game и ui (STAGE2-PLAN A1: «master — game/ui»)

MASTER_FORBIDDEN = ["game", "ui"]


def test_master_does_not_import_game_or_ui():
    folder = SRC / "master"
    assert folder.is_dir()
    assert list(folder.rglob("*.py"))
    bad = []
    for path in sorted(folder.rglob("*.py")):
        for node in ast.walk(parse(path)):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if node.level == 0:
                    names = [module]
                    if module == "ai_dm":
                        names += ["ai_dm." + a.name for a in node.names]
                else:
                    names = ["ai_dm." + module]
                    names += ["ai_dm." + a.name for a in node.names if not module]
            for name in names:
                for layer in MASTER_FORBIDDEN:
                    if name == "ai_dm." + layer or name.startswith("ai_dm." + layer + "."):
                        bad.append(f"{path}: {name}")
    assert bad == []


# партия 5 этапа 2: game -- над master/protocol/persistence/combat, под ui
# (STAGE2-PLAN A1: ui -> game -> master -> llm); game не импортирует ui и SDK провайдеров

GAME_FORBIDDEN = ["ui"]


def test_game_does_not_import_ui_or_sdks():
    folder = SRC / "game"
    assert folder.is_dir()
    assert list(folder.rglob("*.py"))
    bad = []
    for path in sorted(folder.rglob("*.py")):
        for node in ast.walk(parse(path)):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if node.level == 0:
                    names = [module]
                    if module == "ai_dm":
                        names += ["ai_dm." + a.name for a in node.names]
                else:
                    names = ["ai_dm." + module]
                    names += ["ai_dm." + a.name for a in node.names if not module]
            for name in names:
                for layer in GAME_FORBIDDEN:
                    if name == "ai_dm." + layer or name.startswith("ai_dm." + layer + "."):
                        bad.append(f"{path}: {name}")
                for sdk in FORBIDDEN_SDKS:
                    if name == sdk or name.startswith(sdk + "."):
                        bad.append(f"{path}: {name}")
    assert bad == []


def absolute_imports(path):
    # все импортируемые модули файла в абсолютном виде (относительные -- от пакета файла)
    package = ["ai_dm", *path.relative_to(SRC).parts[:-1]]
    names = []
    for node in ast.walk(parse(path)):
        if isinstance(node, ast.Import):
            names += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0:
                base = node.module or ""
            else:
                parts = package[: len(package) - (node.level - 1)]
                if node.module:
                    parts = parts + node.module.split(".")
                base = ".".join(parts)
            names.append(base)
            names += [base + "." + a.name for a in node.names]
    return names


def test_absolute_imports_resolve_relative_imports(tmp_path, monkeypatch):
    import sys

    module = sys.modules[__name__]
    monkeypatch.setattr(module, "SRC", tmp_path)
    folder = tmp_path / "persistence"
    folder.mkdir()
    path = folder / "x.py"
    path.write_text(
        "from ..game import app\nfrom ..game.turn import TurnRunner\n"
        "from . import store\nfrom .store import save\nimport ai_dm.game\n",
        encoding="utf-8",
    )
    names = absolute_imports(path)
    assert "ai_dm.game" in names
    assert "ai_dm.game.app" in names
    assert "ai_dm.game.turn" in names
    assert "ai_dm.persistence.store" in names


def test_lower_layers_do_not_import_game():
    # persistence, master, protocol, llm и движок не знают про game (devtools -- не слой игры:
    # sim_combat берёт выборы героев из game.starter, это разрешено); относительные импорты
    # (from ..game import x) считаются так же, как абсолютные
    bad = []
    for package in ("persistence", "master", "protocol", "llm", *ENGINE_PACKAGES):
        folder = SRC / package
        if not folder.is_dir():
            continue
        for path in sorted(folder.rglob("*.py")):
            for name in absolute_imports(path):
                if name == "ai_dm.game" or name.startswith("ai_dm.game."):
                    bad.append(f"{path}: {name}")
    assert bad == []


# партия 6 этапа 2: ui -- верхний слой (STAGE2-PLAN A1: ui -> game -> master -> llm); ничто, кроме
# самого ui, его не импортирует (относительные импорты считаются так же, как абсолютные)

def test_nothing_but_ui_imports_ui():
    bad = []
    for path in sorted(SRC.rglob("*.py")):
        if path.relative_to(SRC).parts[0] == "ui":
            continue
        for name in absolute_imports(path):
            if name == "ai_dm.ui" or name.startswith("ai_dm.ui."):
                bad.append(f"{path}: {name}")
    assert bad == []


def test_ui_package_exists_with_the_three_modules():
    for name in ("io.py", "simple.py", "cli.py"):
        assert (SRC / "ui" / name).is_file()


# этап 3, партия 1: campaign (A1) не знает llm, master, protocol, game, ui

CAMPAIGN_FORBIDDEN = ["llm", "master", "protocol", "game", "ui"]


def test_campaign_does_not_import_upper_layers():
    folder = SRC / "campaign"
    assert list(folder.rglob("*.py"))
    bad = []
    for path in sorted(folder.rglob("*.py")):
        for name in absolute_imports(path):
            for layer in CAMPAIGN_FORBIDDEN:
                if name == "ai_dm." + layer or name.startswith("ai_dm." + layer + "."):
                    bad.append(f"{path}: {name}")
    assert bad == []


def test_campaign_does_not_use_random_or_wall_clock():
    bad = []
    for path in sorted((SRC / "campaign").rglob("*.py")):
        for name in absolute_imports(path):
            if name in ("random", "time", "datetime"):
                bad.append(f"{path}: {name}")
    assert bad == []


# этап 3, партия 3: world_sim (A1) -- структурный ход мира: без llm, master, protocol, game, ui;
# детерминирован (без random, часов и builtin hash), как движок

WORLD_SIM_FORBIDDEN = ["llm", "master", "protocol", "game", "ui"]


def test_world_sim_package_exists():
    assert list((SRC / "world_sim").rglob("*.py"))


def test_world_sim_does_not_import_upper_layers():
    bad = []
    for path in sorted((SRC / "world_sim").rglob("*.py")):
        for name in absolute_imports(path):
            for layer in WORLD_SIM_FORBIDDEN:
                if name == "ai_dm." + layer or name.startswith("ai_dm." + layer + "."):
                    bad.append(f"{path}: {name}")
    assert bad == []


def test_world_sim_does_not_use_random_or_wall_clock():
    bad = []
    for path in sorted((SRC / "world_sim").rglob("*.py")):
        for name in absolute_imports(path):
            if name in ("random", "time", "datetime"):
                bad.append(f"{path}: {name}")
    assert bad == []


def test_world_sim_does_not_call_builtin_hash():
    bad = []
    for path in sorted((SRC / "world_sim").rglob("*.py")):
        for node in ast.walk(parse(path)):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "hash"
            ):
                bad.append(f"{path}:{node.lineno}: hash()")
    assert bad == []


def test_only_game_imports_world_sim():
    # world_sim зовёт game (boundary); ему же разрешены devtools и тесты; остальные слои не знают
    bad = []
    for path in sorted(SRC.rglob("*.py")):
        top = path.relative_to(SRC).parts[0]
        if top in ("world_sim", "game", "devtools"):
            continue
        for name in absolute_imports(path):
            if name == "ai_dm.world_sim" or name.startswith("ai_dm.world_sim."):
                bad.append(f"{path}: {name}")
    assert bad == []


# этап 4, P1: master/summarizer.py -- роль summarizer в слое master (как master/world.py)

def test_summarizer_module_exists_and_does_not_import_upper_layers():
    path = SRC / "master" / "summarizer.py"
    assert path.is_file()
    bad = []
    for name in absolute_imports(path):
        for layer in ("game", "ui", "world_sim", "persistence"):
            if name == "ai_dm." + layer or name.startswith("ai_dm." + layer + "."):
                bad.append(name)
    assert bad == []


# P3: master.context -- чистый расчёт без адаптеров, игры и интерфейса

def imported_names(path):
    names = []
    for node in ast.walk(parse(path)):
        if isinstance(node, ast.Import):
            names += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            module = node.module or ""
            names.append(module)
            names += [module + "." + a.name for a in node.names]
    return names


def test_master_context_does_not_import_adapters_game_or_ui():
    bad = []
    for name in imported_names(SRC / "master" / "context.py"):
        if name.startswith(("ai_dm.game", "ai_dm.ui", "ai_dm.persistence")):
            bad.append(name)
        if name.startswith("ai_dm.llm.") and name != "ai_dm.llm.types" and not name.startswith(
            "ai_dm.llm.types."
        ):
            bad.append(name)
        if "adapter" in name:
            bad.append(name)
    assert bad == []


def test_master_context_imports_only_allowed_ai_dm_modules():
    bad = []
    for name in imported_names(SRC / "master" / "context.py"):
        if not name.startswith("ai_dm"):
            continue
        allowed = ("ai_dm.llm.types", "ai_dm.state", "ai_dm.master.relevance")
        if not name.startswith(allowed):
            bad.append(name)
    assert bad == []


def test_master_memory_module_is_gone():
    assert not (SRC / "master" / "memory.py").exists()
    import importlib.util

    assert importlib.util.find_spec("ai_dm.master.memory") is None


def test_master_relevance_does_not_import_game_or_llm():
    bad = [
        n for n in imported_names(SRC / "master" / "relevance.py")
        if n.startswith(("ai_dm.game", "ai_dm.ui", "ai_dm.llm"))
    ]
    assert bad == []


# этап 5, P1: textual импортирует только ai_dm.ui.tui*, остальным слоям он неизвестен

def test_textual_is_imported_only_from_ui_tui():
    bad = []
    for path in sorted(SRC.rglob("*.py")):
        relative = path.relative_to(SRC)
        if relative.parts[:2] == ("ui", "tui") or relative.parts == ("ui", "tui.py"):
            continue
        for node in ast.walk(parse(path)):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                names = [node.module or ""]
            for name in names:
                if name == "textual" or name.startswith("textual."):
                    bad.append(f"{path}: {name}")
    assert bad == []


def test_cli_imports_tui_only_lazily():
    # верхний уровень cli не должен тянуть ai_dm.ui.tui (и textual)
    tree = parse(SRC / "ui" / "cli.py")
    bad = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            bad += [a.name for a in node.names if a.name.startswith("ai_dm.ui.tui")]
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            module = node.module or ""
            if module.startswith("ai_dm.ui.tui") or (
                module == "ai_dm.ui" and any(a.name == "tui" for a in node.names)
            ):
                bad.append(module)
    assert bad == []


# этап 6а, P0: reports (A1) -- репорты хода: не знает game, ui, master (его вызывают game и ui.cli)

REPORTS_FORBIDDEN = ["game", "ui", "master"]


def test_reports_package_exists():
    assert list((SRC / "reports").rglob("*.py"))


def test_reports_does_not_import_game_ui_master():
    bad = []
    for path in sorted((SRC / "reports").rglob("*.py")):
        for name in absolute_imports(path):
            for layer in REPORTS_FORBIDDEN:
                if name == "ai_dm." + layer or name.startswith("ai_dm." + layer + "."):
                    bad.append(f"{path}: {name}")
    assert bad == []


# Б1а: создание героя на лету -- модули нового кода не тянут верхние слои

def forbidden_imports(path, layers):
    bad = []
    for name in absolute_imports(path):
        for layer in layers:
            if name == "ai_dm." + layer or name.startswith("ai_dm." + layer + "."):
                bad.append(f"{path}: {name}")
    return bad


def test_master_hero_does_not_import_game_ui_or_campaign():
    assert forbidden_imports(SRC / "master" / "hero.py", ["game", "ui", "campaign"]) == []


def test_protocol_hero_handler_does_not_import_upper_layers_or_campaign():
    path = SRC / "protocol" / "handlers" / "hero.py"
    assert forbidden_imports(path, ["llm", "master", "game", "ui", "campaign"]) == []


def test_rules_builder_does_not_import_protocol_master_game_ui_or_campaign():
    layers = ["protocol", "llm", "master", "game", "ui", "campaign"]
    assert forbidden_imports(SRC / "rules" / "builder.py", layers) == []


def test_campaign_build_does_not_import_protocol_or_master():
    assert forbidden_imports(SRC / "campaign" / "build.py", ["protocol", "master"]) == []


# Б3 (B3-PLAN, A1-A4): import пака -- новые модули не нарушают слои

def test_master_importer_does_not_import_game_ui_or_campaign():
    assert forbidden_imports(SRC / "master" / "importer.py", ["game", "ui", "campaign"]) == []


def test_protocol_pack_handler_does_not_import_upper_layers_or_campaign():
    path = SRC / "protocol" / "handlers" / "pack.py"
    assert forbidden_imports(path, ["llm", "master", "game", "ui", "campaign"]) == []


def test_campaign_importer_exists_and_does_not_make_temp_dirs_or_use_wall_clock():
    path = SRC / "campaign" / "importer.py"
    assert path.is_file()
    names = absolute_imports(path)
    for banned in ("tempfile", "shutil", "random", "time", "datetime"):
        assert banned not in names, banned
    assert forbidden_imports(path, CAMPAIGN_FORBIDDEN) == []


def test_game_pack_import_does_not_import_ui():
    assert forbidden_imports(SRC / "game" / "pack_import.py", GAME_FORBIDDEN) == []


def test_protocol_pack_handler_does_not_touch_disk():
    names = absolute_imports(SRC / "protocol" / "handlers" / "pack.py")
    for banned in ("os", "shutil", "tempfile", "yaml", "pathlib"):
        assert banned not in names, banned


# Му-а (MU-PLAN A1): audio ниже game, ui; miniaudio только в audio/miniaudio_player.py, лениво

AUDIO_FORBIDDEN = ["game", "ui", "llm", "master", "protocol"]
MINIAUDIO_MODULE = SRC / "audio" / "miniaudio_player.py"


def test_audio_package_exists():
    assert (SRC / "audio" / "__init__.py").is_file()


def test_audio_does_not_import_upper_layers():
    bad = []
    for path in sorted((SRC / "audio").rglob("*.py")):
        bad += forbidden_imports(path, AUDIO_FORBIDDEN)
    assert bad == []


def is_miniaudio(name):
    return name == "miniaudio" or name.startswith("miniaudio.")


def test_miniaudio_is_imported_only_from_its_player_module():
    bad = []
    for path in sorted(SRC.rglob("*.py")):
        if path == MINIAUDIO_MODULE:
            continue
        bad += [f"{path}: {n}" for n in absolute_imports(path) if is_miniaudio(n)]
    assert bad == []


def module_level_imports(statements):
    # импорты вне функций: верхний уровень, а также внутри if/try/with верхнего уровня
    names = []
    for node in statements:
        if isinstance(node, ast.Import):
            names += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            names.append(node.module or "")
        elif isinstance(node, (ast.If, ast.Try, ast.With, ast.For, ast.While)):
            for field in ("body", "orelse", "finalbody"):
                names += module_level_imports(getattr(node, field, []))
            for handler in getattr(node, "handlers", []):
                names += module_level_imports(handler.body)
    return names


def test_miniaudio_is_imported_lazily_inside_functions():
    if not MINIAUDIO_MODULE.is_file():
        return  # плеер появляется в Му-б
    tree = parse(MINIAUDIO_MODULE)
    assert [n for n in module_level_imports(tree.body) if is_miniaudio(n)] == []


def test_audio_package_is_imported_without_miniaudio():
    import subprocess
    import sys

    code = "import ai_dm.audio, sys; assert 'miniaudio' not in sys.modules"
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_audio_does_not_use_wall_clock_or_random_by_itself():
    # время приходит параметром now (по умолчанию time.monotonic); time.time() и random не нужны
    bad = []
    for path in sorted((SRC / "audio").rglob("*.py")):
        for node in ast.walk(parse(path)):
            if isinstance(node, ast.Import):
                bad += [f"{path}: {a.name}" for a in node.names if a.name == "random"]
            elif isinstance(node, ast.ImportFrom) and node.module == "random":
                bad.append(f"{path}: random")
            elif (isinstance(node, ast.Attribute) and node.attr == "time"
                  and isinstance(node.value, ast.Name) and node.value.id == "time"):
                bad.append(f"{path}:{node.lineno}: time.time")
    assert bad == []


# Му-б (MU-PLAN B2): miniaudio -- только необязательная зависимость (extra audio)

def test_miniaudio_is_optional_dependency_only():
    import tomllib

    root = SRC.parents[1]
    data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    extra = data["project"]["optional-dependencies"]["audio"]
    assert any(item.replace(" ", "").startswith("miniaudio") for item in extra)
    required = data["project"]["dependencies"]
    assert not any(item.startswith("miniaudio") for item in required)


def test_lock_file_knows_miniaudio():
    root = SRC.parents[1]
    assert 'name = "miniaudio"' in (root / "uv.lock").read_text(encoding="utf-8")


# К0а: state не знает правил, level_up не знает game/ui, миграция v9 заморожена

def imported_modules(path):
    names = []
    for node in ast.walk(parse(path)):
        if isinstance(node, ast.Import):
            names += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            names.append(node.module or "")
    return names


def test_state_hero_does_not_import_rules():
    names = imported_modules(SRC / "state" / "hero.py")
    assert not [n for n in names if n.startswith("ai_dm.rules")]


def test_state_creature_does_not_import_rules_or_other_state_modules():
    names = imported_modules(SRC / "state" / "creature.py")
    assert not [n for n in names if n.startswith(("ai_dm.rules", "ai_dm.state.hero"))]


def test_level_up_does_not_import_game_or_ui():
    names = imported_modules(SRC / "rules" / "level_up.py")
    assert not [n for n in names if n.startswith(("ai_dm.game", "ai_dm.ui"))]


def test_migration_v9_does_not_import_state_or_content():
    names = imported_modules(SRC / "persistence" / "migrations" / "m0009_v8_to_v9.py")
    assert not [n for n in names if n.startswith(("ai_dm.state", "ai_dm.content"))]
