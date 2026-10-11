import re
from pathlib import Path

AUTO_RE = re.compile(r"auto(-[0-9]+)?")
WORLD_ID_RE = re.compile(r"[\w-]+")


def slugify(name: str) -> str:
    slug = re.sub(r"[\W_]+", "-", name.lower()).strip("-")
    return slug or "hero"


def hero_dir_name(hero) -> str:
    return f"{hero.ordinal:02d}_{slugify(hero.name)}"


def check_world_id(world_id: str) -> None:
    # только буквы, цифры, "_" и "-"; не с точки; никаких разделителей пути
    if WORLD_ID_RE.fullmatch(world_id) and not world_id.startswith("."):
        return
    raise ValueError(f"плохой world_id: {world_id!r}")


def slots_dir(root: Path, world_id: str) -> Path:
    check_world_id(world_id)
    return Path(root) / world_id / "slots"


def slot_dir(root: Path, world_id: str, slot: str) -> Path:
    check_slot_name(slot)
    return slots_dir(root, world_id) / slot


def visible_dirs(path: Path) -> list[Path]:
    # служебные каталоги (.DS_Store, .tmp-*, .old-*) не считаются
    return [p for p in path.iterdir() if p.is_dir() and not p.name.startswith(".")]


def check_slot_name(slot: str) -> None:
    # "auto", "auto-<число>" или "manual-<имя>"
    if AUTO_RE.fullmatch(slot):
        return
    if slot.startswith("manual-"):
        name = slot[len("manual-"):]
        bad = "/" in name or "\\" in name or ".." in name or name.startswith(".")
        bad = bad or name != name.lower()
        if name and not bad:
            return
    raise ValueError(f"плохое имя слота: {slot!r}")
