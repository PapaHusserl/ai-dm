# Ожидаемый API: ai_dm.reports.writer.write_report(saves_root, world_id, capture, text, now) -> Path
# (этап 6а, P0): каталог saves/<world>/issues/<YYYYMMDDTHHMMSS>-t<turn_seq>-<метки|manual>/ с
# report.md и meta.json; имя уникально (коллизия -- суффикс -2); запись атомарна (нет tmp-*);
# ошибка записи -- OSError наружу.
import json

import pytest
from reports_kit import NOW, make_capture

from ai_dm.reports.writer import write_report


def issues_dir(tmp_path):
    return tmp_path / "w1" / "issues"


def test_report_dir_has_report_md_and_meta_json(registry, tmp_path):
    path = write_report(tmp_path, "w1", make_capture(registry), "что-то не так", NOW)
    assert path.is_dir()
    assert (path / "report.md").is_file()
    assert (path / "meta.json").is_file()


def test_report_dir_is_inside_world_issues(registry, tmp_path):
    path = write_report(tmp_path, "w1", make_capture(registry), "текст", NOW)
    assert path.parent == issues_dir(tmp_path)


def test_manual_report_dir_name(registry, tmp_path):
    path = write_report(tmp_path, "w1", make_capture(registry), "текст", NOW)
    assert path.name == "20261007T123045-t5-manual"


def test_tag_report_dir_name_has_tag(registry, tmp_path):
    capture = make_capture(registry, tags=["missing-mechanic"])
    path = write_report(tmp_path, "w1", capture, "", NOW)
    assert path.name == "20261007T123045-t5-missing-mechanic"


def test_name_has_turn_seq(registry, tmp_path):
    path = write_report(tmp_path, "w1", make_capture(registry, turn_seq=12), "текст", NOW)
    assert "-t12-" in path.name


def test_same_name_gets_suffix_2(registry, tmp_path):
    capture = make_capture(registry)
    first = write_report(tmp_path, "w1", capture, "раз", NOW)
    second = write_report(tmp_path, "w1", capture, "два", NOW)
    assert second.name == first.name + "-2"


def test_third_same_name_gets_suffix_3(registry, tmp_path):
    capture = make_capture(registry)
    write_report(tmp_path, "w1", capture, "раз", NOW)
    write_report(tmp_path, "w1", capture, "два", NOW)
    third = write_report(tmp_path, "w1", capture, "три", NOW)
    assert third.name.endswith("-manual-3")


def test_second_report_does_not_overwrite_first(registry, tmp_path):
    capture = make_capture(registry)
    first = write_report(tmp_path, "w1", capture, "первый текст", NOW)
    write_report(tmp_path, "w1", capture, "второй текст", NOW)
    assert "первый текст" in (first / "report.md").read_text(encoding="utf-8")


def test_no_tmp_dirs_left_after_write(registry, tmp_path):
    write_report(tmp_path, "w1", make_capture(registry), "текст", NOW)
    names = [p.name for p in issues_dir(tmp_path).iterdir()]
    assert [n for n in names if n.startswith("tmp-")] == []


def test_report_md_has_player_text(registry, tmp_path):
    path = write_report(tmp_path, "w1", make_capture(registry), "дверь не открылась", NOW)
    assert "дверь не открылась" in (path / "report.md").read_text(encoding="utf-8")


def test_meta_json_has_report_format_1(registry, tmp_path):
    path = write_report(tmp_path, "w1", make_capture(registry), "текст", NOW)
    meta = json.loads((path / "meta.json").read_text(encoding="utf-8"))
    assert meta["report_format"] == 1


def test_meta_json_has_run_ids(registry, tmp_path):
    capture = make_capture(registry, run_ids=["run-1", "bnd-2"])
    path = write_report(tmp_path, "w1", capture, "", NOW)
    meta = json.loads((path / "meta.json").read_text(encoding="utf-8"))
    assert meta["run_ids"] == ["run-1", "bnd-2"]


def test_meta_json_has_tags_and_status(registry, tmp_path):
    capture = make_capture(registry, tags=["refusal"], status="aborted", failure_reason="refusal")
    path = write_report(tmp_path, "w1", capture, "", NOW)
    meta = json.loads((path / "meta.json").read_text(encoding="utf-8"))
    assert meta["tags"] == ["refusal"]
    assert meta["status"] == "aborted"
    assert meta["failure_reason"] == "refusal"


def test_meta_json_has_player_input_and_model(registry, tmp_path):
    path = write_report(tmp_path, "w1", make_capture(registry), "текст", NOW)
    meta = json.loads((path / "meta.json").read_text(encoding="utf-8"))
    assert meta["player_input"] == "Открываю дверь"
    assert meta["model"] == "claude-opus-5-5"


def test_meta_json_has_now(registry, tmp_path):
    path = write_report(tmp_path, "w1", make_capture(registry), "текст", NOW)
    meta = json.loads((path / "meta.json").read_text(encoding="utf-8"))
    assert meta["now"] == NOW.isoformat()


def test_two_tags_make_one_dir_with_both(registry, tmp_path):
    capture = make_capture(registry, tags=["limit-exceeded", "invalid-death"])
    path = write_report(tmp_path, "w1", capture, "", NOW)
    text = (path / "report.md").read_text(encoding="utf-8")
    assert "limit-exceeded" in text
    assert "invalid-death" in text
    assert len(list(issues_dir(tmp_path).iterdir())) == 1


def test_write_error_raises_oserror(registry, tmp_path):
    # на месте каталога issues лежит файл: создать каталог нельзя
    (tmp_path / "w1").mkdir()
    (tmp_path / "w1" / "issues").write_text("не каталог", encoding="utf-8")
    with pytest.raises(OSError):
        write_report(tmp_path, "w1", make_capture(registry), "текст", NOW)


def test_failed_write_leaves_no_report_dir(registry, tmp_path, monkeypatch):
    import os

    def broken(src, dst):
        raise OSError("диск полон")

    monkeypatch.setattr(os, "replace", broken)
    with pytest.raises(OSError):
        write_report(tmp_path, "w1", make_capture(registry), "текст", NOW)
    assert list(issues_dir(tmp_path).iterdir()) == []


def test_two_tags_dir_name_joins_with_plus(registry, tmp_path):
    capture = make_capture(registry, tags=["limit-exceeded", "invalid-death"])
    path = write_report(tmp_path, "w1", capture, "", NOW)
    assert path.name == "20261007T123045-t5-limit-exceeded+invalid-death"


def test_meta_json_keeps_cyrillic_readable(registry, tmp_path):
    path = write_report(tmp_path, "w1", make_capture(registry), "текст", NOW)
    raw = (path / "meta.json").read_text(encoding="utf-8")
    assert "Открываю дверь" in raw


def test_meta_json_has_world_id_and_manual_flag(registry, tmp_path):
    manual = write_report(tmp_path, "w1", make_capture(registry), "текст", NOW)
    auto = write_report(tmp_path, "w1", make_capture(registry, tags=["refusal"]), "", NOW)
    assert json.loads((manual / "meta.json").read_text(encoding="utf-8"))["world_id"] == "w1"
    assert json.loads((manual / "meta.json").read_text(encoding="utf-8"))["manual"] is True
    assert json.loads((auto / "meta.json").read_text(encoding="utf-8"))["manual"] is False


def test_other_world_gets_own_issues_dir(registry, tmp_path):
    path = write_report(tmp_path, "other", make_capture(registry), "текст", NOW)
    assert path.parent == tmp_path / "other" / "issues"
