import asyncio
import logging
from time import time

import webrtcvad
from aiortc.mediastreams import MediaStreamError
from aiortc.rtcrtpreceiver import RemoteStreamTrack

from app.audio.resample import resample_to_16k
from app.audio.utils import save_as_wav
from app.service.stt import STTService

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# 1ms 당 PCM 데이터: 16kHz => 16 samples/ms, each sample 2 bytes -> 16*2 = 32 bytes/ms.
BYTES_PER_MS = 16 * 2
BYTES_PER_SECOND = BYTES_PER_MS * 1000


class AudioReceiver:
    def __init__(
        self,
        track: RemoteStreamTrack,
        sid,
        on_stt_finished,
    ):
        super().__init__()
        self.track = track
        self.sid = sid

        self.vad = webrtcvad.Vad(3)
        self.in_speech = False
        self.speech_count = 0
        self.queue = asyncio.Queue()

        self.response_task = None
        self.stt_service = STTService()
        self.stt_finished_callback = on_stt_finished

        self.speech_end_time = None

    async def recv(self):
        try:
            while True:
                frame = await self.track.recv()
                pcm_48k = memoryview(frame.planes[0])
                pcm_16k = resample_to_16k(pcm_48k)
                await self.detect_speech(pcm_16k)

        except MediaStreamError:
            logger.info(f"❌ MediaStream 종료: {self.sid}")

    async def detect_speech(self, pcm: bytes):
        chunk = self.get_chunk(pcm)
        is_speech = self.vad.is_speech(chunk, 16000)

        if is_speech:
            if not self.in_speech:
                self.in_speech = True
                self.queue = asyncio.Queue()

            if (
                self.response_task is None
                and self.queue.qsize() > 10  # 20ms * 10 = 200ms
            ):
                self.response_task = asyncio.create_task(self.create_response())

            await self.add_to_queue(pcm)

        elif self.in_speech:
            self.speech_count += 1
            if self.speech_count > 40:  # 40 * 20ms = 800ms
                self.speech_end_time = time()
                await self.add_to_queue(None)
                self.in_speech = False

    async def add_to_queue(self, item):
        if self.in_speech:
            await self.queue.put(item)
            self.speech_count = 0

    def get_chunk(self, pcm: bytes, desired_ms=20):
        target_size = desired_ms * BYTES_PER_MS

        if len(pcm) >= target_size:
            return memoryview(pcm)[:target_size]

        chunk = bytearray(target_size)
        chunk[: len(pcm)] = pcm
        return chunk

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

            if len(buffer) >= BYTES_PER_SECOND / 4:
                yield flush_buffer(buffer, seq_id)
                seq_id += 1

    async def create_response(self):
        logger.debug("🟣 응답 생성 시작")
        text = await self.stt_service.run(self.generate_pcm_iter())
        logger.debug(f"🗣️  STT time: {(time() - self.speech_end_time) * 1000:.2f}ms")

        try:
            if text:
                await self.stt_finished_callback(text)
        finally:
            self.response_task = None

    async def cancel(self):
        self.track.stop()

        if self.response_task:
            self.response_task.cancel()
            try:
                await self.response_task
            except asyncio.CancelledError:
                logger.info(f"❌ 응답 생성 취소: {self.sid}")

        await self.stt_service.close()
