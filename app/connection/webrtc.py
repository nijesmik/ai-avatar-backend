import asyncio
import logging

from aiortc import RTCPeerConnection
from azure.cognitiveservices.speech import SpeechSynthesisVisemeEventArgs
from socketio import AsyncServer

from app.audio.receiver import AudioReceiver
from app.audio.track import AudioTrack
from app.audio.tts import TTSAudioTrack

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class PeerConnection(RTCPeerConnection):
    def __init__(self, sid, sio: AsyncServer):
        super().__init__()
        self.sid = sid
        self.sio = sio
        self.sender = self.addTrack(AudioTrack())
        self.audio_receiver = None
        self.recv_task = None
        self.loop = asyncio.get_running_loop()

    def set_audio_receiver(self, track):
        if self.audio_receiver:
            return

        self.audio_receiver = AudioReceiver(track, self.sid, self.tts)
        self.recv_task = asyncio.create_task(self.audio_receiver.recv())

    async def tts(self, text: str):
        tts = TTSAudioTrack(text, self.send_viseme)
        self.add_tts_track(tts)
        await tts.run_synthesis()

    async def add_tts_track(self, tts: TTSAudioTrack):
        self.addTrack(tts)
        await self.sio.emit("renegotiate", to=self.sid)

    async def replace_tts_track(self, tts: TTSAudioTrack):
        old_track: AudioTrack = self.sender.track
        tts.start_time = old_track.start_time
        self.sender.replaceTrack(tts)

        if old_track:
            old_track.stop()

    def send_viseme(self, event: SpeechSynthesisVisemeEventArgs):
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
