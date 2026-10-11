# AD1, W1: durable-запись сейва. Флаг durable.DURABLE (в тестах выключен корневым conftest),
# fsync подменён шпионами: os.fsync и fcntl.fcntl не трогают диск, а пишут путь по дескриптору.
# Порядок записи слота: fsync файлов -> fsync каталогов tmp -> replace -> fsync slots -> fsync мира.
import fcntl
import os
from pathlib import Path

import pytest

from ai_dm.persistence import durable
from ai_dm.persistence.layout import slot_dir, slots_dir
from ai_dm.persistence.store import load_slot, move_slot, save_auto, save_slot, write_slot

NOW = "2026-01-01T12:00:00Z"
GET_PATH = getattr(fcntl, "F_GETPATH", None)


def path_of(fd):
    if GET_PATH is not None:
        raw = real_fcntl(fd, GET_PATH, b"\0" * 1024)
        return Path(raw.split(b"\0")[0].decode()).resolve()
    return Path(os.readlink(f"/proc/self/fd/{fd}")).resolve()


real_fcntl = fcntl.fcntl
real_replace = os.replace


@pytest.fixture
def durable_on():
    durable.set_durable(True)
    yield
    durable.set_durable(False)


class Events(list):
    fail = ()


@pytest.fixture
def events(monkeypatch):
    # [("sync", путь)] и [("replace", src, dst)] по порядку; fail -- имена, на которых fsync падает
    log = Events()
    log.fail = set()

    def record(fd):
        path = path_of(fd)
        if path.name in log.fail:
            raise OSError("диск отказал")
        log.append(("sync", path))

    def fake_fsync(fd):
        record(fd)

    def fake_fcntl(fd, cmd, *args):
        if cmd == getattr(fcntl, "F_FULLFSYNC", None):
            record(fd)
            return 0
        return real_fcntl(fd, cmd, *args)

    def spy_replace(src, dst):
        log.append(("replace", Path(src).resolve(), Path(dst).resolve()))
        real_replace(src, dst)

    monkeypatch.setattr(os, "fsync", fake_fsync)
    monkeypatch.setattr(fcntl, "fcntl", fake_fcntl)
    monkeypatch.setattr(os, "replace", spy_replace)
    return log


def synced(log):
    return [e[1] for e in log if e[0] == "sync"]


def first_replace(log):
    return [e[0] for e in log].index("replace")


def slots_of(saves, bundle):
    return slots_dir(saves, bundle.world.world_id).resolve()


# sync_file / sync_dir

