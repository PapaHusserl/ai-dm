# Ожидаемый API: ai_dm.rules.secrets (шаг 14, ТЗ 4 «Секреты NPC»)
#   check_reveal(secret: Secret, world: WorldState, hero: HeroState) -> Evaluation
#       то же, что evaluate(secret.reveal_if, world, hero) (Evaluation / Truth из triggers_eval)
#   reveal(npc: NPC, secret_id: str, world: WorldState, hero: HeroState,
#          narrative_confirmed: bool = False) -> list[DomainEvent] | Rejected
#       Rejected живёт в нейтральном rules.results (D10); из mortality_guard реэкспортируется.
#       неизвестный secret_id у этого NPC -> KeyError (как remove_creature с неизвестным id)
#       секрет уже раскрыт (revealed == True) -> no-op: [] без событий, состояние не меняется
#           (проверяется ДО условия: раскрытый секрет не «закрывается», даже если условие
#           с тех пор перестало выполняться)
#       условие TRUE -> secret.revealed = True, secret.id добавляется в npc.known_to_player
#           (без дублей), возвращается [DomainEvent(type="secret_revealed",
#           data={"npc": npc.id, "secret": secret.id})]
#       условие FALSE -> Rejected(reason="too_early", report_tag=None) -- сигнал мастеру
#           «ещё рано»; состояние не меняется
#       условие NEEDS_NARRATIVE (движок проверить не может) -> Rejected(reason="needs_narrative",
#           report_tag=None); состояние не меняется
#           narrative_confirmed=True при NEEDS_NARRATIVE -- мастер подтвердил нарратив:
#           секрет раскрывается как при TRUE (revealed, known_to_player, событие).
#           При FALSE флаг ничего не меняет: по-прежнему Rejected("too_early").
import pytest

from ai_dm.core.events import DomainEvent
from ai_dm.core.rng import Rng
from ai_dm.rules.results import Rejected
from ai_dm.rules.secrets import check_reveal, reveal
from ai_dm.rules.triggers_eval import Truth
from ai_dm.state.creature import CreatureState
from ai_dm.state.hero import BackgroundSpec, CharacterSheet, ClassLevel, HeroState
from ai_dm.state.triggers import Secret
from ai_dm.state.world import NPC, WorldState


def make_hero():
    sheet = CharacterSheet(
        species_id="human",
        classes=[ClassLevel(class_id="fighter")], level_history=["fighter"] * 1,
        background=BackgroundSpec(
            name="Солдат",
            abilities=["str", "dex", "con"],
            skills=["athletics", "intimidation"],
            tool="dice_set",
            feat="savage_attacker",
        ),
        abilities={"str": 17, "dex": 13, "con": 15, "int": 8, "wis": 10, "cha": 12},
    )
    return HeroState(
        id="h1", ordinal=1, name="Арн", sheet=sheet,
        creature=CreatureState(hp_current=12, hp_max=12),
    )


def make_world(reveal_if):
    world = WorldState(world_id="w1", rng=Rng(1).state)
    world.npcs["mentor_aldric"] = NPC(
        id="mentor_aldric", name="Олдрик", means=["магия крови"],
        secrets=[Secret(id="sister_vampire", text="сестра -- вампир", reveal_if=reveal_if)],
    )
    return world


def make_state(reveal_if=None, flags=None):
    world = make_world(reveal_if or {"flag": "found_diary"})
    world.flags.update(flags or {})
    return world, world.npcs["mentor_aldric"], make_hero()


def test_check_reveal_true_when_condition_met():
    world, npc, hero = make_state(flags={"found_diary": True})
    assert check_reveal(npc.secrets[0], world, hero).truth == Truth.TRUE


def test_check_reveal_false_when_condition_not_met():
    world, npc, hero = make_state()
    assert check_reveal(npc.secrets[0], world, hero).truth == Truth.FALSE


def test_check_reveal_needs_narrative_for_narrative_condition():
    world, npc, hero = make_state(reveal_if={"narrative": "герой читает дневник"})
    result = check_reveal(npc.secrets[0], world, hero)
    assert result.truth == Truth.NEEDS_NARRATIVE
    assert result.narrative == ["герой читает дневник"]


def test_check_reveal_does_not_change_state():
    world, npc, hero = make_state(flags={"found_diary": True})
    check_reveal(npc.secrets[0], world, hero)
    assert npc.secrets[0].revealed is False
    assert npc.known_to_player == []


def test_reveal_marks_secret_revealed_when_condition_met():
    world, npc, hero = make_state(flags={"found_diary": True})
    reveal(npc, "sister_vampire", world, hero)
    assert npc.secrets[0].revealed is True


def test_reveal_moves_secret_to_known_to_player():
    world, npc, hero = make_state(flags={"found_diary": True})
    reveal(npc, "sister_vampire", world, hero)
    assert npc.known_to_player == ["sister_vampire"]


