import logging
import wave

import numpy as np
from aiortc import MediaStreamError

from app.audio.track import AudioTrack

logger = logging.getLogger(__name__)


class TestAudioTrack(AudioTrack):
    def __init__(self, path):
        super().__init__()
        self.wav = wave.open(path, "rb")
        self.sample_rate = self.wav.getframerate()
        self.channels = self.wav.getnchannels()
        self.width = self.wav.getsampwidth()

    async def recv(self):
        raw = self.wav.readframes(self.samples_per_frame)
        if not raw:
            self.wav.close()
            self.stop()
            raise MediaStreamError("End of stream")

        data = np.frombuffer(raw, dtype=np.int16)
        logger.debug(f"recv called with {len(data) * 2} bytes")

        padding = self.samples_per_frame - len(data)
        if padding > 0:
            data = np.concatenate((data, np.zeros(padding, dtype=np.int16)))

        await self.sleep()
        return self.create_frame(data)
