import logging

from aiortc import RTCIceCandidate, RTCSessionDescription
from socketio import AsyncServer

from app.connection.session import SessionManager

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class SocketEventHandler:
    def __init__(self, sio: AsyncServer):
        self.sio = sio
        self.session_manager = SessionManager(sio)

    async def connect(self, sid, environ):
        logger.info(f"🔌 Connected: {sid}")
        await self.session_manager.add(sid)

    async def disconnect(self, sid):
        logger.info(f"❌ Disconnected: {sid}")
        await self.session_manager.remove(sid)

    async def offer(self, sid, data):
        session = await self.session_manager.get(sid)
        if not session.peer_connection:
            session.create_peer_connection()
        pc = session.peer_connection

        offer = RTCSessionDescription(sdp=data["sdp"], type=data["type"])
        await pc.setRemoteDescription(offer)
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)

        await self.sio.emit(
            "answer",
            {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type},
            to=sid,
        )

    async def ice_candidate(self, sid, data):
        candidate = RTCIceCandidate(
            sdpMid=data["sdpMid"],
            sdpMLineIndex=data["sdpMLineIndex"],
            candidate=data["candidate"],
        )
        session = await self.session_manager.get(sid)
        if session.peer_connection:
            await session.peer_connection.addIceCandidate(candidate)

    async def voice(self, sid, data):
        session = await self.session_manager.get(sid)
        if not session:
            return

        voice = data["gender"]
        session.voice = voice

        if session.peer_connection:
            session.peer_connection.tts_track.set_voice(voice)

        return {"status": "ok"}
