"""The controller's socket: how an agent's MCP tool server reaches the controller.

Each agent's CLI starts our MCP server (:mod:`research_pipeline.mcp_server`) as a
child process inside the agent's confinement. That server forwards every tool call
to the controller over a Linux *abstract* Unix socket. An abstract socket has no
file path, so it needs no writable or visible file inside the confinement and has
no path-length limit. Each request carries the agent's identity and the token of
its current session, so a stale session cannot act.

Protocol: one JSON object per line in each direction, one request per connection.
"""
from __future__ import annotations

import asyncio
import json
import socket
from typing import Awaitable, Callable

#: Largest request or reply accepted, in bytes.
LIMIT = 4 * 1024 * 1024

Handler = Callable[[dict], Awaitable[str]]


async def serve(name: str, handler: Handler) -> asyncio.AbstractServer:
    """Listen on the abstract socket ``name``; each request's reply text comes from ``handler``."""

    async def connection(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            request = json.loads(await reader.readline())
            text = await handler(request)
        except Exception as error:  # a broken request must never take the controller down
            text = f'Error: {error}'
        try:
            writer.write(json.dumps({'text': text}).encode() + b'\n')
            await writer.drain()
        except (ConnectionError, OSError):
            pass  # the caller's session ended meanwhile (e.g. the investigation finished)
        finally:
            writer.close()

    return await asyncio.start_unix_server(connection, path='\0' + name, limit=LIMIT)


def call(name: str, request: dict, timeout: float = 300) -> str:
    """Send ``request`` to the controller listening on ``name`` and return its reply text (blocking)."""
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(timeout)
        connection.connect('\0' + name)
        connection.sendall(json.dumps(request).encode() + b'\n')
        with connection.makefile('rb') as replies:
            line = replies.readline(LIMIT)
    if not line:
        raise ConnectionError('the research controller closed the connection without replying')
    return json.loads(line)['text']
