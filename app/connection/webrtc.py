import asyncio

from aiortc import RTCPeerConnection

from app.audio.receiver import AudioReceiver
from app.service.chat import ChatService
from app.service.stt import STTResult
from app.service.tts import TTSAudioTrack
from app.websocket.emit import emit_speech_message


class PeerConnection(RTCPeerConnection):
    def __init__(self, sid, chat_service: ChatService, voice):
        super().__init__()
        self.sid = sid
        self.chat_service = chat_service
        self.tts_track = TTSAudioTrack(sid, voice)
        self.sender = self.addTrack(self.tts_track)
        self.audio_receiver = None
        self.recv_task = None

    def set_audio_receiver(self, track):
        if self.audio_receiver:
            return

        self.audio_receiver = AudioReceiver(track, self.sid, self.create_tts_response)
        self.recv_task = asyncio.create_task(self.audio_receiver.recv())

    async def create_tts_response(self, stt: STTResult):
        if not stt.success:
            await self.tts_track.run_synthesis(self.generate_error_response(stt.reason))
            return

        text = stt.text
        emit_task = asyncio.create_task(emit_speech_message(self.sid, "user", text))

        await self.tts_track.run_synthesis(self.chat_service.send_utterance(text))

        await emit_task
        await self.chat_service.wait_emit_message()

    async def generate_error_response(self, reason: str | None):
        if reason == "No more slot":
            yield "서버 연결이 원활하지 않습니다.다시 말씀해 주세요."
        if reason == "Unavilable":
            yield "음성 인식 서버에 문제가 발생했습니다.나중에 다시 시도해 주세요."
        else:
            yield "음성 인식에 실패했습니다.잠시 후 다시 시도해 주세요."
