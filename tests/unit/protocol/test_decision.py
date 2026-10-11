# Ожидаемый API: ai_dm.protocol.decision -- см. контракт в protocol_kit.py.
#   Decision(status, reason="", signal_to_master=None, report_tag=None, result={}, log=[])
#   Invalid(code, message). Pydantic, extra="forbid".
import pytest
from pydantic import ValidationError

from ai_dm.protocol.decision import Decision, Invalid


def test_decision_minimal_accepted():
    d = Decision(status="accepted")
    assert d.reason == ""
    assert d.signal_to_master is None
    assert d.report_tag is None
    assert d.result == {}
    assert d.log == []


@pytest.mark.parametrize("status", ["accepted", "clamped", "rejected"])
def test_decision_statuses(status):
    assert Decision(status=status).status == status


def test_decision_unknown_status_is_error():
    with pytest.raises(ValidationError):
        Decision(status="maybe")


def test_decision_status_is_required():
    with pytest.raises(ValidationError):
        Decision()


def test_decision_forbids_extra():
    with pytest.raises(ValidationError):
        Decision(status="accepted", bogus=1)


def test_decision_defaults_are_not_shared():
    a = Decision(status="accepted")
    b = Decision(status="accepted")
    a.log.append("x")
    a.result["k"] = 1
    assert b.log == [] and b.result == {}


def test_decision_json_roundtrip():
    d = Decision(
        status="clamped", reason="урезано", signal_to_master="опиши иначе",
        report_tag="limit-exceeded", result={"qty": 20}, log=["строка"],
    )
    assert Decision.model_validate_json(d.model_dump_json()) == d


def test_invalid_has_code_and_message():
    inv = Invalid(code="unknown_item", message="нет такого предмета")
    assert inv.code == "unknown_item"
    assert inv.message == "нет такого предмета"


def test_invalid_requires_code_and_message():
    with pytest.raises(ValidationError):
        Invalid(code="x")
    with pytest.raises(ValidationError):
        Invalid(message="x")


def test_invalid_forbids_extra():
    with pytest.raises(ValidationError):
        Invalid(code="x", message="y", bogus=1)


def test_invalid_is_not_a_decision():
    assert not isinstance(Invalid(code="x", message="y"), Decision)
