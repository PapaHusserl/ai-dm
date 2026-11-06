# scripts/migrate_dusk_mainland.py <каталог мира|слота> -- одноразовая правка сейва dusk_academy:
# корень mainland, upper_market и gull_haven_inn под ним, абзац world_text, строки truths, блок
# близкого круга и мотивы команды, помолвка Нокса, внешность героини. stdlib, бэкап до записи,
# идемпотентность, отказ без записи. Синтетический слот во tmp_path; запуск отдельным процессом.
import json
import subprocess
import sys
from pathlib import Path

from ai_dm.state.hero import BackgroundSpec
from ai_dm.state.world import Location, Lore

SCRIPT = Path(__file__).parents[3] / "scripts" / "migrate_dusk_mainland.py"
WORLD_ID = "dusk_academy-d3de6c57"
CIRCLE_IDS = ("knox", "killian", "henry", "kurt", "leo", "zimmer", "orlando")
KNOX_NOTES = (
    "Мира — его любимая. Решил сделать ей предложение руки и сердца: готовит кольцо и момент"
    " — сделает его в ближайшей спокойной сцене наедине.\nПросьбы героини: 1) по имени\n"
    "Раньше: Только что приплыл с материка паромом, на острове никого не знает.\nБрат Люциана."
    " Цель - найти брата и позвать его в путешествие. Бунтарь.\n"
    "Он просто ищет Люциана в академии.\n\nРевность говорит спокойно."
)
CREW_NOTES = "Старый приятель Нокса: теперь команда пришла в Туманную Гавань.\nДобрый."
KILLIAN_NOTES = (
    "Старый приятель Нокса: а теперь его команда пришла в Туманную Гавань.\n"
    "Слушает её, спрашивает мнения, не давит; рад, когда она сама делает шаг первой. Дарит."
)


def loc(loc_id, parent_id=None):
    return {
        "id": loc_id, "name": loc_id, "parent_id": parent_id, "description": "", "tags": [],
        "connections": [], "visited": False, "origin": "ai",
    }


