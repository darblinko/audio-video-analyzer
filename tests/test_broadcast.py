import asyncio
import time

from av_analyzer.server import ConnectionManager


class FakeSocket:
    def __init__(self, stall: bool = False):
        self.stall = stall
        self.sent: list[dict] = []

    async def send_json(self, message: dict) -> None:
        if self.stall:
            await asyncio.sleep(3600)
        self.sent.append(message)


def test_a_stalled_client_does_not_block_the_broadcast():
    manager = ConnectionManager(send_timeout_s=0.05)
    stalled, healthy = FakeSocket(stall=True), FakeSocket()
    manager.connections = [stalled, healthy]
    started = time.monotonic()
    asyncio.run(manager.broadcast({"type": "progress"}))
    assert time.monotonic() - started < 1.0
    assert healthy.sent == [{"type": "progress"}]
    assert manager.connections == [healthy]


def test_broadcast_sends_to_clients_concurrently():
    class SlowSocket(FakeSocket):
        async def send_json(self, message: dict) -> None:
            await asyncio.sleep(0.2)
            self.sent.append(message)

    manager = ConnectionManager(send_timeout_s=1.0)
    manager.connections = [SlowSocket() for _ in range(5)]
    started = time.monotonic()
    asyncio.run(manager.broadcast({"type": "progress"}))
    assert time.monotonic() - started < 0.6
    assert all(socket.sent for socket in manager.connections)
