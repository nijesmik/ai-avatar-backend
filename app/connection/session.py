import asyncio
import logging

from socketio import AsyncServer

from app.connection.webrtc import PeerConnection
from app.service.chat import ChatService

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class SessionManager:
    def __init__(self, sio: AsyncServer):
        self.sio = sio
        self.sessions = {}
        self.lock = asyncio.Lock()

    async def add(self, sid):
        async with self.lock:
            self.sessions[sid] = Session(sid, self.sio)

    async def get(self, sid) -> "Session" | None:
        async with self.lock:
            return self.sessions.get(sid, None)

    async def remove(self, sid):
        async with self.lock:
            session = self.sessions.pop(sid, None)
            session.remove_peer_connection()


class Session:
    def __init__(self, sid, sio: AsyncServer):
        super().__init__()
        self.sid = sid
        self.sio = sio
        self.chat = ChatService()
        self.peer_connection: PeerConnection = None

    async def remove_peer_connection(self):
        pc = self.peer_connection
        if not pc:
            return

        if pc.recv_task:
            pc.recv_task.cancel()
            try:
                logger.debug(f"🟡 AudioReceiver 종료 대기: {self.sid}")
                await pc.recv_task
            except asyncio.CancelledError:
                pass

        await pc.close()
        logger.info(f"❌ PeerConnection 종료: {self.sid}")

    def create_peer_connection(self):
        pc = PeerConnection(self.sid, self.sio)
        self.peer_connection = pc

        @pc.on("track")
        async def on_track(track):
            logger.debug(f"📥 Track 수신: {track.kind} - {self.sid}")
            if track.kind == "audio":
                pc.set_audio_receiver(track)

        @pc.on("connectionstatechange")
        async def on_connectionstatechange():
            if pc.connectionState in ["disconnected", "failed", "closed"]:
                await self.remove_peer_connection()

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
                    to=self.sid,
                )
