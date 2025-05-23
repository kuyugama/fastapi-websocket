import asyncio
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


async def _handle_exception(exception: Exception, websocket: WebSocket) -> None:
    if isinstance(exception, WebSocketDisconnect):
        return

    traceback.print_exception(exception)
    await websocket.send_json(create_error_event("Internal server error", "internal-error"))


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

        user_context: dict[str, typing.Any] = {
            "headers": websocket.headers,
            "cookies": websocket.cookies,
            "query_params": websocket.query_params,
            "path_params": websocket.path_params,
        }

        async def _send_event(kind: str, data: typing.Any):
            try:
                await websocket.send_json(create_event(kind, data))
            except Exception as exception:
                await _handle_exception(exception, websocket)

        async def _send_error(reason: str, code: str):
            try:
                await websocket.send_json(create_error_event(reason, code))
            except Exception as exception:
                await _handle_exception(exception, websocket)

        user_context.update(send_event=_send_event, send_error=_send_error)

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
                    "context": user_context,
                }
                async with util.inline_inject(self.entrypoint, scope) as raw_response:
                    response = jsonable_encoder(raw_response)
                    await websocket.send_json(create_event("init", response))

            except Exception as exc:
                await _handle_exception(exc, websocket)

        async for message in websocket.iter_json():
            request = validate_request(message)
            if request is None:
                await websocket.send_json(
                    create_error_event("Invalid request sent", "validation-error")
                )
                continue

            asyncio.create_task(
                self._handle_request(request, websocket, user_context), name="handle-request"
            )

        if self.terminator is not None:
            await util.fast_inject(self.terminator, {**user_context, "context": user_context})

    async def _handle_request(
        self, request: RequestType, websocket: WebSocket, user_context: dict[str, typing.Any]
    ) -> None:
        try:
            endpoint = self.endpoints.get(request["endpoint"])

            if endpoint is None:
                await websocket.send_json(
                    create_error_event("Invalid endpoint", "invalid-endpoint")
                )
                return

            async with util.inline_inject(
                endpoint,
                {
                    **user_context,
                    "ws": websocket,
                    "request_data": request["data"],
                    "context": user_context,
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

        except Exception as exc:
            await _handle_exception(exc, websocket)

    def connect_to_fastapi(self, router: APIRouter):
        """Connect websocket domain to FastAPI router"""
        router.add_api_websocket_route(self.path, self.__call__)
