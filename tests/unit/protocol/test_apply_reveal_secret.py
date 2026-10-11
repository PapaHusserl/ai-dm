# Ожидаемый API: ai_dm.protocol.apply.apply -- reveal_secret (STAGE3-PLAN A10, П3).
# Открыт в explore с этапа 3. Через rules.secrets.reveal:
#   * условие FALSE -> Decision rejected («ещё рано»), signal_to_master непустой; это НЕ Invalid
#     (бюджет невалидных ответов не тратится), секрет не раскрыт;
#   * TRUE -> accepted, secret.revealed, id в npc.known_to_player, событие secret_revealed в
#     ctx.events;
#   * NEEDS_NARRATIVE без narrative_ok -> rejected; с narrative_ok=True -> раскрыт;
#   * неизвестный npc_id / secret_id -> Invalid, состояние не меняется.
from protocol_kit import dump, make_bundle, make_ctx, req

from ai_dm.protocol.apply import apply
from ai_dm.protocol.decision import Decision, Invalid
from ai_dm.state.triggers import Secret


def secret_ctx(registry, cfg, reveal_if, narrative_ok=False):
    bundle = make_bundle(registry)
    bundle.world.npcs["aldric"].secrets.append(
        Secret.model_validate(
            {"id": "sister", "text": "сестра в беде", "reveal_if": reveal_if,
             "narrative_ok": narrative_ok}
        )
    )
    return make_ctx(registry, cfg, bundle=bundle)


def reveal(ctx, npc_id="aldric", secret_id="sister"):
    return apply(ctx, req("reveal_secret", npc_id=npc_id, secret_id=secret_id))


def secret_of(ctx):
    return ctx.bundle.world.npcs["aldric"].secrets[0]


def test_reveal_secret_false_condition_is_rejected_too_early(registry, cfg):
    ctx = secret_ctx(registry, cfg, {"flag": "found"})
    d = reveal(ctx)
    assert isinstance(d, Decision)
    assert d.status == "rejected"
    assert d.signal_to_master


def test_reveal_secret_false_condition_changes_nothing(registry, cfg):
    ctx = secret_ctx(registry, cfg, {"flag": "found"})
    before = dump(ctx)
    reveal(ctx)
    assert dump(ctx) == before
    assert ctx.events == []


def test_reveal_secret_true_condition_reveals(registry, cfg):
    ctx = secret_ctx(registry, cfg, {"flag": "found"})
    ctx.bundle.world.flags["found"] = True
    d = reveal(ctx)
    assert isinstance(d, Decision)
    assert d.status == "accepted"
    assert secret_of(ctx).revealed is True


def test_reveal_secret_true_condition_adds_known_to_player(registry, cfg):
    ctx = secret_ctx(registry, cfg, {"flag": "found"})
    ctx.bundle.world.flags["found"] = True
    reveal(ctx)
    assert ctx.bundle.world.npcs["aldric"].known_to_player == ["sister"]


def test_reveal_secret_true_condition_emits_event(registry, cfg):
    ctx = secret_ctx(registry, cfg, {"flag": "found"})
    ctx.bundle.world.flags["found"] = True
    reveal(ctx)
    assert [e.type for e in ctx.events] == ["secret_revealed"]
    assert ctx.events[0].data == {"npc": "aldric", "secret": "sister"}


def test_reveal_secret_narrative_without_ok_is_rejected(registry, cfg):
    ctx = secret_ctx(registry, cfg, {"narrative": "герой завоевал доверие"})
    d = reveal(ctx)
    assert isinstance(d, Decision)
    assert d.status == "rejected"
    assert secret_of(ctx).revealed is False


def test_reveal_secret_narrative_with_narrative_ok_reveals(registry, cfg):
    ctx = secret_ctx(registry, cfg, {"narrative": "герой завоевал доверие"}, narrative_ok=True)
    d = reveal(ctx)
    assert d.status == "accepted"
    assert secret_of(ctx).revealed is True


def test_reveal_secret_mixed_condition_with_false_structure_is_rejected_even_if_ok(registry, cfg):
    cond = {"all": [{"flag": "found"}, {"narrative": "герой завоевал доверие"}]}
    ctx = secret_ctx(registry, cfg, cond, narrative_ok=True)
    d = reveal(ctx)
    assert d.status == "rejected"
    assert secret_of(ctx).revealed is False


def test_reveal_secret_unknown_npc_is_invalid(registry, cfg):
    ctx = secret_ctx(registry, cfg, {"flag": "found"})
    before = dump(ctx)
    d = reveal(ctx, npc_id="nobody")
    assert isinstance(d, Invalid)
    assert dump(ctx) == before


def test_reveal_secret_unknown_secret_is_invalid(registry, cfg):
    ctx = secret_ctx(registry, cfg, {"flag": "found"})
    before = dump(ctx)
    d = reveal(ctx, secret_id="nothing")
    assert isinstance(d, Invalid)
    assert dump(ctx) == before
