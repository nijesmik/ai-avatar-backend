import asyncio
import logging

import azure.cognitiveservices.speech as speechsdk

from app.audio.utils import WavFileWriter

logger = logging.getLogger(__name__)


class StreamCallback(speechsdk.audio.PushAudioOutputStreamCallback):
    def __init__(self, queue: asyncio.Queue, debug=False):
        super().__init__()
        self.queue = queue
        self.loop = asyncio.get_running_loop()
        self.debug = debug
        self.wav = None
        if debug:
            self.wav = WavFileWriter(path_prefix="original")

    def write(self, audio_buffer: memoryview) -> int:
        chunk = audio_buffer.tobytes()
        asyncio.run_coroutine_threadsafe(self.queue.put(chunk), self.loop)

        if self.debug:
            self.wav.write(chunk)

        return len(audio_buffer)

    def close(self):
        # asyncio.run_coroutine_threadsafe(self.queue.put(None), self.loop)
        logger.info("🚪 TTS stream closed")

        if self.debug:
            self.wav.close()
