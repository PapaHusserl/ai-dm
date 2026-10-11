# Ожидаемый API: ai_dm.core.events (доменные события, D3)
#   DomainEvent(BaseModel): type: str, data: dict[str, int | str | bool | None]
#       extra="forbid": лишние поля -> ValidationError; type и data обязательны;
#       значения data -- только int / str / bool / None (список, вложенный dict -> ValidationError)
import pytest
from pydantic import ValidationError

from ai_dm.core.events import DomainEvent


def test_event_keeps_type_and_data():
    event = DomainEvent(type="hero_died", data={"id": "h1", "cause": "goal", "by": None})
    assert event.type == "hero_died"
    assert event.data == {"id": "h1", "cause": "goal", "by": None}


def test_event_accepts_int_str_bool_and_none_values():
    data = {"a": 1, "b": "x", "c": True, "d": None}
    assert DomainEvent(type="t", data=data).data == data


def test_event_requires_type():
    with pytest.raises(ValidationError):
        DomainEvent(data={})


def test_event_requires_data():
    with pytest.raises(ValidationError):
        DomainEvent(type="t")


def test_event_forbids_extra_fields():
    with pytest.raises(ValidationError):
        DomainEvent(type="t", data={}, extra=1)


def test_event_data_rejects_list_value():
    with pytest.raises(ValidationError):
        DomainEvent(type="t", data={"a": [1, 2]})


def test_event_data_rejects_nested_dict_value():
    with pytest.raises(ValidationError):
        DomainEvent(type="t", data={"a": {"b": 1}})


def test_events_with_same_content_are_equal():
    a = DomainEvent(type="t", data={"id": "x"})
    b = DomainEvent(type="t", data={"id": "x"})
    assert a == b
