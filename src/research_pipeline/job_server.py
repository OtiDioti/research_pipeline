"""Thin stdio MCP adapter. The research runtime owns jobs and event-driven waits."""
import asyncio
import json
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from pydantic import StrictFloat, StrictInt

from . import jobs


class Adapter:
    def __init__(self, context):
        self.context = context

    async def call(self, operation, **arguments):
        reader, writer = await asyncio.open_unix_connection(self.context.get('socket', '/run/research-rpc/control.sock'), limit=1024 * 1024 + 1)
        try:
            writer.write((json.dumps({'token': self.context['token'], 'operation': operation, 'arguments': arguments}, allow_nan=False) + '\n').encode())
            await writer.drain()
            # Wait subscriptions have no scientific/RPC lifetime clamp. Closing this
            # context closes the connection, without cancelling the computation.
            raw = await reader.readline()
            if not raw:
                raise jobs.JobError('Control connection ended; outcome unknown; inspect before resubmission')
            result = json.loads(raw)
            if 'error' in result:
                raise jobs.JobError(result['error'])
            return result['result']
        finally:
            writer.close()
            await writer.wait_closed()


def create_server(adapter):
    server = FastMCP('research-jobs')

    @server.tool()
    async def job_run(argv: list[str], cwd: str, runtime_seconds: StrictFloat | StrictInt) -> dict:
        """Admit once with an explicit positive finite timeout, including hours.
        Return a stable job ID. Deadline includes preparation and all descendants.
        cwd is an absolute /project path in your own workspace. No queue or retry.
        """
        return await adapter.call('job_run', argv=argv, cwd=cwd, runtime_seconds=runtime_seconds)

    @server.tool()
    async def job_status(job_id: str | None = None) -> dict:
        """Inspect this logical owner's jobs, including retained results and cleanup evidence."""
        return await adapter.call('job_status', job_id=job_id)

    @server.tool()
    async def job_wait(job_id: str) -> dict:
        """Subscribe until this owned job finishes. No model polling, restart or deadline extension."""
        return await adapter.call('job_wait', job_id=job_id)

    @server.tool()
    async def job_cancel(job_id: str) -> dict:
        """Cancel an owned job; report confirmed cleanup or explicit uncertainty."""
        return await adapter.call('job_cancel', job_id=job_id)

    @server.tool()
    async def write_draft(path: str, content: str) -> dict:
        """Save scoped scientific Markdown independently of job capacity."""
        return await adapter.call('write_draft', path=path, content=content)

    @server.tool()
    async def control(action: str = 'check', path: str | None = None, parent: str = 'primary',
                      offset: StrictInt = 0) -> dict:
        """Fixed operations: check, tasks, delegate, verify, documents, read_document.
        documents lists scoped immutable snapshots, 32 per page. read_document uses
        path=document_id and offset=character offset; follow next_offset for more.
        Handoffs/reports remain readable before safe canonical publication.
        Terminal decisions and automatic rollover are later lifecycle increments.
        """
        return await adapter.call('control', action=action, path=path, parent=parent, offset=offset)

    return server


def main():
    context = jobs.read(Path('/run/research-jobs.json'))
    if not context:
        raise jobs.JobError('Controlled context attachment unavailable')
    create_server(Adapter(context)).run(transport='stdio')


if __name__ == '__main__':
    main()
