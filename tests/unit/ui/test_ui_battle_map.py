# Карта боя (stage3-live-map, раздел T): раскладка, pos мастера, пометки, значки, строка движений,
# ширина, список при >8 зонах, /map. Идём через приложение: бой стартует scripted-ходом
# start_combat с заданным графом зон, карту смотрим по /map (и по меню хода).
# Допущения (ТРЕБОВАНИЕ к реализации, сверено со spec K1-K5): значки ● герой, ✕ враг, † упавший,
# «(скрыт)»; пометки ▲N / ▼N / укр.½ / укр.¾ / темно (feature kind "dark") / труднопрох. / опасно /
# выход; pos мастера -- поле pos: [ряд, колонка] в зоне start_combat; строка «Движение: ...».
import re

from ui_kit import (
    OPUS,
    ReactiveAdapter,
    ScriptThenReactive,
    build_app,
    numbered_lines,
    play,
    text_step,
)

from ai_dm.llm.mock import ScriptedAdapter

WIDTH = 80
HERO = "Арн"
FOE = "Грош"
FIGHT = "Дерусь"
NAMES = ["Вход", "Штольня", "Уступ", "Шахта", "Склад", "Лаз", "Обрыв", "Пещера", "Грот"]
LEGEND = ("●", "✕", "†")


def zone_specs(count, extra=None):
    zones = []
    for i in range(count):
        near = []
        if i > 0:
            near.append(f"z{i - 1}")
        if i < count - 1:
            near.append(f"z{i + 1}")
        zones.append({"id": f"z{i}", "name": NAMES[i], "adjacent": near})
    for index, fields in (extra or {}).items():
        zones[index].update(fields)
    return zones


def start_step(zones, enemy_zone, hero_zone="z0"):
    data = {
        "type": "start_combat",
        "hero_zone": hero_zone,
        "initiated_by": "hero",
        "zones": zones,
        "enemies": [
            {"ref": "g1", "monster_id": "goblin_warrior", "zone": enemy_zone,
             "group": "goblins", "name": FOE},
        ],
        "groups": [{"id": "goblins", "leader": "g1", "intent": "kill"}],
    }
    return {"tool_calls": [{"id": "c1", "name": "start_combat", "input": data}]}


def fight(registry, tmp_path, zones, enemy_zone=None):
    enemy_zone = enemy_zone or zones[-1]["id"]
    steps = [start_step(zones, enemy_zone), text_step("Бой.")]
    scripted = ScriptedAdapter(steps, provider="anthropic", model=OPUS)
    adapter = ScriptThenReactive(scripted, ReactiveAdapter())
    app = build_app(registry, tmp_path, adapter, hp=200)
    out = play(app, [FIGHT])
    return app, out


def wide_fight(registry, tmp_path, count):
    # старт боя допускает 2-5 зон; больше -- подменяем граф в уже идущем бою
    from ai_dm.state.combat import Zone

    app, _ = fight(registry, tmp_path, zone_specs(3))
    state = combat_of(app)
    state.zones = [Zone(**spec) for spec in zone_specs(count)]
    for participant in state.participants:
        if participant.side == "enemies":
            participant.zone_id = f"z{count - 1}"
    return app


def quiet_app(registry, tmp_path):
    adapter = ScriptedAdapter([text_step("Тихо.")], provider="anthropic", model=OPUS)
    return build_app(registry, tmp_path, adapter)


def map_raw(app):
    return app.handle("/map").raw


def raw_text(raw):
    return "\n".join(raw)


def column_of(raw, word):
    for line in raw:
        if word in line:
            return line.index(word)
    raise AssertionError(f"{word!r} нет на карте")


def row_of(raw, word):
    for number, line in enumerate(raw):
        if word in line:
            return number
    raise AssertionError(f"{word!r} нет на карте")


def combat_of(app):
    return app.bundle.session.active_combat


def test_layout_is_deterministic(registry, tmp_path):
    first, _ = fight(registry, tmp_path / "a", zone_specs(4))
    second, _ = fight(registry, tmp_path / "b", zone_specs(4))
    assert map_raw(first) == map_raw(second)


