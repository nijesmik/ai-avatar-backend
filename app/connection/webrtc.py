import asyncio
import logging
from aiortc import RTCPeerConnection
from app.audio.receiver import AudioReceiverTrack

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


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

    async def create(self, sid, emit_icecandidate):
        pc = RTCPeerConnection()

        @pc.on("track")
        def on_track(track):
            logger.info(f"🎧 Track: {track.kind}")
            if track.kind == "audio":
                pc.addTrack(AudioReceiverTrack(track, sid))

        @pc.on("connectionstatechange")
        async def on_connectionstatechange():
            if pc.connectionState in ["disconnected", "failed", "closed"]:
                await self.remove(sid)
                logger.info(f"❌ WebRTC 연결 종료 처리 완료: {sid}")

        @pc.on("icecandidate")
        async def on_icecandidate(event):
            candidate = event.candidate
            if candidate:
                await emit_icecandidate(
                    {
                        "candidate": candidate.to_sdp(),
                        "sdpMid": candidate.sdpMid,
                        "sdpMLineIndex": candidate.sdpMLineIndex,
                    },
                )

        await self.add(sid, pc)
        return pc
