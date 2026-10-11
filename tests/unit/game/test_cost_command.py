# Этап 5, P4 (STAGE5-PLAN, «P4», Q5): /cost -- строки роль × модель + итог для сессии, дня и мира.
# Ожидаемый API (допущения):
#   CostReport.<session|day|world>.by_role_model -- dict {(роль, модель): нано-доллары};
#   текст /cost: заголовки «Сессия…», «День…», «Мир…» (как раньше), под каждым -- строки, где в
#   ОДНОЙ строке и роль, и модель, и сумма в долларах ($X.XXXX, допустимо больше знаков).
# Журнал -- реальный CostLedger на tmp_path, без сети.
from datetime import timedelta

from game_kit import NOW, OPUS, SONNET, ReactiveAdapter, make_app

from ai_dm.game.commands import TOTAL
from ai_dm.llm.cost import CostLedger
from ai_dm.llm.types import Usage

TODAY = NOW.astimezone().date()
YESTERDAY = TODAY - timedelta(days=1)


def text_of(reply):
    return "\n".join(reply.lines)


def add(ledger, call_id, role, model, nano, day=TODAY):
    ledger.add(
        call_id=call_id, role=role, model=model, usage=Usage(input=1, output=1),
        cost_nano=nano, day=day,
    )


def fixture_app(registry, tmp_path):
    # сессия: narrator/OPUS ×2, world/SONNET (нечётные нано), summarizer/SONNET
    # мир (не сессия): вчерашний narrator/SONNET; другой мир, сегодня: world/OPUS
    app = make_app(registry, tmp_path, ReactiveAdapter())
    add(app.ledger, "s-1", "narrator", OPUS, 1_111_111_111)
    add(app.ledger, "s-2", "narrator", OPUS, 222_222_222)
    add(app.ledger, "s-3", "world", SONNET, 7)
    add(app.ledger, "s-4", "summarizer", SONNET, 3_000_000_001)
    add(CostLedger(tmp_path, "w1"), "w-1", "narrator", SONNET, 500_000_000, day=YESTERDAY)
    add(CostLedger(tmp_path, "other-world"), "o-1", "world", OPUS, 5_000_000_000)
    return app


def sections(text):
    # {"Сессия": [итог, строки…], ...}; в тексте итог («Сессия: $…») -- ПОСЛЕДНЯЯ строка периода,
    # как в cost_rows; другой порядок роняет тест
    lines = text.splitlines()
    ends = [i for i, line in enumerate(lines) if line.startswith(("Сессия", "День", "Мир"))]
    assert ends[-1:] == [len(lines) - 1]
    result, start = {}, 0
    for end in ends:
        result[lines[end].split(":")[0]] = [lines[end]] + lines[start:end]
        start = end + 1
    return result


def row(lines, role, model):
    found = [line for line in lines if role in line and model in line]
    assert len(found) == 1
    return found[0]


def test_by_role_model_has_nano_exact_cells(registry, tmp_path):
    app = fixture_app(registry, tmp_path)
    report = app.ledger.report(TODAY)
    assert report.session.by_role_model == {
        ("narrator", OPUS): 1_333_333_333,
        ("world", SONNET): 7,
        ("summarizer", SONNET): 3_000_000_001,
    }
    assert report.world.by_role_model[("narrator", SONNET)] == 500_000_000
    assert report.day.by_role_model[("world", OPUS)] == 5_000_000_000


def test_by_role_model_cells_sum_to_total_to_the_nano(registry, tmp_path):
    report = fixture_app(registry, tmp_path).ledger.report(TODAY)
    for totals in (report.session, report.day, report.world):
        assert sum(totals.by_role_model.values()) == totals.total_nano
    assert report.session.total_nano == 4_333_333_341
    assert report.day.total_nano == 9_333_333_341
    assert report.world.total_nano == 4_833_333_341


def test_cost_has_three_sections_with_totals(registry, tmp_path):
    app = fixture_app(registry, tmp_path)
    parts = sections(text_of(app.handle("/cost")))
    assert list(parts) == ["Сессия", "День", "Мир"]
    assert "$4.3333" in parts["Сессия"][0]
    assert "$9.3333" in parts["День"][0]
    assert "$4.8333" in parts["Мир"][0]


def test_cost_session_rows_are_role_by_model(registry, tmp_path):
    app = fixture_app(registry, tmp_path)
    lines = sections(text_of(app.handle("/cost")))["Сессия"][1:]
    assert "$1.3333" in row(lines, "narrator", OPUS)
    assert "$0.0000" in row(lines, "world", SONNET)
    assert "$3.0000" in row(lines, "summarizer", SONNET)
    assert not any("narrator" in line and SONNET in line for line in lines)


def test_cost_day_rows_include_other_worlds_and_skip_old_days(registry, tmp_path):
    app = fixture_app(registry, tmp_path)
    lines = sections(text_of(app.handle("/cost")))["День"][1:]
    assert "$5.0000" in row(lines, "world", OPUS)
    assert not any("narrator" in line and SONNET in line for line in lines)


def test_cost_world_rows_include_earlier_sessions_not_other_worlds(registry, tmp_path):
    app = fixture_app(registry, tmp_path)
    lines = sections(text_of(app.handle("/cost")))["Мир"][1:]
    assert "$0.5000" in row(lines, "narrator", SONNET)
    assert "$1.3333" in row(lines, "narrator", OPUS)
    assert not any("world" in line and OPUS in line for line in lines)


def test_cost_with_empty_journal_shows_zero_totals(registry, tmp_path):
    app = make_app(registry, tmp_path, ReactiveAdapter())
    parts = sections(text_of(app.handle("/cost")))
    assert list(parts) == ["Сессия", "День", "Мир"]
    for lines in parts.values():
        assert "$0.0000" in lines[0]
        assert len(lines) == 1


# cost_rows: плоская таблица (период, роль, модель, нано)

def test_cost_rows_order_and_total_rows(registry, tmp_path):
    from ai_dm.game.commands import cost_rows

    rows = cost_rows(fixture_app(registry, tmp_path).ledger.report(TODAY))
    assert [row[0] for row in rows] == ["Сессия"] * 4 + ["День"] * 5 + ["Мир"] * 5
    session = rows[:4]
    assert session[:3] == [
        ("Сессия", "narrator", OPUS, 1_333_333_333),
        ("Сессия", "summarizer", SONNET, 3_000_000_001),
        ("Сессия", "world", SONNET, 7),
    ]
    assert session[3] == ("Сессия", TOTAL, "", 4_333_333_341)
    assert rows[8] == ("День", TOTAL, "", 9_333_333_341)
    assert rows[13] == ("Мир", TOTAL, "", 4_833_333_341)


def test_cost_rows_cells_sum_to_each_total(registry, tmp_path):
    from ai_dm.game.commands import cost_rows

    rows = cost_rows(fixture_app(registry, tmp_path).ledger.report(TODAY))
    for period in ("Сессия", "День", "Мир"):
        own = [row for row in rows if row[0] == period]
        assert sum(row[3] for row in own[:-1]) == own[-1][3]


def test_cost_rows_empty_journal_has_only_totals(registry, tmp_path):
    from ai_dm.game.commands import cost_rows

    app = make_app(registry, tmp_path, ReactiveAdapter())
    assert cost_rows(app.ledger.report(TODAY)) == [
        ("Сессия", TOTAL, "", 0), ("День", TOTAL, "", 0), ("Мир", TOTAL, "", 0),
    ]
