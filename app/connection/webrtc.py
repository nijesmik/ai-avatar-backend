import asyncio


class PeerConnectionManager:
    def __init__(self):
        self.peer_connections = {}
        self.lock = asyncio.Lock()

    async def add(self, sid, pc):
        async with self.lock:
            self.peer_connections[sid] = pc

    async def get(self, sid):
        async with self.lock:
            return self.peer_connections.get(sid)

    async def remove(self, sid):
        async with self.lock:
            pc = self.peer_connections.pop(sid, None)
            if pc:
                await pc.close()
