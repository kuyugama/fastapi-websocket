import traceback
from typing import Callable, Any, TypeVar, TypedDict, Literal, cast

from fastapi import APIRouter
from fundi import CallableInfo, scan
from fastapi.encoders import jsonable_encoder
from starlette.websockets import WebSocket, WebSocketDisconnect

from . import util
from .error import BaseRequestError

Tc = TypeVar("Tc", bound=Callable)


class RequestType(TypedDict):
    id: str
    type: Literal["request"]
    endpoint: str
    data: Any


def validate_request(body: Any) -> RequestType | None:
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

    return cast(
        RequestType,
        dict(id=body["id"], type=body["type"], endpoint=body["endpoint"], data=body["data"]),
    )


def create_event(kind: str, data: Any):
    return {"type": "event", "kind": kind, "data": data}


def create_error_event(reason: str, code: str):
    return create_event("error", {"reason": reason, "code": code})


class WebsocketDomain:
    def __init__(self, path: str):
        self.path = path

        self.entrypoint: CallableInfo[Any] | None = None
        self.endpoints: dict[str, CallableInfo[Any]] = {}
        self.terminator: CallableInfo[Any] | None = None

    def enter(self, entrypoint: Tc) -> Tc:
        """Register connection handler"""
        self.entrypoint = scan(entrypoint)
        return entrypoint

    def endpoint(self, name: str) -> Callable[[Tc], Tc]:
        """Register endpoint"""

        def register_endpoint(entry: Tc) -> Tc:
            self.endpoints[name] = scan(entry)
            return entry

        return register_endpoint

    def exit(self, terminator: Tc) -> Tc:
        """Register connection termination handler"""
        self.terminator = scan(terminator)
        return terminator

    async def __call__(self, websocket: WebSocket):
        await websocket.accept()

        user_scope: dict[str, Any] = {}

        if self.entrypoint is not None:
            try:
                raw_response = await util.fast_inject(
                    self.entrypoint, {"ws": websocket, "scope": user_scope, "context": user_scope}
                )
                response = jsonable_encoder(raw_response)
                await websocket.send_json(create_event("init", response))
            except Exception as exc:
                await self._handle_exception(exc, websocket, user_scope)

        async for message in websocket.iter_json():
            request = validate_request(message)
            if request is None:
                await websocket.send_json(
                    create_error_event("Invalid request sent", "validation-error")
                )
                continue

            try:
                await self._handle_request(request, websocket, user_scope)
            except Exception as exc:
                await self._handle_exception(exc, websocket, user_scope)

    async def _handle_request(
        self, request: RequestType, websocket: WebSocket, user_scope: dict[str, Any]
    ) -> None:
        endpoint = self.endpoints.get(request["endpoint"])

        if endpoint is None:
            await websocket.send_json(create_error_event("Invalid endpoint", "invalid-endpoint"))
            return

        try:
            raw_response = await util.fast_inject(
                endpoint,
                {
                    **user_scope,
                    "ws": websocket,
                    "request_data": request["data"],
                    "scope": user_scope,
                    "context": user_scope,
                },
            )
        except BaseRequestError as exc:
            await websocket.send_json(
                {"id": request["id"], "type": "response.error", "data": exc.json()}
            )
            return

        response = jsonable_encoder(raw_response)
        await websocket.send_json({"id": request["id"], "type": "response", "data": response})

    async def _handle_exception(
        self, exception: Exception, websocket: WebSocket, user_scope: dict[str, Any]
    ) -> None:
        if isinstance(exception, WebSocketDisconnect):
            await util.fast_inject(
                self.terminator, {**user_scope, "scope": user_scope, "context": user_scope}
            )
            return

        await websocket.send_json(create_error_event("Internal server error", "internal-error"))
        traceback.print_exception(exception)

    def connect_to_fastapi(self, router: APIRouter):
        """Connect websocket domain to FastAPI router"""
        router.add_api_websocket_route(self.path, self.__call__)
