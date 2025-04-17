import logging
import wave

import numpy as np
from aiortc import MediaStreamError, MediaStreamTrack
from av import AudioFrame

logger = logging.getLogger(__name__)


class AudioTestTrack(MediaStreamTrack):
    kind = "audio"

    def __init__(self, path):
        super().__init__()
        self.wav = wave.open(path, "rb")
        self.rate = self.wav.getframerate()
        self.channels = self.wav.getnchannels()
        self.width = self.wav.getsampwidth()
        self.timestamp = 0

    async def recv(self):
        raw = self.wav.readframes(960)
        if not raw:
            self.wav.close()
            self.stop()
            raise MediaStreamError("End of stream")

        data = np.frombuffer(raw, dtype=np.int16)
        logger.debug(f"recv called with {len(data) * 2} bytes")

        frame = AudioFrame(format="s16", layout="mono", samples=len(data))
        frame.pts = self.timestamp
        frame.sample_rate = self.rate
        frame.planes[0].update(data.tobytes())
        self.timestamp += 960
        return frame
