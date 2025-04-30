from typing import TypeVar, Any
from fundi import from_, FromType
from pydantic import BaseModel, TypeAdapter
from starlette.datastructures import Headers, QueryParams

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

def from_header(name: str, type_: type[Tt]) -> Tt:
    adapter = TypeAdapter(type_)
    def validator(headers: FromType[Headers]) -> Tt:
        return adapter.validate_python(headers.get(name))

    return from_(validator)


def from_cookie(name: str, type_: type[Tt]) -> Tt:
    adapter = TypeAdapter(type_)
    def validator(cookies: dict[str, str]) -> Tt:
        return adapter.validate_python(cookies.get(name))

    return from_(validator)

def from_query(name: str, type_: type[Tt]) -> Tt:
    adapter = TypeAdapter(type_)
    def validator(query_params: FromType[QueryParams]) -> Tt:
        return adapter.validate_python(query_params.get(name))

    return from_(validator)


def from_path(name: str, type_: type[Tt]) -> Tt:
    adapter = TypeAdapter(type_)
    def validator(path_params: dict[str, Any]) -> Tt:
        return adapter.validate_python(path_params.get(name))

    return from_(validator)
