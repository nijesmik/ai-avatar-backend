from aiortc import MediaStreamTrack
import logging
import webrtcvad
import asyncio
from app.audio.stt import STTService
from app.audio.resample import resample_to_16k
from app.audio.utils import save_as_wav

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# 1ms 당 PCM 데이터: 16kHz => 16 samples/ms, each sample 2 bytes -> 16*2 = 32 bytes/ms.
BYTES_PER_MS = 16 * 2
BYTES_PER_SECOND = BYTES_PER_MS * 1000


class AudioReceiverTrack(MediaStreamTrack):
    kind = "audio"
    vad = webrtcvad.Vad(3)

    def __init__(self, track, sid):
        super().__init__()
        self.track = track
        self.sid = sid
        self.in_speech = False
        self.speech_count = 0
        self.queue = asyncio.Queue()
        self.stt_task = None

    async def recv(self):
        frame = await self.track.recv()
        pcm_48k = bytes(frame.planes[0])
        pcm_16k = resample_to_16k(pcm_48k)
        chunk = self.get_chunk(pcm_16k)
        is_speech = self.vad.is_speech(chunk, 16000)

        if is_speech:
            if not self.in_speech and self.stt_task is None:
                logger.debug("🟢 발화 시작")
                self.in_speech = True
                self.queue = asyncio.Queue()
                self.stt_task = asyncio.create_task(self.create_response())

            await self.add_to_queue(pcm_16k)

        elif self.in_speech:
            self.speech_count += 1
            if self.speech_count > 50:  # 50 * 20ms = 1s
                logger.debug("🔴 발화 종료")
                await self.add_to_queue(None)
                self.in_speech = False

        return frame

    async def add_to_queue(self, item):
        if self.in_speech:
            await self.queue.put(item)
            self.speech_count = 0

    def get_chunk(self, pcm: bytes, desired_ms=20):
        target_size = desired_ms * BYTES_PER_MS

        if len(pcm) >= target_size:
            return pcm[:target_size]
        else:
            # 부족하면 zero-padding
            return pcm + bytes(target_size - len(pcm))

    async def generate_pcm_iter(self):
        seq_id = 0
        buffer = bytearray()

        def flush_buffer(buffer, seq_id, final=False):
            joined_pcm = bytes(buffer)
            buffer.clear()
            # save_as_wav(joined_pcm)

            chunk = (joined_pcm, seq_id, False)
            if not final:
                return chunk

            padding = bytes(BYTES_PER_SECOND * 2)
            padded_pcm = joined_pcm + padding
            # save_as_wav(padded)
            return [
                (padded_pcm, seq_id, False),
                (padding, seq_id + 1, True),
                (padding, seq_id + 2, True),
            ]

        while True:
            pcm = await self.queue.get()
            if pcm is None:
                for chunk in flush_buffer(buffer, seq_id, final=True):
                    yield chunk
                break

            buffer.extend(pcm)

            if len(buffer) >= BYTES_PER_SECOND:
                yield flush_buffer(buffer, seq_id)
                seq_id += 1

    async def create_response(self):
        text = await STTService(self.generate_pcm_iter()).run()
        logger.info(f"🗣️  STT 결과: {text}")