def test_sync_file_uses_full_fsync_when_available(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(fcntl, "F_FULLFSYNC", 51, raising=False)
    monkeypatch.setattr(fcntl, "fcntl", lambda fd, cmd, *a: calls.append((fd, cmd)) or 0)
    monkeypatch.setattr(os, "fsync", lambda fd: calls.append((fd, "fsync")))
    durable.sync_file(7)
    assert calls == [(7, 51)]


def test_sync_file_falls_back_to_fsync_when_full_fsync_fails(monkeypatch):
    calls = []

    def broken(fd, cmd, *a):
        raise OSError("не поддерживается")

    monkeypatch.setattr(fcntl, "F_FULLFSYNC", 51, raising=False)
    monkeypatch.setattr(fcntl, "fcntl", broken)
    monkeypatch.setattr(os, "fsync", lambda fd: calls.append(fd))
    durable.sync_file(7)
    assert calls == [7]


def test_sync_file_uses_fsync_when_no_full_fsync_attribute(monkeypatch):
    calls = []
    monkeypatch.delattr(fcntl, "F_FULLFSYNC", raising=False)
    monkeypatch.setattr(fcntl, "fcntl", lambda *a: calls.append("fcntl"))
    monkeypatch.setattr(os, "fsync", lambda fd: calls.append(("fsync", fd)))
    durable.sync_file(7)
    assert calls == [("fsync", 7)]


def test_sync_file_error_of_plain_fsync_goes_out(monkeypatch):
    def broken(fd):
        raise OSError("диск отказал")

    monkeypatch.delattr(fcntl, "F_FULLFSYNC", raising=False)
    monkeypatch.setattr(os, "fsync", broken)
    with pytest.raises(OSError):
        durable.sync_file(7)


def test_sync_dir_syncs_the_directory(events, tmp_path):
    durable.sync_dir(tmp_path)
    assert synced(events) == [tmp_path.resolve()]


def test_sync_dir_closes_descriptor_when_sync_fails(monkeypatch, tmp_path):
    opened = []
    closed = []
    real_open = os.open
    real_close = os.close

    def spy_open(path, flags, *a):
        fd = real_open(path, flags, *a)
        opened.append(fd)
        return fd

    def spy_close(fd):
        closed.append(fd)
        real_close(fd)

    def broken(fd):
        raise OSError("диск отказал")

    monkeypatch.delattr(fcntl, "F_FULLFSYNC", raising=False)
    monkeypatch.setattr(os, "fsync", broken)
    monkeypatch.setattr(os, "open", spy_open)
    monkeypatch.setattr(os, "close", spy_close)
    with pytest.raises(OSError):
        durable.sync_dir(tmp_path)
    assert len(opened) == 1
    assert closed == opened


def test_set_durable_changes_the_flag():
    durable.set_durable(True)
    assert durable.DURABLE is True
    durable.set_durable(False)
    assert durable.DURABLE is False


# write_slot

def test_write_slot_syncs_every_file_before_first_replace(durable_on, events, saves, bundle):
    write_slot(saves, "w1", bundle, "auto", saved_at=NOW)
    before = events[:first_replace(events)]
    names = [p.name for p in synced(before)]
    for name in ("world.json", "chronicle.json", "memory.json", "session.json", "manifest.json"):
        assert name in names
    assert names.count("hero.json") == 2


def test_write_slot_syncs_tmp_directories_before_first_replace(durable_on, events, saves, bundle):
    write_slot(saves, "w1", bundle, "auto", saved_at=NOW)
    before = synced(events[:first_replace(events)])
    tmp = [p for p in before if p.name == "world.json"][0].parent.parent
    assert tmp.name.startswith(".tmp-")
    assert tmp / "world" in before
    assert tmp in before
    heroes = [p for p in before if p.name == "hero.json"]
    for hero in heroes:
        assert hero.parent in before


def test_write_slot_syncs_files_before_directories(durable_on, events, saves, bundle):
    write_slot(saves, "w1", bundle, "auto", saved_at=NOW)
    before = synced(events[:first_replace(events)])
    last_file = max(i for i, p in enumerate(before) if p.suffix == ".json")
    first_dir = min(i for i, p in enumerate(before) if p.suffix != ".json")
    assert last_file < first_dir


def test_write_slot_syncs_slots_and_world_dir_after_replace(durable_on, events, saves, bundle):
    write_slot(saves, "w1", bundle, "auto", saved_at=NOW)
    after = synced(events[first_replace(events):])
    slots = slots_of(saves, bundle)
    assert after == [slots, slots.parent]
    assert events[-1] == ("sync", slots.parent)


def test_write_slot_replace_over_existing_syncs_after_both_replaces(
    durable_on, events, saves, bundle
):
    save_slot(saves, bundle, "auto", saved_at=NOW)
    del events[:]
    write_slot(saves, "w1", bundle, "auto", saved_at=NOW)
    kinds = [e[0] for e in events]
    last_replace = len(kinds) - 1 - kinds[::-1].index("replace")
    assert kinds.count("replace") == 2
    assert kinds[last_replace + 1:] == ["sync", "sync"]


def test_write_slot_keeps_syncing_when_slot_is_new_and_world_dir_exists(
    durable_on, events, saves, bundle
):
    save_slot(saves, bundle, "auto", saved_at=NOW)
    del events[:]
    write_slot(saves, "w1", bundle, "manual-a", saved_at=NOW)
    assert synced(events)[-2:] == [slots_of(saves, bundle), slots_of(saves, bundle).parent]


def test_write_slot_result_is_loadable(durable_on, saves, bundle):
    write_slot(saves, "w1", bundle, "auto", saved_at=NOW)
    assert load_slot(saves, "w1", "auto").world.world_id == "w1"


def test_write_slot_fsync_error_raises_and_old_slot_survives(durable_on, events, saves, bundle):
    save_slot(saves, bundle, "auto", saved_at=NOW)
    bundle.heroes[0].money_cp = 1
    events.fail.add("session.json")
    with pytest.raises(OSError):
        write_slot(saves, "w1", bundle, "auto", saved_at="2026-02-02T00:00:00Z")
    events.fail.clear()
    loaded = load_slot(saves, "w1", "auto")
    assert loaded.heroes[0].money_cp == 1235
    assert loaded.manifest.saved_at == NOW
    assert [p.name for p in slots_dir(saves, "w1").iterdir()] == ["auto"]


def test_write_slot_dir_fsync_error_raises_and_removes_tmp(durable_on, events, saves, bundle):
    save_slot(saves, bundle, "auto", saved_at=NOW)
    events.fail.add("heroes")
    with pytest.raises(OSError):
        write_slot(saves, "w1", bundle, "auto", saved_at="2026-02-02T00:00:00Z")
    assert [p.name for p in slots_dir(saves, "w1").iterdir()] == ["auto"]
    assert load_slot(saves, "w1", "auto").manifest.saved_at == NOW


def test_write_slot_fsync_error_without_old_slot_leaves_nothing(durable_on, events, saves, bundle):
    events.fail.add("manifest.json")
    with pytest.raises(OSError):
        write_slot(saves, "w1", bundle, "auto", saved_at=NOW)
    assert list(slots_dir(saves, "w1").iterdir()) == []


def test_write_slot_with_empty_heroes_still_syncs(durable_on, events, saves, empty_bundle):
    write_slot(saves, "w1", empty_bundle, "auto", saved_at=NOW)
    names = [p.name for p in synced(events)]
    assert "manifest.json" in names
    assert "hero.json" not in names


# DURABLE = False

def test_write_slot_without_durable_does_no_sync(events, saves, bundle):
    write_slot(saves, "w1", bundle, "auto", saved_at=NOW)
    assert synced(events) == []


def test_move_slot_without_durable_does_no_sync(events, saves, bundle):
    save_slot(saves, bundle, "auto", saved_at=NOW)
    move_slot(saves, "w1", "auto", "auto-1")
    assert synced(events) == []


def test_save_auto_without_durable_does_no_sync(events, saves, bundle, cfg):
    save_auto(saves, bundle, saved_at=NOW, cfg=cfg)
    save_auto(saves, bundle, saved_at=NOW, cfg=cfg)
    assert synced(events) == []


def test_without_durable_files_are_still_written(events, saves, bundle):
    write_slot(saves, "w1", bundle, "auto", saved_at=NOW)
    assert (slot_dir(saves, "w1", "auto") / "manifest.json").is_file()


# move_slot / save_auto

def test_move_slot_syncs_manifest_tmp_and_dirs(durable_on, events, saves, bundle):
    save_slot(saves, bundle, "auto", saved_at=NOW)
    del events[:]
    move_slot(saves, "w1", "auto", "auto-1")
    dst = slot_dir(saves, "w1", "auto-1").resolve()
    assert ("sync", dst / "manifest.json.tmp") in events
    assert synced(events)[-2:] == [dst, dst.parent]


def test_move_slot_syncs_file_before_its_replace(durable_on, events, saves, bundle):
    save_slot(saves, bundle, "auto", saved_at=NOW)
    del events[:]
    move_slot(saves, "w1", "auto", "auto-1")
    dst = slot_dir(saves, "w1", "auto-1").resolve()
    file_sync = events.index(("sync", dst / "manifest.json.tmp"))
    manifest_replace = events.index(("replace", dst / "manifest.json.tmp", dst / "manifest.json"))
    assert file_sync < manifest_replace
    assert events.index(("sync", dst)) > manifest_replace


def test_move_slot_keeps_manifest_slot_name(durable_on, events, saves, bundle):
    save_slot(saves, bundle, "auto", saved_at=NOW)
    move_slot(saves, "w1", "auto", "auto-1")
    assert load_slot(saves, "w1", "auto-1").manifest.slot == "auto-1"


def test_save_auto_syncs_slots_dir_before_writing_new_slot(durable_on, events, saves, bundle, cfg):
    save_auto(saves, bundle, saved_at=NOW, cfg=cfg)
    del events[:]
    save_auto(saves, bundle, saved_at=NOW, cfg=cfg)
    slots = slots_of(saves, bundle)
    tmp_syncs = [i for i, e in enumerate(events) if e[0] == "sync" and ".tmp-" in str(e[1])]
    first_tmp_file = tmp_syncs[0]
    assert ("sync", slots) in events[:first_tmp_file]


def test_first_save_auto_in_new_world_works(durable_on, saves, bundle, cfg):
    save_auto(saves, bundle, saved_at=NOW, cfg=cfg)
    assert load_slot(saves, "w1", "auto").manifest.slot == "auto"


def test_save_auto_rotation_leaves_loadable_slots(durable_on, saves, bundle, cfg):
    for _ in range(3):
        save_auto(saves, bundle, saved_at=NOW, cfg=cfg)
    assert load_slot(saves, "w1", "auto-2").manifest.slot == "auto-2"


def test_save_auto_with_keep_zero_does_no_rotation_sync_but_writes(
    durable_on, events, saves, bundle, cfg
):
    save_auto(saves, bundle, saved_at=NOW, cfg=cfg, keep=0)
    before = events[:first_replace(events)]
    assert all(".tmp-" in str(p) for p in synced(before))