def test_reveal_returns_secret_revealed_event():
    world, npc, hero = make_state(flags={"found_diary": True})
    events = reveal(npc, "sister_vampire", world, hero)
    data = {"npc": "mentor_aldric", "secret": "sister_vampire"}
    assert events == [DomainEvent(type="secret_revealed", data=data)]


def test_reveal_too_early_returns_rejected():
    world, npc, hero = make_state()
    result = reveal(npc, "sister_vampire", world, hero)
    assert isinstance(result, Rejected)
    assert result.reason == "too_early"
    assert result.report_tag is None


def test_reveal_too_early_does_not_change_state():
    world, npc, hero = make_state()
    reveal(npc, "sister_vampire", world, hero)
    assert npc.secrets[0].revealed is False
    assert npc.known_to_player == []


def test_reveal_narrative_condition_is_rejected_without_changes():
    world, npc, hero = make_state(reveal_if={"narrative": "герой читает дневник"})
    result = reveal(npc, "sister_vampire", world, hero)
    assert isinstance(result, Rejected)
    assert result.reason == "needs_narrative"
    assert npc.secrets[0].revealed is False
    assert npc.known_to_player == []


def test_reveal_twice_is_noop_without_events():
    world, npc, hero = make_state(flags={"found_diary": True})
    reveal(npc, "sister_vampire", world, hero)
    assert reveal(npc, "sister_vampire", world, hero) == []


def test_reveal_twice_does_not_duplicate_known_to_player():
    world, npc, hero = make_state(flags={"found_diary": True})
    reveal(npc, "sister_vampire", world, hero)
    reveal(npc, "sister_vampire", world, hero)
    assert npc.known_to_player == ["sister_vampire"]


def test_revealed_secret_stays_revealed_when_condition_stops_holding():
    world, npc, hero = make_state(flags={"found_diary": True})
    reveal(npc, "sister_vampire", world, hero)
    world.flags["found_diary"] = False
    assert reveal(npc, "sister_vampire", world, hero) == []
    assert npc.secrets[0].revealed is True


def test_reveal_unknown_secret_raises_key_error():
    world, npc, hero = make_state(flags={"found_diary": True})
    with pytest.raises(KeyError):
        reveal(npc, "no_such_secret", world, hero)


def test_reveal_only_touches_requested_secret():
    world, npc, hero = make_state(flags={"found_diary": True})
    npc.secrets.append(Secret(id="debt", text="долг", reveal_if={"flag": "found_diary"}))
    reveal(npc, "debt", world, hero)
    assert npc.secrets[0].revealed is False
    assert npc.secrets[1].revealed is True
    assert npc.known_to_player == ["debt"]


def test_reveal_narrative_confirmed_reveals_secret():
    world, npc, hero = make_state(reveal_if={"narrative": "герой читает дневник"})
    events = reveal(npc, "sister_vampire", world, hero, narrative_confirmed=True)
    data = {"npc": "mentor_aldric", "secret": "sister_vampire"}
    assert events == [DomainEvent(type="secret_revealed", data=data)]
    assert npc.secrets[0].revealed is True
    assert npc.known_to_player == ["sister_vampire"]


def test_reveal_narrative_not_confirmed_by_default_is_rejected():
    world, npc, hero = make_state(reveal_if={"narrative": "герой читает дневник"})
    result = reveal(npc, "sister_vampire", world, hero, narrative_confirmed=False)
    assert isinstance(result, Rejected)
    assert result.reason == "needs_narrative"


def test_reveal_narrative_confirmed_does_not_override_false_condition():
    world, npc, hero = make_state()
    result = reveal(npc, "sister_vampire", world, hero, narrative_confirmed=True)
    assert isinstance(result, Rejected)
    assert result.reason == "too_early"
    assert npc.secrets[0].revealed is False


def test_reveal_narrative_confirmed_in_mixed_condition_with_true_structure():
    data = {"all": [{"flag": "found_diary"}, {"narrative": "герой читает дневник"}]}
    world, npc, hero = make_state(reveal_if=data, flags={"found_diary": True})
    events = reveal(npc, "sister_vampire", world, hero, narrative_confirmed=True)
    data = {"npc": "mentor_aldric", "secret": "sister_vampire"}
    assert events == [DomainEvent(type="secret_revealed", data=data)]


def test_rejected_in_results_is_same_class_as_in_mortality_guard():
    from ai_dm.rules import mortality_guard, results

    assert mortality_guard.Rejected is results.Rejected


def test_rejected_from_results_has_expected_fields():
    rejected = Rejected(reason="too_early", report_tag=None)
    assert rejected.status == "rejected"
    assert rejected.reason == "too_early"
    assert rejected.report_tag is None