def test_layout_is_stable_between_calls(registry, tmp_path):
    app, _ = fight(registry, tmp_path, zone_specs(4))
    assert map_raw(app) == map_raw(app)


def test_zone_boxes_do_not_jump_when_people_move(registry, tmp_path):
    app, _ = fight(registry, tmp_path, zone_specs(4))
    before = map_raw(app)
    for participant in combat_of(app).participants:
        if participant.side == "enemies":
            participant.zone_id = "z1"
    after = map_raw(app)
    for name in NAMES[:4]:
        assert column_of(before, name) == column_of(after, name)
        assert row_of(before, name) == row_of(after, name)


def test_zones_go_left_to_right_by_distance_from_hero(registry, tmp_path):
    app, _ = fight(registry, tmp_path, zone_specs(3))
    raw = map_raw(app)
    columns = [column_of(raw, name) for name in NAMES[:3]]
    assert columns == sorted(columns)
    assert len(set(columns)) == 3


def test_master_pos_overrides_default_layout(registry, tmp_path):
    zones = zone_specs(3)
    for index, zone in enumerate(zones):
        zone["pos"] = [0, 2 - index]
    app, _ = fight(registry, tmp_path, zones)
    raw = map_raw(app)
    columns = [column_of(raw, name) for name in NAMES[:3]]
    assert columns == sorted(columns, reverse=True)


def test_master_pos_row_puts_zone_below(registry, tmp_path):
    zones = zone_specs(2)
    zones[0]["pos"] = [0, 0]
    zones[1]["pos"] = [1, 0]
    app, _ = fight(registry, tmp_path, zones)
    raw = map_raw(app)
    assert row_of(raw, NAMES[1]) > row_of(raw, NAMES[0])
    assert column_of(raw, NAMES[1]) == column_of(raw, NAMES[0])


def test_elevation_up_mark(registry, tmp_path):
    app, _ = fight(registry, tmp_path, zone_specs(3, {2: {"elevation": 2}}))
    assert "▲2" in raw_text(map_raw(app))


def test_elevation_down_mark(registry, tmp_path):
    app, _ = fight(registry, tmp_path, zone_specs(3, {2: {"elevation": -1}}))
    assert "▼1" in raw_text(map_raw(app))


def test_ground_has_no_elevation_mark(registry, tmp_path):
    app, _ = fight(registry, tmp_path, zone_specs(3))
    text = raw_text(map_raw(app))
    assert "▲" not in text.replace("▲N", "")
    assert "▼" not in text.replace("▼N", "")


def feature_zone(kind, **fields):
    return zone_specs(3, {1: {"features": [{"kind": kind, **fields}]}})


def test_half_cover_mark(registry, tmp_path):
    app, _ = fight(registry, tmp_path, feature_zone("cover_half"))
    assert "укр.½" in raw_text(map_raw(app))


def test_three_quarters_cover_mark(registry, tmp_path):
    app, _ = fight(registry, tmp_path, feature_zone("cover_three_quarters"))
    assert "укр.¾" in raw_text(map_raw(app))


def test_dark_mark(registry, tmp_path):
    app, _ = fight(registry, tmp_path, feature_zone("dark"))
    assert "темно" in raw_text(map_raw(app))


def test_difficult_mark(registry, tmp_path):
    app, _ = fight(registry, tmp_path, feature_zone("difficult"))
    assert "труднопрох." in raw_text(map_raw(app))


def test_hazard_mark(registry, tmp_path):
    zones = feature_zone("hazard", damage="1d4", damage_type="fire", save="dex", dc=10)
    app, _ = fight(registry, tmp_path, zones)
    assert "опасно" in raw_text(map_raw(app))


def test_exit_mark(registry, tmp_path):
    app, _ = fight(registry, tmp_path, zone_specs(3, {2: {"exit": True}}))
    assert "выход" in raw_text(map_raw(app))


def test_plain_zone_has_no_marks(registry, tmp_path):
    app, _ = fight(registry, tmp_path, zone_specs(3))
    text = raw_text(map_raw(app))
    for mark in ("укр.", "темно", "труднопрох.", "опасно"):
        assert mark not in text


