import asyncio
import logging

from socketio import AsyncServer

from app.connection.webrtc import PeerConnection

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class PeerConnectionManager:
    def __init__(self, sio: AsyncServer):
        self.sio = sio
        self.peer_connections = {}
        self.lock = asyncio.Lock()

    async def add(self, sid, pc: PeerConnection):
        async with self.lock:
            self.peer_connections[sid] = pc

    async def get(self, sid) -> PeerConnection | None:
        async with self.lock:
            return self.peer_connections.get(sid, None)

    async def remove(self, sid):
        async with self.lock:
            pc = self.peer_connections.pop(sid, None)

        if not pc:
            return

        if pc.recv_task:
            pc.recv_task.cancel()
            try:
                logger.debug(f"🟡 AudioReceiver 종료 대기: {sid}")
                await pc.recv_task
            except asyncio.CancelledError:
                pass

        await pc.close()
        logger.info(f"❌ PeerConnection 종료: {sid}")

    async def create(self, sid):
        pc = PeerConnection(sid, self.sio)

        @pc.on("track")
        async def on_track(track):
            logger.debug(f"📥 Track 수신: {track.kind} - {sid}")
            if track.kind == "audio":
                pc.set_audio_receiver(track)

        @pc.on("connectionstatechange")
        async def on_connectionstatechange():
            if pc.connectionState in ["disconnected", "failed", "closed"]:
                await self.remove(sid)

        @pc.on("icecandidate")
        async def on_icecandidate(event):
            candidate = event.candidate
            if candidate:
                await self.sio.emit(
                    "ice_candidate",
                    {
                        "candidate": candidate.to_sdp(),
                        "sdpMid": candidate.sdpMid,
                        "sdpMLineIndex": candidate.sdpMLineIndex,
                    },
                    to=sid,
                )

        await self.add(sid, pc)
        return pc
