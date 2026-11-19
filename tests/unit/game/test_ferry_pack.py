# М0 П2, решение 90: перевозка насквозь на паке-фикстуре tests/fixtures/packs/ferry.
#   Берег shore ↔ Остров island (4800 м водой, needs_transport), сухой Луг meadow (300 м), у берега
#   Финн (finn) с услугой ferry. Вид услуги -- из defaults.toml, не подменяется. Мир: load_pack +
#   new_world_from_pack, команды -- app.handle, мастер -- заглушка, живых вызовов нет.
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ui"))

from game_kit import OPUS, SAVED_AT, ScriptedAdapter, make_app, settings  # noqa: E402
from ui_kit import text_step  # noqa: E402

from ai_dm.campaign.loader import load_pack  # noqa: E402
from ai_dm.game.starter import new_world_from_pack  # noqa: E402
from ai_dm.state.world import NPC  # noqa: E402

FERRY = Path(__file__).resolve().parents[2] / "fixtures" / "packs" / "ferry"


def ferry_app(registry, tmp_path):
    cfg = settings()
    pack = load_pack(FERRY, registry)
    bundle = new_world_from_pack(
        registry, cfg.rules, pack, hero="arn", seed=3, world_id="ferry-t", saved_at=SAVED_AT
    )
    adapter = ScriptedAdapter([text_step()], provider="anthropic", model=OPUS)
    return make_app(registry, tmp_path, adapter, bundle=bundle, model=OPUS)


def hero_of(app):
    return app.bundle.heroes[0]


def snapshot(app):
    hero = hero_of(app)
    return hero.location_id, app.bundle.world.clock.now_s, hero.money_cp


def test_pack_loads_and_finn_offers_ferry(registry):
    pack = load_pack(FERRY, registry)
    finn = [n for n in pack.npcs if n.id == "finn"][0]
    assert finn.services == ["ferry"]


def test_where_shows_closed_island_and_timed_meadow(registry, tmp_path):
    app = ferry_app(registry, tmp_path)
    before = snapshot(app)
    lines = app.handle("/where").lines
    island = [line for line in lines if "Остров" in line]
    meadow = [line for line in lines if "Луг" in line]
    assert any("Остров — 4800 м, водный путь — нужен транспорт" in line for line in island)
    assert meadow
    assert "нужен транспорт" not in meadow[0]
    assert "мин" in meadow[0]
    assert snapshot(app) == before


def test_go_island_without_boat_names_the_ferryman(registry, tmp_path):
    app = ferry_app(registry, tmp_path)
    before = snapshot(app)
    text = " ".join(app.handle("/go Остров").lines)
    assert "до «Остров» только по воде — нужен водный транспорт; перевозят: Финн" in text
    assert "island" not in text
    assert snapshot(app) == before


def test_shop_shows_one_passage_line_and_none_for_dry_neighbour(registry, tmp_path):
    app = ferry_app(registry, tmp_path)
    lines = [line for line in app.handle("/shop").lines if "перевозка:" in line]
    assert len(lines) == 1
    assert "перевозка: Остров — 5 см / раз" in lines[0]
    assert not [line for line in lines if "Луг" in line]


def test_ferry_crosses_charges_and_logs(registry, tmp_path):
    app = ferry_app(registry, tmp_path)
    start = snapshot(app)
    lines = app.handle("/shop услуга finn ferry:island 1").lines
    assert "Перевозка: Финн, 5 см — «Остров»" in lines
    assert hero_of(app).location_id == "island"
    assert app.bundle.world.clock.now_s == start[1] + 1800
    assert start[2] - hero_of(app).money_cp == 50
    assert app.bundle.world.flags["visited:island"] is True


def add_follower(app):
    app.bundle.world.npcs["bran"] = NPC(
        id="bran", name="Бран", named=True, means=["меч"], location_id="shore",
        follows=hero_of(app).id,
    )


def test_ferry_with_follower_takes_him_for_one_price(registry, tmp_path):
    app = ferry_app(registry, tmp_path)
    add_follower(app)
    start = snapshot(app)
    lines = app.handle("/shop услуга finn ferry:island 1").lines
    assert "С тобой: Бран" in lines
    assert app.bundle.world.npcs["bran"].location_id == "island"
    assert start[2] - hero_of(app).money_cp == 50


def test_ferry_without_money_is_refused(registry, tmp_path):
    app = ferry_app(registry, tmp_path)
    hero_of(app).money_cp = 49
    before = snapshot(app)
    lines = app.handle("/shop услуга finn ferry:island 1").lines
    assert not [line for line in lines if line.startswith("Перевозка:")]
    assert snapshot(app) == before
    assert hero_of(app).location_id == "shore"


