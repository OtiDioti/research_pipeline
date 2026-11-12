"""Small research-owned newline JSON-RPC driver; no controller-engine dependency."""
import asyncio
import json

from .isolation import RuntimeUnavailable


class Client:
    def __init__(self, service, on_event=None):
        self.service = service
        self.on_event = on_event
        self.pending = {}
        self.serial = 0
        self.reader = None
        self.diagnostics = bytearray()
        self.failure = None
        self.turns = {}
        self.completed = {}
        self.telemetry = None
        self.thread_id = None

    async def send(self, message):
        data = (json.dumps(message, allow_nan=False) + '\n').encode()
        if len(data) > 1024 * 1024:
            raise RuntimeUnavailable('RPC message exceeds 1 MiB')
        self.service.process.stdin.write(data)
        await self.service.process.stdin.drain()

    async def request(self, method, params, timeout=15):
        if self.failure:
            raise self.failure
        self.serial += 1
        serial = self.serial
        future = asyncio.get_running_loop().create_future()
        self.pending[serial] = future
        try:
            await self.send({'id': serial, 'method': method, 'params': params})
            return await asyncio.wait_for(future, timeout)
        except asyncio.TimeoutError as exc:
            raise RuntimeUnavailable(f'Operational RPC timeout: {method}; outcome uncertain') from exc
        finally:
            self.pending.pop(serial, None)

    async def start(self):
        self.reader = asyncio.create_task(self.read())
        self.stderr = asyncio.create_task(self.read_stderr())
        await self.request('initialize', {'clientInfo': {'name': 'research_pipeline', 'version': '0.1.0'},
                                         'capabilities': {'experimentalApi': False}})
        await self.send({'method': 'initialized'})

    async def read_stderr(self):
        while data := await self.service.process.stderr.read(65536):
            self.diagnostics.extend(data[:max(0, 16384 - len(self.diagnostics))])

    async def read(self):
        try:
            while raw := await self.service.process.stdout.readline():
                if len(raw) > 1024 * 1024:
                    raise RuntimeUnavailable('App-server message exceeds 1 MiB')
                value = json.loads(raw)
                if not isinstance(value, dict):
                    raise RuntimeUnavailable('Malformed app-server message')
                if 'id' in value and 'method' not in value:
                    future = self.pending.get(value['id'])
                    if future is None or future.done():
                        raise RuntimeUnavailable('Uncorrelated app-server response')
                    if 'error' in value:
                        future.set_exception(RuntimeUnavailable(f'App-server RPC error: {value["error"]}'))
                    elif 'result' in value:
                        future.set_result(value['result'])
                    else:
                        raise RuntimeUnavailable('RPC response has neither result nor error')
                elif 'id' in value:
                    # Never silently approve unknown requests, permissions or tools.
                    await self.send({'id': value['id'], 'error': {'code': -32601, 'message': 'Unsupported research boundary request'}})
                    raise RuntimeUnavailable(f'Unexpected app-server request: {value.get("method")}')
                elif isinstance(value.get('method'), str):
                    method, params = value['method'], value.get('params', {})
                    if method == 'turn/completed':
                        if params.get('threadId') != self.thread_id:
                            raise RuntimeUnavailable('Turn notification thread ownership mismatch')
                        turn = params['turn']
                        self.completed[turn['id']] = turn
                        event = self.turns.pop(turn['id'], None)
                        if event and not event.done():
                            event.set_result(turn)
                    if method == 'thread/tokenUsage/updated':
                        if params.get('threadId') != self.thread_id:
                            raise RuntimeUnavailable('Telemetry thread ownership mismatch')
                        self.telemetry = params.get('tokenUsage')
                    if self.on_event:
                        await self.on_event(value)
                else:
                    raise RuntimeUnavailable('Malformed RPC notification')
            raise RuntimeUnavailable('App-server EOF; context ended unexpectedly')
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self.failure = exc if isinstance(exc, RuntimeUnavailable) else RuntimeUnavailable(f'App-server protocol failure: {exc}')
            for future in [*self.pending.values(), *self.turns.values()]:
                if not future.done():
                    future.set_exception(self.failure)

    async def new_thread(self, cwd, model=None, instructions=None):
        params = {'cwd': cwd, 'sandbox': 'workspace-write', 'approvalPolicy': 'never',
                  'ephemeral': True, 'developerInstructions': instructions}
        if model:
            params['model'] = model
        result = await self.request('thread/start', params)
        self.thread_id = result['thread']['id']
        return self.thread_id

    async def turn(self, text):
        result = await self.request('turn/start', {'threadId': self.thread_id,
                    'input': [{'type': 'text', 'text': text}]})
        turn_id = result['turn']['id']
        if turn_id in self.completed:
            return self.completed.pop(turn_id)
        if self.failure:
            raise self.failure
        future = asyncio.get_running_loop().create_future()
        self.turns[turn_id] = future
        # There is intentionally no scientific session timer.
        return await future

    async def interrupt(self, turn_id):
        return await self.request('turn/interrupt', {'threadId': self.thread_id, 'turnId': turn_id})

    async def close(self):
        if self.thread_id and not self.failure:
            try:
                await self.request('thread/unsubscribe', {'threadId': self.thread_id}, timeout=5)
            except RuntimeUnavailable:
                pass
        result = await self.service.close()
        for task in (self.reader, self.stderr):
            if task:
                task.cancel()
        await asyncio.gather(*(t for t in (self.reader, self.stderr) if t), return_exceptions=True)
        return result
