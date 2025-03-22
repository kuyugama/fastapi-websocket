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