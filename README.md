# # _FastAPI Websocket_

> This library still in development(it may stay in this state forever!)

> Because, no one created that before

This library implements convenient websocket connection handler

## Less talk, more code:

```python
import logging

from fastapi import FastAPI
from pydantic import BaseModel
from fundi import from_, FromType
from starlette.websockets import WebSocket
from fastapi_websocket import from_model, SendEvent
from fastapi_websocket.domain import WebsocketDomain


class Move(BaseModel):
    x: int
    y: int


def require_game_id(ws: FromType[WebSocket]):
    return ws.query_params["game_id"]


route = WebsocketDomain("/ws")


@route.enter
async def enter(
    context: dict,
    send_event: SendEvent,
    game_id: int = from_(require_game_id),
):
    """New connection established"""
    print(f"Entered game {game_id = }")
    print(f"{context.get('state') = }")

    context.update(game_id=game_id)
    
    # game_manager.create_game(game_id)
    
    await send_event("game:state", {"status": "init", "player_count": 1})
    
    return {"success": True}


@route.endpoint("move")
async def some_action(
        game_id: int, move: Move = from_model(Move)
):
    print(f"Endpoint 'move' called with {move} {game_id = }")
    return {"success": True}


@route.exit()
async def disconnect(game_id: int):
    """Connection was closed during sending an event or response"""
    
    # game_manager.close_game(game_id)


app = FastAPI()

route.connect_to_fastapi(app.router)

logging.basicConfig(format="[%(levelname)s] %(name)s - %(message)s", level=logging.INFO)
```

Code above shows basic usage of this library.

This library realises custom protocol on top of websockets. This protocol contains 4 possible objects:
1. `event` - can be sent by server to inform client about something without client's request. 

   Example:

   `{"type": "event", "kind": "event-kind", "data": Any}`
2. `request` - sent by client to get response

   Example:

   `{"id": "request-id", "type": "request", "data": Any}`
3. `response` - sent by server in response to client's request

   Example:

   `{"id": "request-id", "type": "response", "data": Any}`
4. `response.error` - sent by server in response to client's request to inform about unsuccessful request handling (validation errors, service errors, etc.)

   Example:

   `{"id": "request-id", "type": "response.error", "data": Any}`
