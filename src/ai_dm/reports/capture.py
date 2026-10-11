from dataclasses import dataclass


@dataclass
class TurnCapture:
    # что снято с хода для репорта: before -- бандл до хода, after -- после (None у откатанного)
    # before и after -- копии на момент хода; у пустого снимка (none) before -- живой бандл
    turn_seq: int
    run_ids: list
    player_input: str | None
    tags: list
    # committed | aborted | none (ходов в сессии ещё не было)
    status: str
    failure_reason: str | None
    before: object
    after: object | None
    now_iso: str
    model: str
