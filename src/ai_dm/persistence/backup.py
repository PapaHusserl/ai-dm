import shutil
from datetime import UTC, datetime
from pathlib import Path

from ai_dm.persistence.layout import check_world_id, slot_dir


def make_backup(root: Path, world_id: str, slot: str, old_version: int, ts=None) -> Path:
    # копия всего слота байт в байт: backups/<slot>-v<old>-<ts>; занято -- суффикс -2, -3...
    if ts is None:
        ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    check_world_id(world_id)
    name = f"{slot}-v{old_version}-{ts}"
    target = Path(root) / world_id / "backups" / name
    number = 2
    while target.exists():
        target = Path(root) / world_id / "backups" / f"{name}-{number}"
        number += 1
    shutil.copytree(slot_dir(root, world_id, slot), target)
    return target
