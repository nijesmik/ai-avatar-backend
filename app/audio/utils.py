import os
import wave
from datetime import datetime


def save_as_wav(
    pcm: bytes, path_prefix="output", sample_rate=16000, directory=".recordings"
):
    os.makedirs(directory, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    path = os.path.join(directory, f"{path_prefix}_{timestamp}.wav")

    with wave.open(path, "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)  # 16-bit PCM = 2 bytes
        f.setframerate(sample_rate)
        f.writeframes(pcm)

    return path  # 저장된 경로 반환
