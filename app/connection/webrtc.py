import asyncio
import logging
from time import time

from aiortc import RTCPeerConnection
from azure.cognitiveservices.speech import SpeechSynthesisVisemeEventArgs
from socketio import AsyncServer

from app.audio.receiver import AudioReceiver
from app.service.stt import STTService
from app.service.tts import TTSAudioTrack

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class PeerConnection(RTCPeerConnection):
    def __init__(self, sid, sio: AsyncServer):
        super().__init__()
        self.sid = sid
        self.sio = sio
        self.tts_track = TTSAudioTrack(self.emit_viseme)
        self.sender = self.addTrack(self.tts_track)
        self.audio_receiver = None
        self.recv_task = None
        self.loop = asyncio.get_running_loop()

    def set_audio_receiver(self, track):
        if self.audio_receiver:
            return

        stt_service = STTService(self.emit_stt_message)
        self.audio_receiver = AudioReceiver(
            track, self.sid, self.tts_track, stt_service
        )
        self.recv_task = asyncio.create_task(self.audio_receiver.recv())

    async def emit_stt_message(self, stt_result: str):
        await self.sio.emit(
            "message",
            {
                "role": "user",
                "content": {
                    "text": stt_result,
                    "type": "speech",
                },
                "time": int(time() * 1000),
            },
            to=self.sid,
        )

    def emit_viseme(self, event: SpeechSynthesisVisemeEventArgs):
        asyncio.run_coroutine_threadsafe(
            self.sio.emit(
                "viseme",
                {
                    "animation": event.animation,
                    "audio_offset": event.audio_offset / 10000,
                    "viseme_id": event.viseme_id,
                },
                to=self.sid,
            ),
            self.loop,
        )
