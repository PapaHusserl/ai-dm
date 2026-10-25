# Спутники героя (stage3-live-followers, F1, F2): NPC.follows -- id героя или None.
#   advance_time(travel_to=...) переносит и всех NPC с follows == id героя; прочих не трогает;
#   лог «С тобой: <имена>»; npc_update(follows="hero"|"none"|"") ставит / снимает / не меняет;
#   смерть и уход снимают follows.
from protocol_kit import ScriptedRng, make_ctx, req

from ai_dm.protocol.apply import apply
from ai_dm.state.world import NPC


def add_follower(ctx, npc_id, name, follows="hero", location_id="vale"):
    npc = NPC(
        id=npc_id, name=name, named=True, means=["m"], location_id=location_id,
        follows=ctx.hero.id if follows == "hero" else follows,
    )
    ctx.bundle.world.npcs[npc_id] = npc
    return npc


def travel(ctx):
    return apply(ctx, req("advance_time", travel_to="forest"))


def npc(ctx, npc_id):
    return ctx.bundle.world.npcs[npc_id]


def test_follower_travels_with_the_hero(registry, cfg):
    ctx = make_ctx(registry, cfg)
    add_follower(ctx, "bran", "Бран")
    travel(ctx)
    assert npc(ctx, "bran").location_id == "forest"


def test_follower_without_location_travels_too(registry, cfg):
    ctx = make_ctx(registry, cfg)
    add_follower(ctx, "bran", "Бран", location_id=None)
    travel(ctx)
    assert npc(ctx, "bran").location_id == "forest"


def test_not_follower_stays_in_place(registry, cfg):
    ctx = make_ctx(registry, cfg)
    add_follower(ctx, "farmer", "Фермер", follows=None)
    travel(ctx)
    assert npc(ctx, "farmer").location_id == "vale"


def test_key_npc_in_the_same_place_stays_if_not_following(registry, cfg):
    ctx = make_ctx(registry, cfg)
    travel(ctx)
    assert npc(ctx, "grakh").location_id == "vale"


def test_follower_of_another_hero_stays_in_place(registry, cfg):
    ctx = make_ctx(registry, cfg)
    add_follower(ctx, "squire", "Оруженосец", follows="other_hero")
    travel(ctx)
    assert npc(ctx, "squire").location_id == "vale"


def test_dead_follower_does_not_travel(registry, cfg):
    ctx = make_ctx(registry, cfg)
    add_follower(ctx, "bran", "Бран").status = "dead"
    travel(ctx)
    assert npc(ctx, "bran").location_id == "vale"


def test_travel_log_names_followers(registry, cfg):
    ctx = make_ctx(registry, cfg)
    add_follower(ctx, "bran", "Бран Седогрив")
    add_follower(ctx, "jorgen", "Йорген")
    d = travel(ctx)
    line = next(line for line in d.log if "С тобой:" in line)
    assert "Бран Седогрив" in line
    assert "Йорген" in line


def test_travel_log_has_no_companions_line_without_followers(registry, cfg):
    ctx = make_ctx(registry, cfg)
    d = travel(ctx)
    assert not [line for line in d.log if "С тобой:" in line]


def test_travel_log_does_not_name_stayers(registry, cfg):
    ctx = make_ctx(registry, cfg)
    add_follower(ctx, "bran", "Бран Седогрив")
    add_follower(ctx, "farmer", "Фермер", follows=None)
    d = travel(ctx)
    line = next(line for line in d.log if "С тобой:" in line)
    assert "Фермер" not in line


def test_advance_time_category_does_not_move_followers(registry, cfg):
    ctx = make_ctx(registry, cfg)
    add_follower(ctx, "bran", "Бран")
    apply(ctx, req("advance_time", category="hour"))
    assert npc(ctx, "bran").location_id == "vale"


# npc_update: follows

def test_npc_update_follows_hero_attaches_the_npc(registry, cfg):
    ctx = make_ctx(registry, cfg)
    d = apply(ctx, req("npc_update", npc_id="aldric", follows="hero"))
    assert d.status == "accepted"
    assert npc(ctx, "aldric").follows == ctx.hero.id


def test_attached_npc_then_travels(registry, cfg):
    ctx = make_ctx(registry, cfg)
    apply(ctx, req("npc_update", npc_id="aldric", follows="hero"))
    travel(ctx)
    assert npc(ctx, "aldric").location_id == "forest"


def test_npc_update_follows_none_detaches_the_npc(registry, cfg):
    ctx = make_ctx(registry, cfg)
    add_follower(ctx, "bran", "Бран")
    apply(ctx, req("npc_update", npc_id="bran", follows="none"))
    assert npc(ctx, "bran").follows is None
    travel(ctx)
    assert npc(ctx, "bran").location_id == "vale"


def test_npc_update_empty_follows_changes_nothing(registry, cfg):
    ctx = make_ctx(registry, cfg)
    add_follower(ctx, "bran", "Бран")
    apply(ctx, req("npc_update", npc_id="bran", attitude_delta=3, follows="keep"))
    assert npc(ctx, "bran").follows == ctx.hero.id


def test_npc_update_without_follows_field_keeps_it_off(registry, cfg):
    ctx = make_ctx(registry, cfg)
    apply(ctx, req("npc_update", npc_id="aldric", attitude_delta=3))
    assert npc(ctx, "aldric").follows is None


# смерть и уход снимают follows

def test_death_clears_follows(registry, cfg):
    ctx = make_ctx(registry, cfg, ScriptedRng(d20=[1]))
    add_follower(ctx, "bran", "Бран")
    ref = apply(ctx, req("skill_check", skill="athletics", category="easy")).result["roll_ref"]
    d = apply(
        ctx, req("npc_update", npc_id="bran", status="dead", cause="goal", evidence_ref=ref)
    )
    assert d.status == "accepted"
    assert npc(ctx, "bran").follows is None


def test_leaving_clears_follows(registry, cfg):
    ctx = make_ctx(registry, cfg, ScriptedRng(d20=[1]))
    add_follower(ctx, "bran", "Бран")
    ref = apply(ctx, req("skill_check", skill="athletics", category="easy")).result["roll_ref"]
    apply(ctx, req("npc_update", npc_id="bran", status="gone", cause="goal", evidence_ref=ref))
    assert npc(ctx, "bran").follows is None
