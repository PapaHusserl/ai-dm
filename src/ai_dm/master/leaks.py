import json
import re

# строка списка с маркером: -, —, •, *, 1. / 1)
MARKED_LINE = re.compile(r"^\s*(?:[-—•*]|\d+[.)])\s")

# прежняя вторая фраза описания offer_choices, которую модель порой выдаёт в рассказ
LEAK_LINE = "Вызывай в последнем ответе, после результатов механики и текста сцены."

HTML_TAG = re.compile(r"</?(?:p|strong|em|b|i|br)\s*/?>")
# JSON вызова offer_choices в тексте: { "offer_choices": ...} и { "type": "offer_choices", ...}
JSON_ANCHOR = re.compile(r'\{\s*"(?:type"\s*:\s*"offer_choices"|offer_choices"\s*:)')
# строка с одним именем инструмента (в бэктиках, жирном, с двоеточием)
NAME_LINE = re.compile(r"^[^\w\n]*offer_choices[^\w\n]*$\n?", re.M)
ARRAY_HEAD = re.compile(r"[ \t]*-[ \t]*(?=\[)")
BLANK_RUN = re.compile(r"\n[ \t]*\n(?:[ \t]*\n)+")
HINT_START = "Подсказка по результатам"
HINT_END = "---"


def choice_list(value):
    # варианты принимаются только списком из двух-трёх строк
    if isinstance(value, list) and 2 <= len(value) <= 3 and all(isinstance(v, str) for v in value):
        return value
    return None


def cut_hints(text):
    # самоинструкция модели: абзац «Подсказка по результатам…» и всё до разделителя «---»
    paragraphs = text.split("\n\n")
    kept = []
    i = 0
    while i < len(paragraphs):
        first = paragraphs[i].strip().split("\n")[0].lstrip("*# ")
        if not first.startswith(HINT_START):
            kept.append(paragraphs[i])
            i += 1
            continue
        end = next(
            (k for k in range(i + 1, len(paragraphs)) if paragraphs[k].strip() == HINT_END), None
        )
        i = i + 1 if end is None else end + 1
    return "\n\n".join(kept)


def cut_json(text):
    # JSON вызова offer_choices -> (текст, варианты | None); оборванный режется до конца
    choices = None
    while True:
        found = JSON_ANCHOR.search(text)
        if found is None:
            return text, choices
        try:
            obj, end = json.JSONDecoder().raw_decode(text, found.start())
        except ValueError:
            return text[: found.start()], choices
        if choices is None:
            choices = choice_list(obj.get("choices") or obj.get("offer_choices"))
        text = text[: found.start()] + text[end:]


def cut_name_lines(text):
    # строка «offer_choices» и следующий за ней блок: массив «- [...]» или маркированные строки
    choices = None
    while True:
        found = NAME_LINE.search(text)
        if found is None:
            return text, choices
        tail = text[found.end():]
        head = ARRAY_HEAD.match(tail)
        rest = tail
        if head is not None:
            try:
                value, end = json.JSONDecoder().raw_decode(tail, head.end())
            except ValueError:
                value, end = None, len(tail)
            if choices is None:
                choices = choice_list(value)
            rest = tail[end:]
        else:
            lines = tail.split("\n")
            count = 0
            while count < len(lines) and MARKED_LINE.match(lines[count]):
                count += 1
            rest = "\n".join(lines[count:])
        text = text[: found.start()] + rest


def cut_tail_list(text):
    # хвостовой блок из маркированных строк (не меньше двух) после последнего пустого перехода
    lines = text.rstrip().split("\n")
    start = len(lines)
    while start > 0 and lines[start - 1].strip():
        start -= 1
    block = lines[start:]
    if len(block) < 2 or not all(MARKED_LINE.match(line) for line in block):
        return text
    return "\n".join(lines[:start])


def cut_leaks(text, choices_taken=False):
    """Служебный текст в рассказе -> (чистый текст, варианты из утёкшего JSON | None).

    Режет JSON offer_choices, строку «offer_choices» с блоком под ней, самоинструкцию
    «Подсказка по результатам», HTML-теги абзацев и (при choices_taken) хвостовой список.
    """
    cleaned = HTML_TAG.sub("", text).replace(LEAK_LINE, "")
    cleaned = cut_hints(cleaned)
    cleaned, choices = cut_json(cleaned)
    cleaned, named = cut_name_lines(cleaned)
    if choices is None:
        choices = named
    if choices_taken:
        cleaned = cut_tail_list(cleaned)
    if cleaned == text:
        return text, None
    return BLANK_RUN.sub("\n\n", cleaned).strip(), choices
