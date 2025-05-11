import asyncio
import logging

import azure.cognitiveservices.speech as speechsdk

from app.audio.utils import WavFileWriter

logger = logging.getLogger(__name__)


class StreamCallback(speechsdk.audio.PushAudioOutputStreamCallback):
    def __init__(self, queue: asyncio.Queue):
        super().__init__()
        self.queue = queue
        self.loop = asyncio.get_running_loop()
        # self.wav = WavFileWriter(path_prefix="original")

    def write(self, audio_buffer: memoryview) -> int:
        chunk = audio_buffer.tobytes()
        asyncio.run_coroutine_threadsafe(self.queue.put(chunk), self.loop)

        # self.wav.write(chunk)

        return len(audio_buffer)

    def close(self):
        logger.info("🚪 TTS stream closed")

        # self.wav.close()
