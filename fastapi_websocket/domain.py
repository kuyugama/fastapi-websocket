import typing
import traceback

from fastapi import APIRouter
from fundi import CallableInfo, scan
from fastapi.encoders import jsonable_encoder
from starlette.websockets import WebSocket, WebSocketDisconnect

from . import util
from .error import BaseRequestError
from .types import create_event, create_error_event, validate_request, RequestType

Tc = typing.TypeVar("Tc", bound=typing.Callable)


class WebsocketDomain:
    def __init__(self, path: str):
        self.path = path

        self.entrypoint: CallableInfo[typing.Any] | None = None
        self.endpoints: dict[str, CallableInfo[typing.Any]] = {}
        self.terminator: CallableInfo[typing.Any] | None = None

    def enter(self, entrypoint: Tc) -> Tc:
        """Register connection handler"""
        self.entrypoint = scan(entrypoint)
        return entrypoint

    def endpoint(self, name: str) -> typing.Callable[[Tc], Tc]:
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

        user_scope: dict[str, typing.Any] = {
            "headers": websocket.headers,
            "cookies": websocket.cookies,
            "query_params": websocket.query_params,
            "path_params": websocket.path_params,
        }

        async def _send_event(kind: str, data: typing.Any):
            try:
                await websocket.send_json(create_event(kind, data))
            except Exception as exception:
                await self._handle_exception(
                    exception, websocket, {**user_scope, "send_event": None, "send_error": None}
                )

        async def _send_error(reason: str, code: str):
            try:
                await websocket.send_json(create_error_event(reason, code))
            except Exception as exception:
                await self._handle_exception(
                    exception, websocket, {**user_scope, "send_event": None, "send_error": None}
                )

        user_scope.update(send_event=_send_event, send_error=_send_error)

        if self.entrypoint is not None:
            try:
                scope = {
                    "ws": websocket,
                    "send_event": _send_event,
                    "send_error": _send_error,
                    "query_params": websocket.query_params,
                    "path_params": websocket.path_params,
                    "headers": websocket.headers,
                    "cookies": websocket.cookies,
                    "scope": user_scope,
                    "context": user_scope,
                }
                async with util.inline_inject(self.entrypoint, scope) as raw_response:
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
        self, request: RequestType, websocket: WebSocket, user_scope: dict[str, typing.Any]
    ) -> None:
        endpoint = self.endpoints.get(request["endpoint"])

        if endpoint is None:
            await websocket.send_json(create_error_event("Invalid endpoint", "invalid-endpoint"))
            return

        try:
            async with util.inline_inject(
                endpoint,
                {
                    **user_scope,
                    "ws": websocket,
                    "request_data": request["data"],
                    "scope": user_scope,
                    "context": user_scope,
                },
            ) as raw_response:
                response = jsonable_encoder(raw_response)
                await websocket.send_json(
                    {"id": request["id"], "type": "response", "data": response}
                )
        except BaseRequestError as exc:
            await websocket.send_json(
                {"id": request["id"], "type": "response.error", "data": exc.json()}
            )
            return

    async def _handle_exception(
        self, exception: Exception, websocket: WebSocket, user_scope: dict[str, typing.Any]
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
