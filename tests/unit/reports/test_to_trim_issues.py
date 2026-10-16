# ТО (docs/TO-PLAN.md §1 п.5, Q3а, Q5а): reports.writer.dir_size(path) -> int и
# trim_issues(saves_root, world_id, max_mb) -> list[Path] -- удалённые каталоги. MB = 1_000_000.
# Хронология -- по имени каталога; самый новый не удаляется; manual и tmp-* не трогаются.
import json

from ai_dm.reports.writer import dir_size, trim_issues

OLD = "20261001T000000-t1-refusal"
MID = "20261002T000000-t2-refusal"
NEW = "20261003T000000-t3-refusal"
CHUNK = 600_000


def issues_dir(root):
    return root / "w1" / "issues"


def make_issue(root, name, size=CHUNK, meta=None):
    path = issues_dir(root) / name
    path.mkdir(parents=True)
    (path / "journal.bin").write_bytes(b"x" * size)
    if meta is not None:
        text = meta if isinstance(meta, str) else json.dumps(meta)
        (path / "meta.json").write_text(text, encoding="utf-8")
    return path


def names(root):
    return sorted(p.name for p in issues_dir(root).iterdir())


# dir_size

def test_dir_size_of_empty_dir_is_zero(tmp_path):
    assert dir_size(tmp_path) == 0


def test_dir_size_sums_nested_files(tmp_path):
    (tmp_path / "a" / "b").mkdir(parents=True)
    (tmp_path / "one").write_bytes(b"x" * 10)
    (tmp_path / "a" / "two").write_bytes(b"x" * 20)
    (tmp_path / "a" / "b" / "three").write_bytes(b"x" * 300)
    assert dir_size(tmp_path) == 330


# trim_issues: когда ничего не делаем

def test_zero_limit_means_no_trimming(tmp_path):
    for name in (OLD, MID, NEW):
        make_issue(tmp_path, name, 2_000_000)
    assert trim_issues(tmp_path, "w1", 0) == []
    assert names(tmp_path) == [OLD, MID, NEW]


def test_total_below_limit_removes_nothing(tmp_path):
    make_issue(tmp_path, OLD)
    make_issue(tmp_path, NEW, 300_000)
    assert trim_issues(tmp_path, "w1", 1) == []
    assert names(tmp_path) == [OLD, NEW]


def test_missing_issues_dir_is_not_an_error(tmp_path):
    assert trim_issues(tmp_path, "w1", 1) == []


# trim_issues: над лимитом

def test_over_limit_removes_oldest_first(tmp_path):
    for name in (MID, OLD, NEW):
        make_issue(tmp_path, name, 400_000)
    removed = trim_issues(tmp_path, "w1", 1)
    assert [p.name for p in removed] == [OLD]
    assert names(tmp_path) == [MID, NEW]


def test_removal_stops_as_soon_as_total_fits(tmp_path):
    for name in (OLD, MID, NEW):
        make_issue(tmp_path, name)
    removed = trim_issues(tmp_path, "w1", 1)
    assert [p.name for p in removed] == [OLD, MID]
    assert names(tmp_path) == [NEW]


def test_limit_is_in_megabytes_of_one_million_bytes(tmp_path):
    make_issue(tmp_path, OLD, 900_000)
    make_issue(tmp_path, NEW, 200_000)
    assert [p.name for p in trim_issues(tmp_path, "w1", 1)] == [OLD]


def test_total_exactly_at_limit_is_kept(tmp_path):
    make_issue(tmp_path, OLD, 500_000)
    make_issue(tmp_path, NEW, 500_000)
    assert trim_issues(tmp_path, "w1", 1) == []


def test_newest_is_kept_even_if_it_alone_exceeds_limit(tmp_path):
    make_issue(tmp_path, OLD, 100)
    make_issue(tmp_path, NEW, 3_000_000)
    trim_issues(tmp_path, "w1", 1)
    assert names(tmp_path) == [NEW]


def test_single_issue_over_limit_is_kept(tmp_path):
    make_issue(tmp_path, NEW, 3_000_000)
    assert trim_issues(tmp_path, "w1", 1) == []
    assert names(tmp_path) == [NEW]


def test_removed_directories_are_gone_from_disk(tmp_path):
    old = make_issue(tmp_path, OLD)
    make_issue(tmp_path, NEW)
    removed = trim_issues(tmp_path, "w1", 1)
    assert removed == [old]
    assert not old.exists()


def test_other_worlds_are_not_touched(tmp_path):
    other = tmp_path / "w2" / "issues" / OLD
    other.mkdir(parents=True)
    (other / "f").write_bytes(b"x" * 3_000_000)
    make_issue(tmp_path, NEW)
    trim_issues(tmp_path, "w1", 1)
    assert other.exists()


# manual (Q5а)

def test_manual_report_is_not_removed(tmp_path):
    manual = make_issue(tmp_path, OLD, meta={"manual": True})
    make_issue(tmp_path, MID, meta={"manual": False})
    make_issue(tmp_path, NEW, meta={"manual": False})
    removed = trim_issues(tmp_path, "w1", 1)
    assert [p.name for p in removed] == [MID]
    assert manual.exists()


def test_auto_reports_older_than_manual_are_removed(tmp_path):
    make_issue(tmp_path, OLD, meta={"manual": False})
    make_issue(tmp_path, MID, meta={"manual": True})
    make_issue(tmp_path, NEW, meta={"manual": False})
    removed = trim_issues(tmp_path, "w1", 1)
    assert OLD in [p.name for p in removed]
    assert MID not in [p.name for p in removed]


def test_only_manual_reports_over_limit_are_all_kept(tmp_path):
    for name in (OLD, MID, NEW):
        make_issue(tmp_path, name, meta={"manual": True})
    assert trim_issues(tmp_path, "w1", 1) == []
    assert names(tmp_path) == [OLD, MID, NEW]


def test_broken_meta_json_counts_as_auto(tmp_path):
    make_issue(tmp_path, OLD, meta="{не json")
    make_issue(tmp_path, NEW)
    assert [p.name for p in trim_issues(tmp_path, "w1", 1)] == [OLD]


def test_missing_meta_json_counts_as_auto(tmp_path):
    make_issue(tmp_path, OLD)
    make_issue(tmp_path, NEW)
    assert [p.name for p in trim_issues(tmp_path, "w1", 1)] == [OLD]


def test_meta_without_manual_key_counts_as_auto(tmp_path):
    make_issue(tmp_path, OLD, meta={"tags": ["refusal"]})
    make_issue(tmp_path, NEW)
    assert [p.name for p in trim_issues(tmp_path, "w1", 1)] == [OLD]


# tmp-*

def test_tmp_dirs_are_neither_counted_nor_removed(tmp_path):
    tmp = make_issue(tmp_path, "tmp-abcd1234", 5_000_000)
    make_issue(tmp_path, OLD, 300_000)
    make_issue(tmp_path, NEW, 300_000)
    assert trim_issues(tmp_path, "w1", 1) == []
    assert tmp.exists()


def test_tmp_dir_is_never_picked_as_oldest_or_newest(tmp_path):
    tmp = make_issue(tmp_path, "tmp-zzzz9999", 100)
    make_issue(tmp_path, OLD)
    make_issue(tmp_path, NEW)
    removed = trim_issues(tmp_path, "w1", 1)
    assert [p.name for p in removed] == [OLD]
    assert tmp.exists()
