
from __future__ import annotations
from typing import TYPE_CHECKING, Optional, TypeVar, Callable, Awaitable
if TYPE_CHECKING:
    from types import TracebackType
    from redditwarp.websocket.websocket_ASYNC import WebSocket

import asyncio

from redditwarp.ASYNC import Client
from redditwarp.dark.ASYNC import Client as DarkClient
from redditwarp.dark.core.http_client_ASYNC import RedditHTTPClient
from redditwarp.websocket.transport.reg_ASYNC import connect
from redditwarp.websocket import exceptions as ws_exceptions


class OnlinePresenceIndicator:
    _TSelf = TypeVar('_TSelf', bound='OnlinePresenceIndicator')

    class BeingOnline:
        _TSelf = TypeVar('_TSelf', bound='OnlinePresenceIndicator.BeingOnline')

        def __init__(self, outer: OnlinePresenceIndicator) -> None:
            self._outer = outer

        async def __aenter__(self: _TSelf) -> _TSelf:
            await self._outer.start()
            return self

        async def __aexit__(self,
            exc_type: Optional[type[BaseException]],
            exc_value: Optional[BaseException],
            exc_traceback: Optional[TracebackType],
        ) -> Optional[bool]:
            await self._outer.stop()
            return None

    def __init__(self, ws: WebSocket, user_id36: str) -> None:
        self.ws: WebSocket = ws
        self.user_id36: str = user_id36

    async def __aenter__(self: _TSelf) -> _TSelf:
        return self

    async def __aexit__(self,
        exc_type: Optional[type[BaseException]],
        exc_value: Optional[BaseException],
        exc_traceback: Optional[TracebackType],
    ) -> Optional[bool]:
        await self.close()
        return None

    async def start(self) -> None:
        s = r'''{"id":"1","type":"start","payload":{"variables":{"input":{"channel":{"teamOwner":"CONTENT_AND_COMMUNITIES","category":"USER_IS_ONLINE","userID":"t2_%s"}}},"extensions":{},"operationName":"SubscribeSubscription","query":"subscription SubscribeSubscription($input: SubscribeInput!) {\n  subscribe(input: $input) {\n    id\n    __typename\n  }\n}\n"}}'''
        await self.ws.send(s % self.user_id36)

    async def stop(self) -> None:
        await self.ws.send(r'''{"id":"1","type":"stop"}''')

    async def close(self) -> None:
        await self.ws.send(r'''{"type":"connection_terminate","payload":null}''')
        await self.ws.close()

    def being_online(self) -> BeingOnline:
        return self.BeingOnline(self)


async def create_online_presence_indicator_factory(username: str, password: str
        ) -> Callable[[], Awaitable[OnlinePresenceIndicator]]:
    dark_client = DarkClient()
    dark_http = dark_client.http
    if not isinstance(dark_http, RedditHTTPClient):
        raise Exception
    dark_authorizer = dark_http.authorizer

    await dark_client.p.login.do_legacy_web_login(username, password)

    client = Client.from_http(dark_http)
    user_id36 = (await client.p.account.fetch()).id36

    async def factory() -> OnlinePresenceIndicator:
        token = await dark_authorizer.attain_token()
        ua = dark_http.get_user_agent()
        ws = await connect(
            'wss://gql-realtime.reddit.com/query',
            headers={
                'Origin': 'https://oauth.reddit.com',
                'User-Agent': ua,
            },
        )
        s = r'''{"type":"connection_init","payload":{"Authorization":"Bearer %s"}}'''
        await ws.send(s % token.access_token)
        return OnlinePresenceIndicator(ws, user_id36)

    return factory


async def do_online_presence_indicator_forever(factory: Callable[[], Awaitable[OnlinePresenceIndicator]]) -> None:
    while True:
        try:
            presence = await factory()
            async with (presence, presence.being_online()):
                async for _event in presence.ws:
                    pass
        except ws_exceptions.TransportError:
            await asyncio.sleep(60)
