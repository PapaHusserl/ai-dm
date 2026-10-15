# 19ф Ф2а, добивка мутантов: tag_missing_combat не ставит тег, если start_combat принят в ходу
# (даже когда боя в бандле уже нет -- он мог закончиться в этом же ходу).
from types import SimpleNamespace

from master_kit import make_ctx, make_session, scripted

ANNOUNCE = "Гоблин выхватывает нож.\n\n*(В этот момент начинается бой!)*"


def tags_after(registry, cfg, tmp_path, accepted):
    session, _, _, _ = make_session(scripted([]), tmp_path)
    ctx = make_ctx(registry, cfg, mode="explore")
    result = SimpleNamespace(narration=ANNOUNCE, accepted=list(accepted), report_tags=[])
    session.tag_missing_combat(ctx, result, "explore")
    return result.report_tags


def test_tag_set_when_nothing_accepted(registry, cfg, tmp_path):
    assert tags_after(registry, cfg, tmp_path, []) == ["combat_announced"]


def test_no_tag_when_start_combat_accepted_even_without_active_combat(registry, cfg, tmp_path):
    assert tags_after(registry, cfg, tmp_path, ["start_combat"]) == []
