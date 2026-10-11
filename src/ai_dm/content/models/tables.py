from pydantic import field_validator

from ai_dm.content.models.common import ContentObject


class Table(ContentObject):
    # ключ (уровень, категория, CR) -> значение
    rows: dict[str, int]

    @field_validator("rows", mode="before")
    @classmethod
    def keys_to_str(cls, value):
        if isinstance(value, dict):
            return {str(k): v for k, v in value.items()}
        return value
