import asyncio
from fractions import Fraction
from time import time

from aiortc import MediaStreamTrack
from av import AudioFrame
from numpy import ndarray
import logging

logger = logging.getLogger(__name__)

class AudioTrack(MediaStreamTrack):
    kind = "audio"

    def __init__(self, sample_rate: int = 48000, samples_per_frame: int = 960):
        super().__init__()
        self.sample_rate = sample_rate
        self.samples_per_frame = samples_per_frame

        self._start = None
        self._timestamp = 0

    async def sleep(self):
        if self._start:
            self._timestamp += self.samples_per_frame
            wait = self._start + (self._timestamp / self.sample_rate) - time()
            if wait > 0:
                logger.debug(f"Sleeping for {wait:.4f} seconds")
                await asyncio.sleep(wait)
        else:
            self._start = time()

    def create_frame(self, pcm: ndarray) -> AudioFrame:
        frame = AudioFrame.from_ndarray(pcm.reshape(1, -1), format="s16", layout="mono")
        frame.sample_rate = self.sample_rate
        frame.pts = self._timestamp
        frame.time_base = Fraction(1, self.sample_rate)
        return frame