# обратно: перевозчик плывёт с героем (решения 94, 98), на острове всё те же команды

def crossed_app(registry, tmp_path):
    app = ferry_app(registry, tmp_path)
    app.handle("/shop услуга finn ferry:island 1")
    return app


def test_after_crossing_finn_is_on_the_island(registry, tmp_path):
    app = crossed_app(registry, tmp_path)
    assert app.bundle.world.npcs["finn"].location_id == "island"


def test_shop_on_the_island_offers_passage_back(registry, tmp_path):
    app = crossed_app(registry, tmp_path)
    lines = app.handle("/shop").lines
    assert any("перевозка: Берег — 5 см / раз" in line for line in lines)


def test_where_on_the_island_shows_closed_shore(registry, tmp_path):
    app = crossed_app(registry, tmp_path)
    lines = app.handle("/where").lines
    assert any("Берег — 4800 м, водный путь — нужен транспорт" in line for line in lines)


def test_go_shore_from_the_island_names_finn_and_stays(registry, tmp_path):
    app = crossed_app(registry, tmp_path)
    before = snapshot(app)
    text = " ".join(app.handle("/go Берег").lines)
    assert "перевозят: Финн" in text
    assert snapshot(app) == before
    assert hero_of(app).location_id == "island"


def test_ferry_back_returns_hero_and_finn_for_a_second_price(registry, tmp_path):
    app = crossed_app(registry, tmp_path)
    start = snapshot(app)
    lines = app.handle("/shop услуга finn ferry:shore 1").lines
    assert "Перевозка: Финн, 5 см — «Берег»" in lines
    assert hero_of(app).location_id == "shore"
    assert app.bundle.world.npcs["finn"].location_id == "shore"
    assert start[2] - hero_of(app).money_cp == 50
    assert app.bundle.world.clock.now_s == start[1] + 1800


def test_round_trip_costs_two_prices_and_an_hour(registry, tmp_path):
    app = ferry_app(registry, tmp_path)
    start = snapshot(app)
    app.handle("/shop услуга finn ferry:island 1")
    app.handle("/shop услуга finn ferry:shore 1")
    assert start[2] - hero_of(app).money_cp == 100
    assert app.bundle.world.clock.now_s == start[1] + 3600


# М0 П2б, решения 96, 98–101: Финн возвращается на берег, когда герой пришёл туда без него

def returned_app(registry, tmp_path):
    app = crossed_app(registry, tmp_path)
    hero_of(app).location_id = "meadow"
    return app


def test_crossing_records_finns_home_shore(registry, tmp_path):
    app = crossed_app(registry, tmp_path)
    assert app.bundle.world.flags["ferry_home:finn"] == "shore"
    assert app.bundle.world.npcs["finn"].location_id == "island"


def test_hero_walking_to_the_shore_brings_finn_back(registry, tmp_path):
    app = returned_app(registry, tmp_path)
    app.handle("/go Берег")
    assert hero_of(app).location_id == "shore"
    assert app.bundle.world.npcs["finn"].location_id == "shore"
    assert "ferry_home:finn" not in app.bundle.world.flags


def test_after_return_go_island_names_finn_again(registry, tmp_path):
    app = returned_app(registry, tmp_path)
    app.handle("/go Берег")
    text = " ".join(app.handle("/go Остров").lines)
    assert "до «Остров» только по воде — нужен водный транспорт; перевозят: Финн" in text


def test_after_return_shop_offers_the_passage_to_the_island(registry, tmp_path):
    app = returned_app(registry, tmp_path)
    app.handle("/go Берег")
    lines = [line for line in app.handle("/shop").lines if "перевозка:" in line]
    assert len(lines) == 1
    assert "перевозка: Остров — 5 см / раз" in lines[0]


def test_return_of_finn_has_no_feed_line(registry, tmp_path):
    app = returned_app(registry, tmp_path)
    lines = app.handle("/go Берег").lines
    assert not [line for line in lines if "Финн" in line]


def test_round_trip_with_finn_leaves_no_home_flag(registry, tmp_path):
    app = ferry_app(registry, tmp_path)
    app.handle("/shop услуга finn ferry:island 1")
    app.handle("/shop услуга finn ferry:shore 1")
    assert "ferry_home:finn" not in app.bundle.world.flags


def test_ferry_back_takes_the_follower_for_one_price(registry, tmp_path):
    app = ferry_app(registry, tmp_path)
    add_follower(app)
    app.handle("/shop услуга finn ferry:island 1")
    mid = hero_of(app).money_cp
    app.handle("/shop услуга finn ferry:shore 1")
    assert app.bundle.world.npcs["bran"].location_id == "shore"
    assert mid - hero_of(app).money_cp == 50
