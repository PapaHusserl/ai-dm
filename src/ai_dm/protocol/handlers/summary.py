from ai_dm.protocol.decision import Decision, Invalid


def scene_summary(ctx, request):
    # выжимка закрытой сцены: ровно один вызов, текст не пустой и не длиннее предела
    if ctx.summary_text is not None:
        return Invalid(code="already_done", message="Выжимка сцены уже принята.")
    text = request.summary.strip()
    if not text:
        return Invalid(code="empty_summary", message="Выжимка пустая: напиши, что произошло.")
    if len(text) > ctx.summary_max:
        return Invalid(
            code="summary_too_long",
            message=f"Выжимка {len(text)} символов, предел {ctx.summary_max}: сократи.",
        )
    ctx.summary_text = text
    ctx.summary_title = request.title or ""
    return Decision(status="accepted", log=["Выжимка сцены принята"])


def chapter_summary(ctx, request):
    # выжимка главы: текст не пустой и не длиннее предела (повтор перезаписывает)
    text = request.summary.strip()
    if not text:
        return Invalid(code="empty_summary", message="Выжимка главы пустая: напиши, что произошло.")
    if len(text) > ctx.chapter_summary_max:
        return Invalid(
            code="summary_too_long",
            message=f"Выжимка главы {len(text)} симв., предел {ctx.chapter_summary_max}: сократи.",
        )
    ctx.chapter_text = text
    ctx.chapter_title_new = request.title or ""
    return Decision(status="accepted", log=["Выжимка главы принята"])


def game_summary(ctx, request):
    # новый game_summary целиком: текст не пустой и не длиннее предела
    text = request.summary.strip()
    if not text:
        return Invalid(code="empty_summary", message="game_summary пустой: напиши историю игры.")
    if len(text) > ctx.game_summary_max:
        return Invalid(
            code="summary_too_long",
            message=f"game_summary {len(text)} символов, предел {ctx.game_summary_max}: сократи.",
        )
    ctx.game_text = text
    return Decision(status="accepted", log=["game_summary принят"])
