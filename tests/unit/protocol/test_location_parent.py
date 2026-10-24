# Родитель и длина связей у location_create (Фикс dusk П1, BACKLOG 170): parent_id обязателен;
# связь с локацией внутри родителя (он сам, потомки, предки) не длиннее cfg.locations.inside_max_m;
# наружу без лимита.
import pytest
from protocol_kit import dump, make_ctx, req

from ai_dm.protocol.apply import apply
from ai_dm.protocol.decision import Invalid
from ai_dm.state.world import Location


def make_academy_ctx(registry, cfg):
    ctx = make_ctx(registry, cfg)
    locations = ctx.bundle.world.locations
    locations["academy"] = Location(id="academy", name="Академия")
    locations["hall"] = Location(id="hall", name="Зал", parent_id="academy")
    locations["candle_library"] = Location(id="candle_library", name="Свечная", parent_id="hall")
    locations["misty_haven"] = Location(id="misty_haven", name="Туманная Гавань")
    return ctx


def create(ctx, connections, parent_id="academy", **kwargs):
    fields = {"id": "annex", "name": "Пристройка", "parent_id": parent_id,
              "connections": connections}
    fields.update(kwargs)
    return apply(ctx, req("location_create", **fields))


def link(to, distance_m):
    return {"to": to, "distance_m": distance_m}


def test_location_create_without_parent_is_rejected(registry, cfg):
    ctx = make_academy_ctx(registry, cfg)
    before = dump(ctx)
    d = create(ctx, [], parent_id="")
    assert d.status == "rejected"
    assert "parent_id" in d.signal_to_master
    assert dump(ctx) == before


def test_location_create_without_parent_is_rejected_with_connections(registry, cfg):
    ctx = make_academy_ctx(registry, cfg)
    d = create(ctx, [link("misty_haven", 100)], parent_id="")
    assert d.status == "rejected"
    assert "parent_id" in d.signal_to_master


def test_location_create_taken_name_without_parent_names_existing_id(registry, cfg):
    ctx = make_academy_ctx(registry, cfg)
    d = create(ctx, [], parent_id="", name="Таверна")
    assert d.status == "rejected"
    assert "vale_tavern" in d.signal_to_master


def test_link_to_sibling_of_parent_far_is_accepted(registry, cfg):
    # сосед родителя (другой ребёнок academy) -- «наружу», лимита нет
    ctx = make_academy_ctx(registry, cfg)
    ctx.bundle.world.locations["gallery"] = Location(
        id="gallery", name="Галерея", parent_id="academy"
    )
    assert create(ctx, [link("gallery", 3000)], parent_id="hall").status == "accepted"


def test_location_create_unknown_parent_is_invalid(registry, cfg):
    ctx = make_academy_ctx(registry, cfg)
    d = create(ctx, [], parent_id="nowhere")
    assert isinstance(d, Invalid)
    assert d.code == "unknown_location"


def test_location_create_parent_only_is_accepted(registry, cfg):
    ctx = make_academy_ctx(registry, cfg)
    assert create(ctx, []).status == "accepted"
    assert "annex" in ctx.bundle.world.locations


def test_inside_link_at_limit_is_accepted(registry, cfg):
    ctx = make_academy_ctx(registry, cfg)
    assert create(ctx, [link("hall", 500)]).status == "accepted"


def test_inside_link_over_limit_is_rejected(registry, cfg):
    ctx = make_academy_ctx(registry, cfg)
    before = dump(ctx)
    d = create(ctx, [link("hall", 501)])
    assert d.status == "rejected"
    assert dump(ctx) == before


def test_inside_link_rejection_names_id_and_meters(registry, cfg):
    ctx = make_academy_ctx(registry, cfg)
    d = create(ctx, [link("candle_library", 3500)])
    assert "candle_library" in d.signal_to_master
    assert "3500" in d.signal_to_master
    assert "500" in d.signal_to_master


def test_link_to_parent_itself_over_limit_is_rejected(registry, cfg):
    ctx = make_academy_ctx(registry, cfg)
    assert create(ctx, [link("academy", 3000)]).status == "rejected"


def test_link_to_grandchild_over_limit_is_rejected(registry, cfg):
    ctx = make_academy_ctx(registry, cfg)
    assert create(ctx, [link("candle_library", 3000)]).status == "rejected"


def test_link_to_ancestor_of_parent_over_limit_is_rejected(registry, cfg):
    ctx = make_academy_ctx(registry, cfg)
    assert create(ctx, [link("academy", 3000)], parent_id="candle_library").status == "rejected"


def test_outside_link_far_is_accepted(registry, cfg):
    ctx = make_academy_ctx(registry, cfg)
    assert create(ctx, [link("misty_haven", 3500)]).status == "accepted"


def test_far_location_under_other_parent_is_accepted(registry, cfg):
    # «Хутор» в области, до соседа за пределами области 4000 м
    ctx = make_academy_ctx(registry, cfg)
    d = create(ctx, [link("vale", 4000)], parent_id="forest", id="farm", name="Хутор")
    assert d.status == "accepted"


def test_one_far_inside_link_among_several_rejects(registry, cfg):
    ctx = make_academy_ctx(registry, cfg)
    d = create(ctx, [link("misty_haven", 3500), link("hall", 900)])
    assert d.status == "rejected"


def test_inside_limit_comes_from_config(registry, cfg):
    small = cfg.model_copy(deep=True)
    small.locations.inside_max_m = 50
    ctx = make_academy_ctx(registry, small)
    assert create(ctx, [link("hall", 51)]).status == "rejected"


@pytest.mark.parametrize("distance", [0, 10])
def test_short_inside_links_are_accepted(distance, registry, cfg):
    ctx = make_academy_ctx(registry, cfg)
    assert create(ctx, [link("hall", distance)]).status == "accepted"


def test_missing_parent_reason_says_parent_id_not_given(registry, cfg):
    ctx = make_academy_ctx(registry, cfg)
    assert create(ctx, [], parent_id="").reason == "не указан parent_id"


def test_missing_parent_signal_has_exact_text(registry, cfg):
    ctx = make_academy_ctx(registry, cfg)
    signal = create(ctx, [], parent_id="").signal_to_master
    assert signal == (
        "Локация не создана: укажи parent_id — здание, двор, город или область из "
        "locations/known_locations. Опиши место иначе или повтори с родителем."
    )


def test_name_and_id_conflicts_are_joined_with_semicolon_in_reason_and_signal(registry, cfg):
    ctx = make_academy_ctx(registry, cfg)
    d = create(ctx, [], id="vale_tavern", name="Таверна")
    assert d.status == "rejected"
    assert d.reason.count("; ") == 1
    assert "'vale_tavern' уже занят" in d.reason
    assert "уже у локации" in d.reason
    assert d.signal_to_master.count("; ") == 1


def test_conflict_signal_has_prefix_and_hint(registry, cfg):
    ctx = make_academy_ctx(registry, cfg)
    signal = create(ctx, [], name="Таверна").signal_to_master
    assert signal.startswith("Локация не создана: ")
    assert signal.endswith(
        ". Место то же — используй существующий id, иначе придумай другое имя и id."
    )


def test_negative_distance_is_still_invalid(registry, cfg):
    ctx = make_academy_ctx(registry, cfg)
    d = create(ctx, [link("hall", -1)])
    assert isinstance(d, Invalid)
    assert d.code == "bad_amount"
