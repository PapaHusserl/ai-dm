# Общие помощники тестов persistence. load_slot для слота старше текущей версии требует
# MigrationContext (цены предметов из реестра): здесь он подставляется, если не задан.
from ai_dm.content.loader import load_registry
from ai_dm.persistence.migrations import MigrationContext
from ai_dm.persistence.store import load_slot as store_load_slot


def srd_context():
    return MigrationContext.from_registry(load_registry())


def load_slot(*args, **kwargs):
    kwargs.setdefault("context", srd_context())
    return store_load_slot(*args, **kwargs)
