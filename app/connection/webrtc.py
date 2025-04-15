import asyncio
import logging
from socketio import AsyncServer
from aiortc import RTCPeerConnection
from app.audio.receiver import AudioReceiver

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class PeerConnectionManager:
    def __init__(self, sio: AsyncServer):
        self.sio = sio
        self.peer_connections = {}
        self.audio_receivers = {}
        self.lock = asyncio.Lock()

    async def add(self, sid, pc: RTCPeerConnection):
        async with self.lock:
            self.peer_connections[sid] = pc

    async def get(self, sid):
        async with self.lock:
            return self.peer_connections.get(sid)

    async def remove(self, sid):
        async with self.lock:
            pc = self.peer_connections.pop(sid, None)
            (ar, task) = self.audio_receivers.pop(sid, (None, None))

        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        if pc:
            await pc.close()

    async def _add_audio_receiver(self, sid, ar: AudioReceiver):
        async with self.lock:
            task = asyncio.create_task(ar.recv())
            self.audio_receivers[sid] = (ar, task)

    async def create(self, sid):
        pc = RTCPeerConnection()

        @pc.on("track")
        async def on_track(track):
            logger.info(f"🎧 Track: {track.kind}")
            if track.kind == "audio":
                await self._add_audio_receiver(sid, AudioReceiver(track, sid, pc))

        @pc.on("connectionstatechange")
        async def on_connectionstatechange():
            if pc.connectionState in ["disconnected", "failed", "closed"]:
                await self.remove(sid)
                logger.info(f"❌ WebRTC 연결 종료 처리 완료: {sid}")

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
