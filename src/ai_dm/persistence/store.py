import json
import os
import shutil
import uuid
from pathlib import Path

from pydantic import ValidationError

from ai_dm.persistence import durable
from ai_dm.persistence.backup import make_backup
from ai_dm.persistence.layout import (
    check_slot_name,
    hero_dir_name,
    slot_dir,
    slots_dir,
    visible_dirs,
)
from ai_dm.persistence.migrations import CURRENT_SCHEMA_VERSION, MIGRATIONS, SaveTooNew, migrate
from ai_dm.state.save import SaveBundle


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not durable.DURABLE:
        path.write_text(text, encoding="utf-8")
        return
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
        f.flush()
        durable.sync_file(f.fileno())


def sync_dirs(paths) -> None:
    if durable.DURABLE:
        for path in paths:
            durable.sync_dir(path)


def write_slot(root, world_id: str, bundle, slot: str, *, saved_at: str, version=None) -> Path:
    # файлы -> slots/.tmp-<uuid>/, manifest последним, потом подмена каталога
    check_slot_name(slot)
    if version is None:
        version = CURRENT_SCHEMA_VERSION
    hero_ids = [h.id for h in bundle.heroes]
    dir_names = [hero_dir_name(h) for h in bundle.heroes]
    if len(set(hero_ids)) != len(hero_ids):
        raise ValueError(f"повтор hero.id в сейве: {hero_ids}")
    if len(set(dir_names)) != len(dir_names):
        raise ValueError(f"повтор каталога героя в сейве: {dir_names}")
    final = slot_dir(root, world_id, slot)
    slots = final.parent
    suffix = uuid.uuid4().hex
    tmp = slots / f".tmp-{suffix}"
    old = slots / f".old-{suffix}"
    manifest = bundle.manifest.model_copy(
        update={
            "schema_version": version,
            "slot": slot,
            "saved_at": saved_at,
            "heroes": hero_ids,
        }
    )
    try:
        write_text(tmp / "world" / "world.json", bundle.world.model_dump_json(indent=2))
        write_text(tmp / "world" / "chronicle.json", bundle.chronicle.model_dump_json(indent=2))
        write_text(tmp / "world" / "memory.json", bundle.memory.model_dump_json(indent=2))
        for hero in bundle.heroes:
            hero_path = tmp / "heroes" / hero_dir_name(hero) / "hero.json"
            write_text(hero_path, hero.model_dump_json(indent=2))
        write_text(tmp / "session.json", bundle.session.model_dump_json(indent=2))
        write_text(tmp / "manifest.json", manifest.model_dump_json(indent=2))
        paths = [tmp / "world"] + [tmp / "heroes" / name for name in dir_names]
        if dir_names:
            paths.append(tmp / "heroes")
        sync_dirs(paths + [tmp])
        if final.exists():
            os.replace(final, old)
        try:
            os.replace(tmp, final)
        except BaseException:
            if old.exists():
                os.replace(old, final)
            raise
        sync_dirs([slots, slots.parent])
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    shutil.rmtree(old, ignore_errors=True)
    return final


def save_slot(root, bundle, slot: str, *, saved_at: str) -> Path:
    return write_slot(root, bundle.world.world_id, bundle, slot, saved_at=saved_at)


def move_slot(root, world_id: str, src: str, dst: str) -> None:
    # переименовать слот и поправить manifest.slot (сырой JSON: файл может быть старой версии)
    src_dir = slot_dir(root, world_id, src)
    dst_dir = slot_dir(root, world_id, dst)
    os.replace(src_dir, dst_dir)
    manifest_path = dst_dir / "manifest.json"
    raw = read_json(manifest_path)
    raw["slot"] = dst
    tmp_path = dst_dir / "manifest.json.tmp"
    write_text(tmp_path, json.dumps(raw, indent=2, ensure_ascii=False))
    os.replace(tmp_path, manifest_path)
    sync_dirs([dst_dir, dst_dir.parent])


def save_auto(root, bundle, *, saved_at: str, cfg, keep: int | None = None) -> Path:
    if keep is None:
        keep = cfg.saves.autosave_keep
    world_id = bundle.world.world_id
    if keep >= 1:
        last = slot_dir(root, world_id, f"auto-{keep}")
        if last.exists():
            old = last.parent / f".old-{uuid.uuid4().hex}"
            os.replace(last, old)
            shutil.rmtree(old)
        for number in range(keep - 1, 0, -1):
            if slot_dir(root, world_id, f"auto-{number}").exists():
                move_slot(root, world_id, f"auto-{number}", f"auto-{number + 1}")
        if slot_dir(root, world_id, "auto").exists():
            move_slot(root, world_id, "auto", "auto-1")
    return save_slot(root, bundle, "auto", saved_at=saved_at)


