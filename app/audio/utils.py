import logging
import os
import wave
from datetime import datetime

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class WavFileWriter:
    def __init__(
        self, path_prefix="output", sample_rate=48000, directory=".recordings"
    ):
        os.makedirs(directory, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        self.path = os.path.join(directory, f"{path_prefix}_{timestamp}.wav")

        self._wav = wave.open(self.path, "wb")
        self._wav.setnchannels(1)
        self._wav.setsampwidth(2)  # 16-bit PCM = 2 bytes
        self._wav.setframerate(sample_rate)

        self.closed = False

    def write(self, data):
        self._wav.writeframes(data)

    def close(self):
        self._wav.close()
        self.closed = True
        logger.debug(f"WAV 파일 저장 완료: {self.path}")


def save_as_wav(
    pcm: bytes, path_prefix="output", sample_rate=16000, directory=".recordings"
):
    wav = WavFileWriter(path_prefix, sample_rate, directory)
    wav.write(pcm)
    wav.close()

    return wav.path  # 저장된 경로 반환
