import shutil
import tempfile
from pathlib import Path

from ai_dm.campaign.importer import (
    ALWAYS_FILES,
    PACK_FILES,
    check_pack_dir,
    clear_pack_files,
    relabel,
    write_pack_files,
)
from ai_dm.master.importer import ImportPromptBuilder
from ai_dm.master.session import MasterSession
from ai_dm.protocol.apply import apply
from ai_dm.protocol.context import CreationContext
from ai_dm.protocol.decision import Invalid
from ai_dm.protocol.requests import IMPORT_MODE


def stage_dir(campaigns_dir, campaign_id) -> Path:
    # временный каталог рядом с паками: та же файловая система, rename атомарный
    return Path(tempfile.mkdtemp(prefix=f".import-{campaign_id}-", dir=campaigns_dir))


def finish_import(folder, campaigns_dir, campaign_id) -> None:
    Path(folder).rename(Path(campaigns_dir) / campaign_id)


def discard_import(folder) -> None:
    shutil.rmtree(folder, ignore_errors=True)


class ImportExecutor:
    # исполнитель import: apply, затем запись файлов в staging и проверка настоящим загрузчиком
    def __init__(self, folder, registry, campaign_id):
        self.folder = folder
        self.registry = registry
        self.campaign_id = campaign_id

    def __call__(self, ctx, request):
        outcome = apply(ctx, request)
        if isinstance(outcome, Invalid):
            return outcome
        write_pack_files(self.folder, ctx.files)
        errors = check_pack_dir(self.folder, self.registry)
        if errors:
            clear_pack_files(self.folder)
            ctx.files = None
            lines = relabel(errors, self.folder, self.campaign_id)
            return Invalid(code="pack_invalid", message="\n".join(lines))
        return outcome


def run_import(deps, task, text, run_id, folder) -> CreationContext:
    # прогон import пака; сбои -- TurnFailed наверх (меню 2.2 у вызывающего)
    ctx = CreationContext(deps.registry, deps.cfg, task)
    session = MasterSession(
        deps.adapter, deps.app_cfg, journal=deps.journal, ledger=None, run_id=run_id,
        now=deps.now, role="import", builder=ImportPromptBuilder(deps.app_cfg, model=deps.model),
    )
    executor = ImportExecutor(folder, deps.registry, task.campaign_id)
    session.run(ctx, text, executor, IMPORT_MODE, run_id=run_id)
    return ctx


def check_summary(text, max_chars) -> str | None:
    # текст отказа или None, если выжимку можно отдавать модели
    if not text.strip():
        return "Выжимка пуста."
    if len(text) > max_chars:
        return f"Выжимка длиннее {max_chars} символов ({len(text)})."
    return None


def pack_report_lines(files) -> list[str]:
    # итог import: что записано и что делать дальше (по тем же правилам, что write_pack_files)
    campaign_id = files["campaign.yaml"]["id"]
    names = ", ".join(
        name for name in PACK_FILES if files[name] or name in ALWAYS_FILES
    )
    counts = (
        f"локаций {len(files['locations.yaml'])}, NPC {len(files['npcs.yaml'])}, "
        f"фракций {len(files['factions.yaml'])}, богов {len(files['pantheon.yaml'])}"
    )
    return [
        f"Пак {campaign_id} записан: campaigns/{campaign_id}/ — {names}; {counts}.",
        f"Дальше: правьте файлы руками и запускайте ai-dm --new --campaign {campaign_id}",
    ]
