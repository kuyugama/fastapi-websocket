import typing


class RequestType(typing.TypedDict):
    id: str
    type: typing.Literal["request"]
    endpoint: str
    data: typing.Any


def validate_request(body: typing.Any) -> RequestType | None:
    if not isinstance(body, dict):
        return None

    if not isinstance(body.get("id"), str):
        return None

    if body.get("type") != "request":
        return None

    if not isinstance(body.get("endpoint"), str):
        return None

    if "data" not in body:
        return None

    return typing.cast(
        RequestType,
        dict(id=body["id"], type=body["type"], endpoint=body["endpoint"], data=body["data"]),
    )


def create_event(kind: str, data: typing.Any):
    return {"type": "event", "kind": kind, "data": data}


def create_error_event(reason: str, code: str):
    return create_event("error", {"reason": reason, "code": code})


class SendEvent(typing.Protocol):
    @staticmethod
    async def __call__(kind: str, data: typing.Any):
        """Send event to websocket"""


class SendError(typing.Protocol):
    @staticmethod
    async def __call__(reason: str, code: str):
        """Send error event to websocket"""