def test_hero_has_icon_name_and_hp(registry, tmp_path):
    app, _ = fight(registry, tmp_path, zone_specs(3))
    assert f"● {HERO} 200/200" in raw_text(map_raw(app))


def test_enemy_has_icon_name_and_hp(registry, tmp_path):
    app, _ = fight(registry, tmp_path, zone_specs(3))
    assert re.search(rf"✕ {FOE}\S* \d+/\d+", raw_text(map_raw(app)))


def test_hero_and_enemy_stand_in_their_zones(registry, tmp_path):
    app, _ = fight(registry, tmp_path, zone_specs(3))
    raw = map_raw(app)
    assert column_of(raw, HERO) < column_of(raw, FOE)


def test_downed_enemy_has_dagger_icon(registry, tmp_path):
    app, _ = fight(registry, tmp_path, zone_specs(3))
    for participant in combat_of(app).participants:
        if participant.side == "enemies":
            participant.status = "down"
    text = raw_text(map_raw(app))
    assert f"† {FOE}" in text
    assert f"✕ {FOE}" not in text


def test_surrendered_enemy_is_marked_on_the_map(registry, tmp_path):
    app, _ = fight(registry, tmp_path, zone_specs(3))
    for participant in combat_of(app).participants:
        if participant.side == "enemies":
            participant.status = "surrendered"
    text = raw_text(map_raw(app))
    assert f"✕ {FOE}" in text
    assert "(сдался)" in text


def test_downed_hero_has_dagger_icon(registry, tmp_path):
    app, _ = fight(registry, tmp_path, zone_specs(3))
    for participant in combat_of(app).participants:
        if participant.side == "heroes":
            participant.status = "down"
    text = raw_text(map_raw(app))
    assert f"† {HERO}" in text
    assert f"● {HERO}" not in text


def test_hidden_hero_is_marked(registry, tmp_path):
    from ai_dm.state.creature import AppliedCondition

    app, _ = fight(registry, tmp_path, zone_specs(3))
    hero = app.bundle.heroes[0].creature
    hero.conditions.append(AppliedCondition(id="invisible", source="hidden", dc=15))
    assert "(скрыт)" in raw_text(map_raw(app))


def test_visible_hero_is_not_marked_hidden(registry, tmp_path):
    app, _ = fight(registry, tmp_path, zone_specs(3))
    assert "(скрыт)" not in raw_text(map_raw(app))


def test_legend_is_one_line_with_icons(registry, tmp_path):
    app, _ = fight(registry, tmp_path, zone_specs(3))
    raw = map_raw(app)
    legend = [line for line in raw if all(icon in line for icon in LEGEND)]
    assert len(legend) == 1


def test_no_movement_line_on_the_first_map(registry, tmp_path):
    _, out = fight(registry, tmp_path, zone_specs(3))
    assert "Движение:" not in out.text


def test_movement_line_shows_enemy_approach(registry, tmp_path):
    zones = zone_specs(4)
    app, out = fight(registry, tmp_path, zones, enemy_zone="z3")
    end = next(n for n, text in reversed(numbered_lines(out.lines)) if text == "Закончить ход")
    after = play(app, [str(end)])
    moves = [line for line in after.lines if line.startswith("Движение:")]
    assert len(moves) == 1
    assert re.search(rf"{FOE}\S* {NAMES[3]} → {NAMES[2]}", moves[0])


def test_map_is_shown_before_turn_menu(registry, tmp_path):
    _, out = fight(registry, tmp_path, zone_specs(3))
    text = out.text
    assert text.index(NAMES[1]) < text.index("Твой ход")


def test_map_command_in_fight_shows_map(registry, tmp_path):
    app, _ = fight(registry, tmp_path, zone_specs(3))
    text = "\n".join(map_raw(app))
    for name in NAMES[:3]:
        assert name in text


def test_map_command_does_not_spend_the_turn(registry, tmp_path):
    app, _ = fight(registry, tmp_path, zone_specs(3))
    before = [option.label for option in app.runner.preview_turn()]
    map_raw(app)
    assert [option.label for option in app.runner.preview_turn()] == before


