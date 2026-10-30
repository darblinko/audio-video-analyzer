"""ASGI middleware that rejects requests before the routes parse them."""

from collections.abc import Iterable

from starlette.exceptions import HTTPException
from starlette.responses import PlainTextResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class BodyLimitMiddleware:
    """Return 413 when a request body to one of `paths` exceeds `limit` bytes.

    The declared Content-Length is checked first. Bodies without one (chunked transfer) are
    counted as they arrive, so the multipart parser never spools more than `limit` bytes.
    """

    def __init__(self, app: ASGIApp, limit: int, paths: Iterable[str]) -> None:
        self.app = app
        self.limit = limit
        self.paths = frozenset(paths)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"] not in self.paths:
            await self.app(scope, receive, send)
            return
        declared = dict(scope["headers"]).get(b"content-length")
        if declared is not None and (not declared.isdigit() or int(declared) > self.limit):
            await _too_large(scope, receive, send)
            return

        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.limit:
                    # FastAPI re-raises HTTPException from body parsing, so this becomes a 413.
                    raise HTTPException(413, "request body exceeds AVA_MAX_UPLOAD_MB")
            return message

        await self.app(scope, limited_receive, send)


async def _too_large(scope: Scope, receive: Receive, send: Send) -> None:
    response = PlainTextResponse("request body exceeds AVA_MAX_UPLOAD_MB", status_code=413)
    await response(scope, receive, send)


SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


class OriginGuardMiddleware:
    """Refuse state-changing requests and WebSocket handshakes from origins not in `allowed`.

    CORS only stops a browser from reading a response; the request itself still runs. Requests
    without an Origin header (curl, scripts) are not sent by a browser page and pass.
    """

    def __init__(self, app: ASGIApp, allowed: Iterable[str]) -> None:
        self.app = app
        self.allowed = frozenset(allowed)

    def _trusted(self, scope: Scope) -> bool:
        origin = dict(scope["headers"]).get(b"origin")
        return origin is None or origin.decode("latin-1") in self.allowed

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "websocket" and not self._trusted(scope):
            await receive()  # the websocket.connect message
            # Closing before accept makes the server answer the handshake with 403.
            await send({"type": "websocket.close", "code": 1008})
            return
        if (
            scope["type"] == "http"
            and scope["method"] not in SAFE_METHODS
            and not self._trusted(scope)
        ):
            response = PlainTextResponse("origin not allowed", status_code=403)
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)
