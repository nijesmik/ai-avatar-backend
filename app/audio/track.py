import asyncio
import logging
from fractions import Fraction
from time import time

import numpy as np
from aiortc import MediaStreamTrack
from av import AudioFrame
from numpy import ndarray

logger = logging.getLogger(__name__)


class AudioTrack(MediaStreamTrack):
    kind = "audio"

    def __init__(self, sample_rate: int = 48000, samples_per_frame: int = 960):
        super().__init__()
        self.event = asyncio.Event()

        self._sample_rate = sample_rate
        self.time_base = Fraction(1, sample_rate)
        self.samples_per_frame = samples_per_frame

        self._streamed_at = None
        self._started_at = None
        self._timestamp = 0

    async def sleep(self):
        if self._started_at:
            self._timestamp += self.samples_per_frame
            wait = self._started_at + (self._timestamp / self.sample_rate) - time()
            if wait > 0:
                await asyncio.sleep(wait)
        else:
            self._started_at = time()

    def create_frame(self, pcm: ndarray) -> AudioFrame:
        frame = AudioFrame.from_ndarray(pcm.reshape(1, -1), format="s16", layout="mono")
        frame.sample_rate = self.sample_rate
        frame.pts = self._timestamp + self.offset
        frame.time_base = self.time_base
        return frame

    async def recv(self) -> AudioFrame:
        await self.event.wait()

        data = np.zeros(self.samples_per_frame, dtype=np.int16)
        await self.sleep()
        return self.create_frame(data)

    def stop(self):
        self.event.set()
        super().stop()
        logger.info(f"🛑 Track stopped: {self.id}")

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    @sample_rate.setter
    def sample_rate(self, sample_rate: int):
        self._sample_rate = sample_rate
        self.time_base = Fraction(1, sample_rate)

    @property
    def start_time(self) -> float:
        return self._streamed_at or self._started_at or time()

    @start_time.setter
    def start_time(self, start_time: float):
        self._streamed_at = start_time

    @property
    def offset(self) -> int:
        if self._streamed_at and self._started_at:
            offset = int((self._started_at - self._streamed_at) * 48000)
            if offset > 0:
                return offset
        return 0
