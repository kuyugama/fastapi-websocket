import typing
from contextlib import AsyncExitStack

from fundi import ainject, scan, CallableInfo

__all__ = ("fast_inject",)

R = typing.TypeVar("R")

SyncLifespan: typing.TypeAlias = typing.Generator[R, None, None]
AsyncLifespan: typing.TypeAlias = typing.AsyncGenerator[R, None]
# noinspection PyTypeHints
Lifespan: typing.TypeAlias = typing.Generator[R, None, None] | typing.AsyncGenerator[R, None]

Injectable: typing.TypeAlias = typing.Union[typing.Callable[..., R], CallableInfo[R]]
Scope: typing.TypeAlias = typing.Mapping[str, typing.Any]


@typing.overload
async def fast_inject(
    where: Injectable[Lifespan[R]],
    scope: Scope,
) -> R: ...
@typing.overload
async def fast_inject(
    where: Injectable[typing.Awaitable[R]],
    scope: Scope,
) -> R: ...
@typing.overload
async def fast_inject(
    where: Injectable[R],
    scope: Scope,
) -> R: ...
async def fast_inject(where: Injectable[typing.Any], scope: Scope) -> typing.Any:
    """Utility function to inject dependencies without bothering setting up exit stack"""
    if not isinstance(where, CallableInfo):
        where = scan(where)

    async with AsyncExitStack() as stack:
        return await ainject(scope, where, stack)
