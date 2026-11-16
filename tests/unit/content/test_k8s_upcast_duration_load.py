# К8с П2: срок в upcast.duration_by_circle проверяется при загрузке, а не при касте.
import pytest
from pydantic import ValidationError

from ai_dm.content.models.spells import Upcast


def test_valid_durations_load():
    upcast = Upcast(duration_by_circle={3: "8h", 5: "24h"})
    assert upcast.duration_by_circle == {3: "8h", 5: "24h"}


@pytest.mark.parametrize("bad", ["8 hours", "8", "h8", ""])
def test_typo_in_a_duration_fails_the_load(bad):
    with pytest.raises(ValidationError):
        Upcast(duration_by_circle={3: bad})


def test_upcast_without_a_table_loads():
    assert Upcast().duration_by_circle is None
