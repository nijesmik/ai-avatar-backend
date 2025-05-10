import asyncio
import logging

from socketio import AsyncServer

from app.connection.webrtc import PeerConnection
from app.service.chat import Google, Groq, Model, Provider
from app.service.tts import SynthesisVoiceKorean

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class Session:
    def __init__(self, sid, sio: AsyncServer):
        super().__init__()
        self.sid = sid
        self.sio = sio
        self.chat = Groq(sid)
        self.voice = SynthesisVoiceKorean.InJoon
        self.peer_connection: PeerConnection = None

    async def remove_peer_connection(self):
        pc = self.peer_connection
        if not pc:
            return

        if pc.recv_task:
            pc.recv_task.cancel()
            try:
                await pc.recv_task
            except asyncio.CancelledError:
                pass
            finally:
                await pc.audio_receiver.cancel()
                logger.info(f"❌ AudioReceiver 종료: {self.sid}")

        await pc.close()
        logger.info(f"❌ PeerConnection 종료: {self.sid}")

    def create_peer_connection(self):
        pc = PeerConnection(self.sid, self.chat, self.voice)
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
                self.peer_connection = None

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

    def replace_model(self, model: Model):
        provider = model.provider()
        if provider == Provider.Google:
            self.chat = Google(self.sid, self.chat.messages)
        elif provider == Provider.Groq:
            self.chat = Groq(self.sid, self.chat.messages)
        else:
            return

        if self.peer_connection:
            self.peer_connection.chat_service = self.chat


class SessionManager:
    def __init__(self, sio: AsyncServer):
        self.sio = sio
        self.sessions = {}
        self.lock = asyncio.Lock()

    async def add(self, sid):
        async with self.lock:
            self.sessions[sid] = Session(sid, self.sio)

    async def get(self, sid) -> Session | None:
        async with self.lock:
            return self.sessions.get(sid, None)

    async def remove(self, sid):
        async with self.lock:
            session = self.sessions.pop(sid, None)
        if session:
            await session.remove_peer_connection()
