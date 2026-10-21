from ai_dm.protocol.decision import Decision, Invalid

SENTENCE_END = ".!?…"
CLOSERS = "\"'»”)]"


def trim_text(text, limit) -> str:
    # обрезка до limit: по последней границе предложения, иначе по пробелу и «…»
    if len(text) <= limit:
        return text
    head = text[:limit]
    best = -1
    for i, ch in enumerate(head):
        if ch not in SENTENCE_END:
            continue
        end = i + 1
        while end < len(head) and head[end] in CLOSERS:
            end += 1
        # конец предложения: дальше пробел или конец текста
        if text[end].isspace():
            best = end
    if best >= limit // 2 and best > 0:
        return head[:best].rstrip()
    head = text[: limit - 1]
    space = head.rfind(" ")
    if space > 0:
        head = head[:space]
    return head.rstrip() + "…"


def fit_text(ctx, key, text, limit, label):
    if not text:
        return Invalid(code="empty_summary", message=f"{label} пустая: напиши, что произошло.")
    if len(text) <= limit:
        return text
    count = ctx.summary_overflows.get(key, 0) + 1
    ctx.summary_overflows[key] = count
    after = ctx.summary_trim_after
    if after > 0 and count > after:
        return trim_text(text, limit)
    if key == "scene" and after > 0:
        ctx.summary_pending = text
    ratio = len(text) / limit
    message = (
        f"{label} {len(text)} симв., предел {limit}: сократи примерно в {ratio:.1f} раза "
        f"— убери подробности, оставь факты, обещания и открытые нити."
    )
    if after > 0:
        message += (
            f" Попытка {count} из {after}. Вызови {key}_summary ещё раз короче; "
            f"если и она длиннее предела, движок примет её, обрезав по предложению."
        )
    return Invalid(code="summary_too_long", message=message)


def accepted(label, original, text) -> Decision:
    if len(text) == len(original):
        return Decision(status="accepted", log=[f"{label} принята"])
    return Decision(
        status="accepted", report_tag="summary_trimmed",
        log=[f"{label} принята с обрезкой {len(original)}→{len(text)} симв."],
    )


def scene_summary(ctx, request):
    # выжимка закрытой сцены: ровно один вызов, текст не пустой и не длиннее предела
    if ctx.summary_text is not None:
        return Invalid(code="already_done", message="Выжимка сцены уже принята.")
    original = request.summary.strip()
    text = fit_text(ctx, "scene", original, ctx.summary_max, "Выжимка")
    if isinstance(text, Invalid):
        return text
    ctx.summary_text = text
    ctx.summary_title = request.title or ""
    return accepted("Выжимка сцены", original, text)


def chapter_summary(ctx, request):
    # выжимка главы: текст не пустой и не длиннее предела (повтор перезаписывает)
    original = request.summary.strip()
    text = fit_text(ctx, "chapter", original, ctx.chapter_summary_max, "Выжимка главы")
    if isinstance(text, Invalid):
        return text
    ctx.chapter_text = text
    ctx.chapter_title_new = request.title or ""
    return accepted("Выжимка главы", original, text)


def game_summary(ctx, request):
    # новый game_summary целиком: текст не пустой и не длиннее предела
    original = request.summary.strip()
    text = fit_text(ctx, "game", original, ctx.game_summary_max, "Выжимка игры")
    if isinstance(text, Invalid):
        return text
    ctx.game_text = text
    return accepted("Выжимка игры", original, text)
