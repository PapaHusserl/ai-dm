class ContentRegistry:
    def __init__(self, items):
        # items: {вид: {id: модель}}
        self._items = items
        # последний реестр с сюжетными предметами мира, собранный от этого: ключ каталога и реестр
        self.overlay_key = None
        self.overlay = None

    def get(self, kind, id):
        return self._items[kind][id]

    def has(self, kind, id):
        return id in self._items.get(kind, {})

    def ids(self, kind):
        return sorted(self._items[kind])

    def all(self, kind):
        return [self._items[kind][id] for id in self.ids(kind)]

    def with_items(self, extra):
        # новый реестр: копия текущего + extra {вид: [модели]}, исходный не меняется
        items = {kind: dict(content) for kind, content in self._items.items()}
        for kind, models in extra.items():
            for model in models:
                items.setdefault(kind, {})[model.id] = model
        return ContentRegistry(items)

    def subclasses_of(self, class_id):
        return [s for s in self.all("subclass") if s.class_id == class_id]
