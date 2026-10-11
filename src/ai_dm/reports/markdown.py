import json

STATUS_NAMES = {
    "committed": "принят",
    "aborted": "откатан",
    "none": "ходов в сессии ещё не было",
}


def title(capture, text) -> str:
    if text:
        return "ручной"
    return ", ".join(capture.tags)


def turn_lines(capture) -> list[str]:
    if capture.status == "none":
        return ["## Ход", "", f"Статус: {STATUS_NAMES['none']}"]
    lines = [
        "## Ход",
        "",
        f"Номер хода: {capture.turn_seq}",
        f"Статус: {STATUS_NAMES[capture.status]}",
    ]
    if capture.failure_reason:
        lines.append(f"Причина сбоя: {capture.failure_reason}")
    if capture.player_input is not None:
        lines.append(f"Фраза игрока: {capture.player_input}")
    if capture.run_ids:
        lines.append(f"Вызовы хода (run_id): {', '.join(capture.run_ids)}")
    return lines


def block_text(block) -> str:
    if block["type"] == "text":
        return block["text"]
    if block["type"] == "tool_call":
        return f"вызов {block['name']}: {json.dumps(block['input'], ensure_ascii=False)}"
    if block["type"] == "tool_result":
        return f"результат: {block['content']}"
    return f"(служебный блок {block['provider']})"


def fence(text) -> str:
    # ограда длиннее любой серии ` в тексте, иначе текст закроет блок раньше времени
    longest = 0
    run = 0
    for char in text:
        run = run + 1 if char == "`" else 0
        longest = max(longest, run)
    return "`" * max(3, longest + 1)


def message_lines(message) -> list[str]:
    lines = [f"- {message['role']}:"]
    for block in message["content"]:
        text = block_text(block)
        bar = fence(text)
        lines += ["", f"  {bar}", text, f"  {bar}"]
    return lines


def stop_detail_text(record) -> str:
    detail = (record["response"] or {}).get("stop_detail")
    return "" if detail is None else f" ({detail})"


def call_lines(record) -> list[str]:
    request = record["request"]
    lines = [
        f"### Вызов {record['call_id']}: {record['role']}, попытка {record['attempt']}",
        "",
        f"- run_id: {record['run_id']}",
        f"- модель: {record['model']} (запрошена {record['requested_model']})",
        f"- stop_reason: {record['stop_reason']}{stop_detail_text(record)}",
        f"- статус хода: {record['turn_status']}",
        f"- system: journal/blobs/{request['system_sha256']}.json",
        f"- tools: journal/blobs/{request['tools_sha256']}.json",
    ]
    if record["error"] is not None:
        lines.append(f"- ошибка: {record['error']['kind']}")
    lines += ["", "Запрос:", ""]
    for message in request["messages"]:
        lines += message_lines(message)
    if record["response"] is not None:
        lines += ["", "Ответ:", ""]
        for block in record["response"]["content"]:
            text = block_text(block)
            bar = fence(text)
            lines += [f"  {bar}", text, f"  {bar}"]
    return lines + [""]


def models_lines(calls) -> list[str]:
    seen = []
    for record in calls:
        line = f"{record['role']}: {record['model']} (запрошена {record['requested_model']})"
        if line not in seen:
            seen.append(line)
    return [f"Модель вызова, {line}" for line in seen]


def calls_lines(calls) -> list[str]:
    if calls is None:
        return ["## Вызовы модели", "", "Журнал отключён, воспроизведение невозможно.", ""]
    lines = ["## Вызовы модели хода", ""]
    if not calls:
        lines += ["Вызовов модели в ходе не было.", ""]
    for record in calls:
        lines += call_lines(record)
    return lines


def recent_lines(capture, recent_turns) -> list[str]:
    bundle = capture.after or capture.before
    turns = bundle.memory.recent_turns
    shown = turns[-recent_turns:]
    lines = ["## Последние ходы", "", f"Показано ходов: {len(shown)} (запрошено {recent_turns})."]
    if len(shown) < recent_turns:
        lines.append("В памяти игры хранится меньше ходов, чем запрошено.")
    for turn in shown:
        lines += ["", f"### Ход {turn.turn_seq}", "", f"Фраза игрока: {turn.player_input}"]
        lines += ["", turn.narration]
        if turn.rolls:
            lines += ["", "Броски:"] + [f"- {roll}" for roll in turn.rolls]
    return lines + [""]


def render(capture, text, calls=None, recent_turns=5) -> str:
    world = capture.before.world
    rng = world.rng
    lines = [f"# Репорт: {title(capture, text)}", ""]
    if text:
        lines += ["## Текст игрока", "", text, ""]
    if capture.tags:
        lines += [f"Метки хода: {', '.join(capture.tags)}", ""]
    lines += turn_lines(capture)
    lines += [
        "",
        "## Мир",
        "",
        f"Мир: {world.world_id}",
        f"Кампания: {world.campaign_id}",
        f"Время репорта: {capture.now_iso}",
        f"Модель рассказчика: {capture.model}",
        f"Сид: {rng.seed}",
        f"Состояние RNG до хода: algo={rng.algo} state={rng.state} inc={rng.inc} draws={rng.draws}",
        *models_lines(calls or []),
        "",
    ]
    lines += recent_lines(capture, recent_turns)
    lines += calls_lines(calls)
    return "\n".join(lines)
