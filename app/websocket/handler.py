import logging
from time import time

from aiortc import RTCIceCandidate, RTCSessionDescription
from google.genai.errors import ServerError
from socketio import AsyncServer

from app.connection.session import SessionManager
from app.service.chat import ModelList, Model
from app.service.tts import SynthesisVoiceKorean

logger = logging.getLogger(__name__)

supported_models: list[Model] = [
    ModelList.Groq.Gemma2_9b_It,
    ModelList.Google.Gemini_2_Flash_Lite,
    ModelList.Google.Gemini_2_Flash
]


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
        voice = SynthesisVoiceKorean.get(gender=data["gender"], voice=data["voice"])
        if voice is None:
            return

        session = await self.session_manager.get(sid)
        if not session:
            return

        session.voice = voice

        if session.peer_connection:
            session.peer_connection.tts_track.voice = voice

        return {"status": "ok"}

    async def message(self, sid, data):
        session = await self.session_manager.get(sid)
        if not session:
            return

        try:
            text = data["text"]
            response = session.chat.llm.send_message_stream(text)

            async for chunk in response:
                await self.sio.emit(
                    "message-chunk",
                    {
                        "text": chunk,
                        "time": int(time() * 1000),
                    },
                    to=sid,
                )

        except ServerError as e:
            return {
                "code": e.code,
                "message": e.message,
                "status": e.status,
                "time": int(time() * 1000),
            }

        return {
            "status": "ok",
        }

    async def model(self, sid, data):
        session = await self.session_manager.get(sid)
        if not session:
            return

        model = data["model"]

        for supported in supported_models:
            if supported.equal(model):
                session.chat.change_model(supported)
                return {"status": "ok"}

        return {
            "status": "Unsupported",
        }