def recover_slots(root, world_id: str) -> None:
    # добрать хвосты упавшей записи: .old-* и .tmp-* в slots/
    slots = slots_dir(root, world_id)
    if not slots.is_dir():
        return
    olds = [p for p in slots.iterdir() if p.is_dir() and p.name.startswith(".old-")]
    tmps = [p for p in slots.iterdir() if p.is_dir() and p.name.startswith(".tmp-")]
    # сначала .tmp-*: полный -- это новая запись, она важнее .old-* того же слота
    for tmp in tmps:
        restore_or_remove(slots, tmp, must_have_manifest=True)
    for old in olds:
        restore_or_remove(slots, old, must_have_manifest=False)


def restore_or_remove(slots: Path, folder: Path, must_have_manifest: bool) -> None:
    manifest_path = folder / "manifest.json"
    if not manifest_path.is_file():
        if must_have_manifest:
            shutil.rmtree(folder)
        return
    name = read_json(manifest_path)["slot"]
    try:
        check_slot_name(name)
    except ValueError:
        return
    target = slots / name
    if target.exists():
        shutil.rmtree(folder)
    else:
        os.replace(folder, target)


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def peek_campaign_id(root, world_id: str, slot: str):
    # campaign_id из manifest до миграции: по нему выбирается реестр, нужный миграции цен
    recover_slots(root, world_id)
    folder = slot_dir(root, world_id, slot)
    return read_json(folder / "manifest.json").get("campaign_id")


def read_raw(folder: Path) -> dict:
    # сырой словарь без знания версии: герои по каталогам или корневой hero.json (v0)
    raw = {
        "manifest": read_json(folder / "manifest.json"),
        "world": read_json(folder / "world" / "world.json"),
        "session": read_json(folder / "session.json"),
    }
    if (folder / "world" / "chronicle.json").is_file():
        raw["chronicle"] = read_json(folder / "world" / "chronicle.json")
    if (folder / "world" / "memory.json").is_file():
        raw["memory"] = read_json(folder / "world" / "memory.json")
    if (folder / "heroes").is_dir():
        heroes = [read_json(p / "hero.json") for p in visible_dirs(folder / "heroes")]
        raw["heroes"] = sorted(heroes, key=lambda h: h["ordinal"])
    elif (folder / "hero.json").is_file():
        raw["hero"] = read_json(folder / "hero.json")
    return raw


def load_slot(
    root, world_id: str, slot: str, *, backup_ts=None, migrations=None, current_version=None,
    context=None,
) -> SaveBundle:
    check_slot_name(slot)
    recover_slots(root, world_id)
    if migrations is None:
        migrations = MIGRATIONS
    if current_version is None:
        current_version = CURRENT_SCHEMA_VERSION
    folder = slot_dir(root, world_id, slot)
    if not folder.is_dir():
        raise FileNotFoundError(str(folder))
    raw = read_raw(folder)
    version = raw["manifest"].get("schema_version", 0)
    if version > current_version:
        raise SaveTooNew(f"сейв версии {version}, движок знает до {current_version}")
    # миграция в памяти до бэкапа: нет звена или битый мир -- файлы не тронуты
    data = migrate(raw, registry=migrations, current_version=current_version, context=context)
    try:
        bundle = SaveBundle.model_validate(data)
    except ValidationError as error:
        lines = []
        for e in error.errors():
            field = ".".join(str(part) for part in e["loc"])
            lines.append(f"поле {field}: {e['msg']}")
        raise ValueError(
            f"сейв {world_id}/{slot} (версия {version}) не проходит проверку:\n" + "\n".join(lines)
        ) from error
    if bundle.world.world_id != world_id or bundle.manifest.world_id != world_id:
        raise ValueError(f"сейв другого мира лежит в каталоге {world_id!r}")
    bundle.manifest.slot = slot
    if version < current_version:
        make_backup(root, world_id, slot, version, backup_ts)
        write_slot(
            root, world_id, bundle, slot, saved_at=bundle.manifest.saved_at,
            version=current_version,
        )
    return bundle
