from fundi import from_
from typing import TypeVar, Any
from pydantic import BaseModel, TypeAdapter

Tm = TypeVar("Tm", bound=BaseModel)
Tt = TypeVar("Tt")


def from_model(model: type[Tm]) -> Tm:
    def validator(request_data: Any) -> Tm:
        return model.model_validate(request_data)

    return from_(validator)


def from_adapter(adapter: TypeAdapter[Tt]) -> Tt:
    def validator(request_data: Any) -> Tt:
        return adapter.validate_python(request_data)

    return from_(validator)

