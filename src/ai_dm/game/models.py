import json
import os

from ai_dm.llm.errors import MissingKey


def model_options(app_cfg, current=None):
    # модели рассказчика для меню выбора: roles, alternatives и цепочка, без повторов; профили
    # в меню не идут: модель профиля там, только если её ключ стоит в llm.narrator_chain;
    # current -- ключ текущей модели: следующая после неё по цепочке идёт первой
    roles = [app_cfg.roles.narrator, app_cfg.alternatives.narrator]
    options = []
    for role in roles:
        key = f"{role.provider}:{role.model}"
        if key not in options:
            options.append(key)
    for key in app_cfg.llm.narrator_chain:
        if key not in options:
            options.append(key)
    following = next_in_chain(app_cfg, current)
    if following in options:
        options.remove(following)
        options.insert(0, following)
    return options


def next_in_chain(app_cfg, current):
    # ключ модели, следующей за current в llm.narrator_chain; нет в цепочке или последняя -- None
    chain = app_cfg.llm.narrator_chain
    if current not in chain or current == chain[-1]:
        return None
    return chain[chain.index(current) + 1]


def check_model(app_cfg, adapter_factory, provider, model):
    # (адаптер, None) для годной модели или (None, текст ошибки): цена, окно и фабрика
    if model not in app_cfg.prices or model not in app_cfg.context_windows:
        return None, f"Для модели {model!r} нет цены или окна контекста в конфиге."
    try:
        return adapter_factory(provider, model), None
    except (MissingKey, ValueError) as error:
        return None, str(error)


def models_path(saves_root, world_id):
    return saves_root / world_id / "meta" / "models.json"


def read_models(saves_root, world_id):
    path = models_path(saves_root, world_id)
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_models(saves_root, world_id, provider, model):
    # запоминает модель рассказчика; битый models.json пишется заново
    try:
        stored = read_models(saves_root, world_id)
    except (ValueError, OSError):
        stored = {}
    stored["narrator"] = {"provider": provider, "model": model}
    path = models_path(saves_root, world_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(stored, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)
