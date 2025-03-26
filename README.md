from pydantic import BaseModel

# Prototype

```python
from typing import Literal
from collections import defaultdict

from pydantic import BaseModel
from fastapi import FastAPI, Header

from fastapi_websocket import WSRegistry, WSWrapper, WebSocket, WSMultiuserDomain, ws_depends
from fastapi_websocket.event import WSEvent, WSEventHandler, event

class User:
    id: int
    avatar: str
    nickname: str

class UserSchema(BaseModel):
    id: int
    avatar: str
    nickname: str


class UserJoin(WSEvent, type="user_join"):
    user: UserSchema


class UserQuit(WSEvent, type="user_quit"):
    user: UserSchema


class UserHit(WSEvent, type="user_hit"):
    user: UserSchema
    target: UserSchema


class UserActionHit(WSEvent, type="user_action.hit"):
    action: Literal["hit"]
    target_id: int


class CannotHit(WSEvent, type="cannot_hit"):
    reason: str


class UserActionQuit(WSEvent, type="user_action.quit"):
    action: Literal["quit"]


class GameUser(WSWrapper):
    def __init__(self, user: User, game_id: int):
        self.user = user
        self.game_id = game_id
        

async def require_user(token: str = Header()) -> User: ...


async def ensure_game_exists(game_id: int) -> int: ...


class GameDomain(WSMultiuserDomain[GameUser], WSEventHandler):
    def __init__(self):
        self.games = defaultdict(list)

    async def entry(
        self,
        _: WebSocket,
        user: User = ws_depends(require_user),
        game_id: int = ws_depends(ensure_game_exists)
    ):

        user_wrapper = GameUser(user=user, game_id=game_id)

        self.games[user_wrapper.game_id].append(user_wrapper)

        await self.broadcast_event(UserJoin(user))
        
        return user_wrapper

    @event(UserActionHit)
    async def user_hit(self, event: UserActionHit, _: WebSocket, user_wrapper: GameUser):
        for target in self.games[user_wrapper.game_id]:
            if target.user.id == event.target_id:
                break
        else:
            await event.answer(CannotHit(reason="User does not exist"))
            return
            
        await self.broadcast_event(UserHit(user_wrapper.user, target=target.user))

    @event(UserActionQuit)
    async def user_quit(self, event: UserActionQuit, _: WebSocket, user_wrapper: GameUser):
        await self.broadcast_event(UserQuit(user_wrapper.user))


ws_registry = WSRegistry()

game_domain = ws_registry.domain("/game", GameDomain())


async def main():
    app = FastAPI()
    
    app.include_router(ws_registry.router)
```

# Prototype V2

```python
from pydantic import BaseModel
from fastapi import FastAPI, Depends, Header, WebSocket

from fastapi_websocket import WebsocketRoute, Event, Action, Store, require_store


class GameServer:
    async def add_player(self, ws: WebSocket, user_id: int): ...

    async def get_player(self, user_id: int): ...
    
    async def schedule(self, event: str, data: dict): ...
    
    async def schedule_with_response(self, event: str, data: dict): ...
    
    async def broadcast_event(self, event: Event): ...


async def require_game_server(game_id: int) -> GameServer: ...


class User:
    id: int
    username: str
    avatar: str
    
    
async def require_user(token: Header) -> User: ...


class UserSchema(BaseModel):
    id: int
    username: str
    avatar: str

    
class PlayerSchema(BaseModel):
    user: UserSchema
    hp: int

    
class PlayerJoinedEvent(Event):
    player: PlayerSchema

    
class PlayerHitEvent(Event):
    target: PlayerSchema
    hit_by: PlayerSchema
    
    
class HitPlayerAction(Action):
    user_id: int


route = WebsocketRoute("/game")


@route.entrypoint
async def join_game(
    ws: WebSocket,
    user: User = Depends(require_user),
    server: GameServer = Depends(require_game_server),
    store: Store = Depends(require_store),
):
    store.save(user=user, server=server)
    
    player = await server.add_player(ws, user.id)
    
    await server.broadcast_event(PlayerJoinedEvent(player=player))

    
@route.action(HitPlayerAction)
async def hit_player(
    action: HitPlayerAction,
    user: User,
    server: GameServer
):
    return await server.schedule_with_response("hit", {"predator": user.id, "victim": action.user_id})

```