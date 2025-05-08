from typing import TypeVar, Any
from pydantic import BaseModel, TypeAdapter
from fundi import from_, FromType, Parameter
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


def require_body(request_data: Any, param: FromType[Parameter]) -> Any:
    if isinstance(param.annotation, BaseModel):
        return param.annotation.model_validate(request_data)
    else:
        return TypeAdapter(param.annotation).validate_python(request_data)


def from_header(name: str = ..., type_: type[Tt] = ...) -> Tt:
    name = None if name is Ellipsis else name
    adapter = None if type_ is Ellipsis else TypeAdapter(type_)

    def validator(headers: FromType[Headers], param: FromType[Parameter]) -> Tt:
        nonlocal adapter, name

        if adapter is None:
            adapter = TypeAdapter(param.annotation)

        if name is None:
            name = param.name

        return adapter.validate_python(headers.get(name))

    return from_(validator)


def from_cookie(name: str, type_: type[Tt]) -> Tt:
    name = None if name is Ellipsis else name
    adapter = None if type_ is Ellipsis else TypeAdapter(type_)

    def validator(cookies: dict[str, str], param: FromType[Parameter]) -> Tt:
        nonlocal adapter, name

        if adapter is None:
            adapter = TypeAdapter(param.annotation)

        if name is None:
            name = param.name

        return adapter.validate_python(cookies.get(name))

    return from_(validator)


def from_query(name: str, type_: type[Tt]) -> Tt:
    name = None if name is Ellipsis else name
    adapter = None if type_ is Ellipsis else TypeAdapter(type_)

    def validator(query_params: FromType[QueryParams], param: FromType[Parameter]) -> Tt:
        nonlocal adapter, name

        if adapter is None:
            adapter = TypeAdapter(param.annotation)

        if name is None:
            name = param.name

        return adapter.validate_python(query_params.get(name))

    return from_(validator)


def from_path(name: str, type_: type[Tt]) -> Tt:
    name = None if name is Ellipsis else name
    adapter = None if type_ is Ellipsis else TypeAdapter(type_)

    def validator(path_params: dict[str, Any], param: FromType[Parameter]) -> Tt:
        nonlocal adapter, name

        if adapter is None:
            adapter = TypeAdapter(param.annotation)

        if name is None:
            name = param.name

        return adapter.validate_python(path_params.get(name))

    return from_(validator)
