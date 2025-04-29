import asyncio
import logging
import re

from aiortc import RTCPeerConnection

from app.audio.receiver import AudioReceiver
from app.service.chat import ChatService
from app.service.tts import TTSAudioTrack
from app.websocket.emit import emit_speech_message

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class PeerConnection(RTCPeerConnection):
    def __init__(self, sid, chat_service: ChatService):
        super().__init__()
        self.sid = sid
        self.chat_service = chat_service
        self.tts_track = TTSAudioTrack(sid)
        self.sender = self.addTrack(self.tts_track)
        self.audio_receiver = None
        self.recv_task = None

    def set_audio_receiver(self, track):
        if self.audio_receiver:
            return

        self.audio_receiver = AudioReceiver(track, self.sid, self.create_tts_response)
        self.recv_task = asyncio.create_task(self.audio_receiver.recv())

    async def create_tts_response(self, text: str):
        tasks = []
        task = asyncio.create_task(emit_speech_message(self.sid, "user", text))
        tasks.append(task)

        await self.tts_track.run_synthesis(self.generate_llm_response(text, tasks))

        await asyncio.gather(*tasks)

    async def generate_llm_response(self, text: str, tasks):
        response = await self.chat_service.send_utterance(text)

        task = asyncio.create_task(emit_speech_message(self.sid, "model", response))
        if tasks:
            tasks.append(task)

        yield re.sub(r"([.!?])\s+", r"\1", response)