def make_slot(root, *, version=14, world_id=WORLD_ID, drop_npc=None, drop_loc=None,
              knox_notes=KNOX_NOTES, hero_description="Любознательная."):
    slot = root / "saves" / world_id / "slots" / "auto"
    (slot / "world").mkdir(parents=True)
    (slot / "heroes" / "01_мира").mkdir(parents=True)
    manifest = {
        "schema_version": version, "world_id": world_id, "slot": "auto",
        "current_hero_id": "hero",
    }
    npcs = {npc_id: {"notes": CREW_NOTES, "motive": "Найти старого друга Нокса."}
            for npc_id in CIRCLE_IDS}
    npcs["knox"] = {"notes": knox_notes, "motive": "Построить семью."}
    npcs["killian"]["notes"] = KILLIAN_NOTES
    npcs["lucian"] = {"notes": "Люциан."}
    npcs.pop(drop_npc, None)
    locations = {
        "dusk_cape": loc("dusk_cape"), "ferry_pier": loc("ferry_pier", "dusk_cape"),
        "gull_haven_inn": loc("gull_haven_inn", "ferry_pier"),
        "upper_market": loc("upper_market", "gull_haven_inn"),
    }
    locations.pop(drop_loc, None)
    world = {
        "world_id": world_id, "npcs": npcs, "locations": locations,
        "lore": {"world_text": "Остров.", "truths": "- Правда."},
    }
    hero = {"id": "hero", "sheet": {"background": {"description": hero_description}}}
    (slot / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    (slot / "world" / "world.json").write_text(
        json.dumps(world, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (slot / "heroes" / "01_мира" / "hero.json").write_text(
        json.dumps(hero, ensure_ascii=False), encoding="utf-8"
    )
    (slot / "session.json").write_text('{"turn_seq": 7}', encoding="utf-8")
    return slot


def run(path):
    return subprocess.run(
        [sys.executable, "-I", str(SCRIPT), str(path)], capture_output=True, text=True,
        encoding="utf-8", check=False,
    )


def world_of(slot):
    return json.loads((slot / "world" / "world.json").read_text(encoding="utf-8"))


def hero_of(slot):
    return json.loads((slot / "heroes" / "01_мира" / "hero.json").read_text(encoding="utf-8"))


def snapshot(root):
    return {p: p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def backups(root, slot):
    original = slot / "world" / "world.json"
    return [p for p in root.rglob("world.json") if p != original]


# применение

def test_apply_prints_done_with_backup_path(tmp_path):
    result = run(make_slot(tmp_path))
    assert result.returncode == 0
    assert result.stdout.startswith("Готово. Бэкап слота: ")


def test_apply_adds_mainland_root_valid_for_location_model(tmp_path):
    slot = make_slot(tmp_path)
    run(slot)
    locations = world_of(slot)["locations"]
    mainland = Location.model_validate(locations["mainland"])
    assert mainland.parent_id is None
    assert mainland.name == "Материк"
    assert mainland.description.startswith("Северное побережье материка")
    for data in locations.values():
        Location.model_validate(data)


def test_apply_moves_market_and_inn_under_mainland(tmp_path):
    slot = make_slot(tmp_path)
    run(slot)
    locations = world_of(slot)["locations"]
    assert locations["upper_market"]["parent_id"] == "mainland"
    assert locations["gull_haven_inn"]["parent_id"] == "mainland"
    assert locations["ferry_pier"]["parent_id"] == "dusk_cape"


def test_apply_appends_world_text_and_truths(tmp_path):
    slot = make_slot(tmp_path)
    run(slot)
    lore = Lore.model_validate(world_of(slot)["lore"])
    assert lore.world_text.startswith("Остров.\n\nМира давно живёт не на острове")
    assert lore.world_text.endswith("без ревности, укола и соперничества.")
    assert lore.truths == (
        "- Правда.\n- Мира живёт на материке, в Норд-Харборе (усадьба у южного склона);"
        " остров — за проливом.\n- Мира — полурослица с рыжими вьющимися волосами"
        " и фиалковыми глазами."
    )


def test_apply_appends_circle_block_to_all_seven(tmp_path):
    slot = make_slot(tmp_path)
    run(slot)
    npcs = world_of(slot)["npcs"]
    for npc_id in CIRCLE_IDS:
        assert "Зрелость: говорит о своих чувствах" in npcs[npc_id]["notes"]
        assert "Просьбы героини: не говорить и не решать за Миру." in npcs[npc_id]["notes"]
    assert npcs["lucian"]["notes"] == "Люциан."


def test_apply_looks_per_npc(tmp_path):
    slot = make_slot(tmp_path)
    run(slot)
    npcs = world_of(slot)["npcs"]
    assert "Внешность: носит бороду." in npcs["orlando"]["notes"]
    assert "без усов" not in npcs["orlando"]["notes"]
    assert npcs["kurt"]["notes"].endswith("Внешность: лицо чисто выбрито, без усов и бороды.")
    assert "серьга в ухе; руки в татуировках." in npcs["killian"]["notes"]
    assert "глаза зелёные; волосы тёмные, вихрастые." in npcs["henry"]["notes"]
    assert "; красавчик, блондин." in npcs["zimmer"]["notes"]
    assert "глаза тёмно-синие; волосы серебристые." in npcs["knox"]["notes"]


def test_apply_replaces_motives_but_not_knox(tmp_path):
    slot = make_slot(tmp_path)
    run(slot)
    npcs = world_of(slot)["npcs"]
    assert npcs["leo"]["motive"] == "Удивлять Миру всё новыми изобретениями."
    assert all("старого друга" not in npcs[i]["motive"] for i in CIRCLE_IDS)
    assert npcs["knox"]["motive"] == "Построить семью."


def test_apply_knox_removes_old_and_adds_engagement(tmp_path):
    slot = make_slot(tmp_path)
    run(slot)
    notes = world_of(slot)["npcs"]["knox"]["notes"]
    assert "Решил сделать ей предложение" not in notes
    assert "Раньше:" not in notes
    assert notes.startswith(
        "Мира — его любимая.\nПросьбы героини: 1) по имени\nБрат Люциана. Бунтарь.\n\n"
        "Ревность говорит спокойно.\n\nЗрелость"
    )
    assert notes.endswith(
        "\nМира — его невеста: он трижды вставал на одно колено, на третий раз она согласилась."
        " Весной они едут в холмы за благословением её родных.\nПомнит: Апельсиновый джем Миры"
        " получила леди Изольда. Барон де Морней проиграл Мире в шахматы — мат."
    )


def test_apply_killian_drops_first_step_phrase(tmp_path):
    slot = make_slot(tmp_path)
    run(slot)
    notes = world_of(slot)["npcs"]["killian"]["notes"]
    assert "Слушает её, спрашивает мнения, не давит. Дарит." in notes
    assert "шаг первой" not in notes


def test_apply_crew_lives_in_nord_harbor(tmp_path):
    slot = make_slot(tmp_path)
    result = run(slot)
    npcs = world_of(slot)["npcs"]
    for npc_id in CIRCLE_IDS[1:]:
        assert "команда живёт в Норд-Харборе, рядом с Мирой.\n" in npcs[npc_id]["notes"]
        assert "Туманную Гавань" not in npcs[npc_id]["notes"]
    assert "не найдена" not in result.stdout


def test_apply_crew_missing_phrase_is_reported_and_skipped(tmp_path):
    slot = make_slot(tmp_path)
    world = world_of(slot)
    world["npcs"]["leo"]["notes"] = "Изобретатель."
    (slot / "world" / "world.json").write_text(json.dumps(world, ensure_ascii=False), "utf-8")
    result = run(slot)
    assert result.returncode == 0
    assert "У leo не найдена фраза, пропущено: 'пришла в Туманную Гавань'" in result.stdout
    assert world_of(slot)["npcs"]["leo"]["notes"].startswith("Изобретатель.\n\nЗрелость")


def test_apply_knox_missing_phrases_are_reported_and_skipped(tmp_path):
    slot = make_slot(tmp_path, knox_notes="Просто заметки.")
    result = run(slot)
    assert result.returncode == 0
    assert result.stdout.count("У knox не найдена фраза") == 4
    assert world_of(slot)["npcs"]["knox"]["notes"].startswith("Просто заметки.\n\nЗрелость")


def test_apply_appends_hero_looks_to_background(tmp_path):
    slot = make_slot(tmp_path)
    run(slot)
    background = hero_of(slot)["sheet"]["background"]
    assert background["description"] == (
        "Любознательная. Внешность: рыжие вьющиеся волосы, фиалковые глаза."
    )
    assert BackgroundSpec.model_fields["description"].annotation is str


def test_apply_does_not_touch_manifest_and_session(tmp_path):
    slot = make_slot(tmp_path)
    manifest = (slot / "manifest.json").read_bytes()
    session = (slot / "session.json").read_bytes()
    run(slot)
    assert (slot / "manifest.json").read_bytes() == manifest
    assert (slot / "session.json").read_bytes() == session


def test_apply_creates_backup_with_original_world_and_hero(tmp_path):
    slot = make_slot(tmp_path)
    world = (slot / "world" / "world.json").read_bytes()
    hero = (slot / "heroes" / "01_мира" / "hero.json").read_bytes()
    run(slot)
    found = backups(tmp_path, slot)
    assert len(found) == 1
    assert found[0].read_bytes() == world
    backup_slot = found[0].parents[1]
    assert backup_slot.parent.name.startswith("backup-mainland-")
    assert (backup_slot / "heroes" / "01_мира" / "hero.json").read_bytes() == hero


def test_apply_leaves_no_tmp_file(tmp_path):
    run(make_slot(tmp_path))
    assert not list(tmp_path.rglob("*.tmp"))


def test_world_dir_argument_edits_auto_slot(tmp_path):
    slot = make_slot(tmp_path)
    assert run(tmp_path / "saves" / WORLD_ID).returncode == 0
    assert "mainland" in world_of(slot)["locations"]


def test_no_argument_exits_two():
    result = subprocess.run(
        [sys.executable, "-I", str(SCRIPT)], capture_output=True, text=True, encoding="utf-8",
        check=False,
    )
    assert result.returncode == 2


# отказ без записи

def refused(tmp_path, **kwargs):
    slot = make_slot(tmp_path, **kwargs)
    before = snapshot(tmp_path)
    result = run(slot)
    assert snapshot(tmp_path) == before
    assert result.returncode == 1
    assert "Отказ" in result.stdout


def test_other_world_is_refused(tmp_path):
    refused(tmp_path, world_id="other_world-1")


def test_version_8_is_refused(tmp_path):
    refused(tmp_path, version=8)


def test_version_15_is_refused(tmp_path):
    refused(tmp_path, version=15)


def test_missing_npc_is_refused(tmp_path):
    refused(tmp_path, drop_npc="zimmer")


def test_missing_location_is_refused(tmp_path):
    refused(tmp_path, drop_loc="upper_market")


def test_missing_manifest_is_refused(tmp_path):
    (tmp_path / "empty").mkdir()
    result = run(tmp_path / "empty")
    assert result.returncode == 1
    assert "Отказ" in result.stdout


# идемпотентность

def test_partial_hero_looks_present_not_doubled_and_world_applied(tmp_path):
    looks = "Любознательная. Внешность: рыжие вьющиеся волосы, фиалковые глаза."
    slot = make_slot(tmp_path, hero_description=looks)
    result = run(slot)
    assert result.stdout.startswith("Готово.")
    assert hero_of(slot)["sheet"]["background"]["description"] == looks
    assert world_of(slot)["locations"]["upper_market"]["parent_id"] == "mainland"


def test_second_run_says_already_applied_and_changes_nothing(tmp_path):
    slot = make_slot(tmp_path)
    run(slot)
    before = snapshot(tmp_path)
    result = run(slot)
    assert result.returncode == 0
    assert "Уже применено: изменений нет." in result.stdout
    assert snapshot(tmp_path) == before
    assert len(backups(tmp_path, slot)) == 1
