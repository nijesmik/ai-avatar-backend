import asyncio
import logging
from time import time

import numpy as np
import webrtcvad
from aiortc.mediastreams import MediaStreamError
from aiortc.rtcrtpreceiver import RemoteStreamTrack

from app.audio.resample import resample_to_16k, resample_to_mono
from app.rnnoise import RNNoise
from app.service.stt import STTService
from app.util.time import log_time

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# 1ms 당 PCM 데이터: 16kHz => 16 samples/ms, each sample 2 bytes -> 16*2 = 32 bytes/ms.
BYTES_PER_MS = 16 * 2
BYTES_PER_SECOND = BYTES_PER_MS * 1000
MAX_BUFFER_SIZE = BYTES_PER_MS * 200  # 200ms
LAST_CHUNK_SIZE = BYTES_PER_MS * 500

UNIT_PCM_CHUNK_TIME = 20  # 20ms
VAD_SIZE = BYTES_PER_MS * UNIT_PCM_CHUNK_TIME
TASK_RUN_THRESHOLD = 300 // UNIT_PCM_CHUNK_TIME
SPEECH_END_THRESHOLD = 300 // UNIT_PCM_CHUNK_TIME


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

        self.rnnoise = RNNoise()
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
                mono = resample_to_mono(pcm_48k, np.float32)
                denoised = self.rnnoise.process(mono)
                pcm_16k = resample_to_16k(denoised)
                await self.detect_speech(pcm_16k)

        except MediaStreamError:
            logger.info(f"❌ MediaStream 종료: {self.sid}")

    async def detect_speech(self, pcm: bytes):
        chunk = self.get_vad_chunk(pcm)
        is_speech = self.vad.is_speech(chunk, 16000)

        await self.queue.put(pcm)

        if is_speech:
            self.speech_count = 0
            if not self.in_speech:
                self.in_speech = True

            if (
                self.response_task is None
                and self.queue.qsize() > TASK_RUN_THRESHOLD + 5
            ):
                self.response_task = asyncio.create_task(self.create_response())

            return

        if self.in_speech:
            self.speech_count += 1
            if self.speech_count > SPEECH_END_THRESHOLD:
                await self.on_sppeech_end()
                self.queue = asyncio.Queue()
            return

        if self.queue.qsize() > 5:
            await self.queue.get()

    def get_vad_chunk(self, pcm: bytes):
        pcm_size = len(pcm)
        if pcm_size == VAD_SIZE:
            return pcm
        if pcm_size > VAD_SIZE:
            return memoryview(pcm)[:VAD_SIZE]

        chunk = bytearray(VAD_SIZE)
        chunk[:pcm_size] = pcm
        return chunk

    async def generate_pcm_iter(self):
        seq_id = 0
        buffer = bytearray()

        def flush_buffer(buffer, seq_id, final=False):
            if final:
                padding = max(0, LAST_CHUNK_SIZE - len(buffer))
                buffer.extend(bytes(padding))

            joined_pcm = bytes(buffer)
            buffer.clear()

            chunk = (joined_pcm, seq_id, False)
            return chunk

        while True:
            pcm = await self.queue.get()
            if pcm is None:
                yield flush_buffer(buffer, seq_id, final=True)
                silence = bytes(BYTES_PER_SECOND * 2)
                for i in range(1, 3):
                    yield (silence, seq_id + i, True)
                return

            buffer.extend(pcm)

            if len(buffer) >= MAX_BUFFER_SIZE:
                yield flush_buffer(buffer, seq_id)
                seq_id += 1

    async def create_response(self):
        result = await self.stt_service.run(self.generate_pcm_iter())

        log_time(self.speech_end_time, "STT")
        self.speech_end_time = None

        if result.success and not result.text:
            return

        await self.stt_finished_callback(result)

    async def cancel(self):
        self.track.stop()

        if self.response_task:
            self.response_task.cancel()
            try:
                await self.response_task
            except asyncio.CancelledError:
                logger.info(f"❌ 응답 생성 취소: {self.sid}")

        await self.stt_service.close()

    async def on_sppeech_end(self):
        await self.queue.put(None)
        self.speech_end_time = time()
        self.in_speech = False

        if self.response_task:
            await self.response_task
            self.response_task = None