def test_map_outside_fight_says_not_a_fight(registry, tmp_path):
    app = quiet_app(registry, tmp_path)
    reply = app.handle("/map")
    assert any("Сейчас не бой" in line for line in reply.lines)


def test_map_is_not_unknown_command(registry, tmp_path):
    app = quiet_app(registry, tmp_path)
    reply = app.handle("/map")
    assert not any("Неизвестная команда" in line for line in reply.lines)


def test_width_two_zones(registry, tmp_path):
    app, _ = fight(registry, tmp_path, zone_specs(2))
    assert max(len(line) for line in map_raw(app)) <= WIDTH


def test_width_four_zones(registry, tmp_path):
    app, _ = fight(registry, tmp_path, zone_specs(4))
    assert max(len(line) for line in map_raw(app)) <= WIDTH


def test_width_six_zones(registry, tmp_path):
    app = wide_fight(registry, tmp_path, 6)
    assert max(len(line) for line in map_raw(app)) <= WIDTH


def test_width_eight_zones(registry, tmp_path):
    app = wide_fight(registry, tmp_path, 8)
    assert max(len(line) for line in map_raw(app)) <= WIDTH


def test_eight_zones_all_present_on_map(registry, tmp_path):
    app = wide_fight(registry, tmp_path, 8)
    text = raw_text(map_raw(app))
    for name in NAMES[:8]:
        assert name in text


def test_more_than_eight_zones_is_a_list(registry, tmp_path):
    app = wide_fight(registry, tmp_path, 9)
    raw = map_raw(app)
    for name in NAMES[:9]:
        assert any(line.strip().startswith(name + ":") for line in raw)


def test_list_has_who_stands_in_zone(registry, tmp_path):
    app = wide_fight(registry, tmp_path, 9)
    raw = map_raw(app)
    first = next(line for line in raw if line.strip().startswith(NAMES[0] + ":"))
    last = next(line for line in raw if line.strip().startswith(NAMES[8] + ":"))
    assert HERO in first
    assert FOE in last


def test_list_has_no_boxes(registry, tmp_path):
    app = wide_fight(registry, tmp_path, 9)
    assert not any(line.startswith(("┌", "╭", "└", "╰")) for line in map_raw(app))


def test_list_width_is_limited(registry, tmp_path):
    app = wide_fight(registry, tmp_path, 9)
    assert max(len(line) for line in map_raw(app)) <= WIDTH


# длинное имя в рамке зоны: укорачивается имя, HP остаётся (живой прогон, 2026-10-06)

def test_fit_keeps_hp_and_cuts_name():
    from ai_dm.game.battle_map import fit

    text = " ✕ Культист-храмовник Лунной Девы 11/11"
    got = fit(text, 24)
    assert len(got) == 24
    assert got.endswith("… 11/11")
    assert got.startswith(" ✕ Культист")


def test_fit_keeps_hidden_mark_with_hp():
    from ai_dm.game.battle_map import fit

    got = fit(" ● Очень длинное имя героя 25/25 (скрыт)", 24)
    assert got.endswith("… 25/25 (скрыт)")
    assert len(got) == 24


def test_fit_short_text_and_no_hp_tail():
    from ai_dm.game.battle_map import fit

    assert fit(" ✕ Гоблин 7/7", 24) == " ✕ Гоблин 7/7"
    assert fit(" † Культист-храмовник Лунной Девы", 12) == " † Культист…"
    # хвост длиннее места -- обычная обрезка
    assert fit(" ✕ Имя 100/100 (скрыт)", 8) == " ✕ Имя …"


def test_box_lines_long_enemy_name_shows_hp():
    from types import SimpleNamespace

    from ai_dm.game.battle_map import box_lines

    zone = SimpleNamespace(name="Двор", elevation=0, features=[], exit=False)
    lines = box_lines(zone, ["✕ Культист-храмовник Лунной Девы 11/11"], 26)
    body = lines[1]
    assert len(body) == 26
    assert body.endswith("… 11/11│")
