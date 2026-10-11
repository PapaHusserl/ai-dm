from pathlib import Path

import yaml

from ai_dm.campaign.loader import PackError, load_pack
from ai_dm.campaign.uniqueness import collect_conflicts
from ai_dm.core.rng import Rng
from ai_dm.state.world import WorldState

# файлы, которые может записать import пака (events.yaml, start/, heroes/ не пишутся)
PACK_FILES = (
    "campaign.yaml", "world.md", "truths.md", "locations.yaml", "npcs.yaml", "factions.yaml",
    "pantheon.yaml",
)
# файлы, которые пишутся всегда, даже пустыми
ALWAYS_FILES = ("campaign.yaml", "world.md")


def write_pack_files(folder, files) -> list[str]:
    # пишет файлы пака из files_from_request; пустые списковые файлы и truths.md не пишутся
    folder = Path(folder)
    written = []
    for name in PACK_FILES:
        content = files[name]
        if not content and name not in ALWAYS_FILES:
            continue
        if name.endswith(".yaml"):
            content = yaml.safe_dump(content, allow_unicode=True, sort_keys=False)
        (folder / name).write_text(content, encoding="utf-8")
        written.append(name)
    return written


def clear_pack_files(folder) -> None:
    for name in PACK_FILES:
        (Path(folder) / name).unlink(missing_ok=True)


def check_pack_dir(folder, registry) -> list[str]:
    # строки ошибок загрузчика пака и конфликтов 5.3; пусто -- пак грузится без ошибок
    try:
        pack = load_pack(folder, registry)
    except PackError as error:
        return error.lines
    world = WorldState(world_id="import", rng=Rng(0).state)
    _, conflicts = collect_conflicts(world, [], pack)
    return [conflict.line() for conflict in conflicts]


def relabel(lines, folder, campaign_id) -> list[str]:
    # временный путь staging в строках ошибок -> id кампании
    return [line.replace(str(folder), campaign_id) for line in lines]
