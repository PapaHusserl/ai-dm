from ai_dm.ui.menu_rows import BACK_LABEL, MenuRow, option_row, short_label

# Подгруппа вариантов одного заклинания («Цветной шар ▸», решение 19): пункты с params["variant"]
# сворачиваются в одну строку; группа variants:<родитель>:<заклинание>:<круг>:<цель>, родитель --
# группа, из которой раскрыта подгруппа («Назад» ведёт в неё; пусто -- корень меню). Родитель --
# без двоеточий (parent_of берёт второй сегмент).
VARIANTS_GROUP = "variants:"


def group_of(option, parent):
    # группа вариантов пункта или None, если вариантов у заклинания нет
    if "variant" not in option.params:
        return None
    params = option.params
    return f"{VARIANTS_GROUP}{parent or ''}:{params['spell']}:{params['circle']}:{params['target']}"


def parent_of(group):
    # группа, куда ведёт «Назад» из раскрытой группы; None -- корень
    if group is None or not group.startswith(VARIANTS_GROUP):
        return None
    return group.split(":")[1] or None


def spell_rows(options, target, parent=None):
    # пункты заклинаний; варианты одного заклинания -- одна строка «<Имя> ▸»
    rows = []
    seen = set()
    for option in options:
        group = group_of(option, parent)
        if group is None:
            rows.append(option_row(option, "target", target))
        elif group not in seen:
            seen.add(group)
            rows.append(MenuRow(f"{option.params['title']} ▸", kind="expand", group=group, rank=3))
    return rows


def variant_rows(options, target, group):
    # внутри подгруппы -- «Назад» и пункт на значение: «огонь → гоблин»
    parent = parent_of(group)
    rows = []
    for option in options:
        if group_of(option, parent) != group:
            continue
        word, _, rest = option.label[len(option.params["title"]) + 2 :].partition(")")
        shown = option.model_copy(update={"label": word + rest})
        rows.append(option_row(option, "target", target, short_label(shown, target)))
    return [MenuRow(BACK_LABEL, kind="back", group=parent)] + rows
