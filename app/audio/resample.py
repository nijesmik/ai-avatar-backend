import numpy as np
from scipy.signal import resample_poly


def resample_to_mono(pcm_48k: memoryview, type: np.int16 | np.float32) -> np.ndarray:
    # stereo, 48kHz, 16bit PCM → numpy 배열
    audio_np = np.frombuffer(pcm_48k, dtype=np.int16).reshape(-1, 2)

    # stereo → mono (단순 평균)
    mono = audio_np.mean(axis=1).astype(type)

    return mono


def resample_to_16k(pcm_48k_mono: np.ndarray) -> bytes:
    # 48kHz → 16kHz (다운샘플링)
    resampled = resample_poly(pcm_48k_mono, up=1, down=3)

    # 다시 bytes로 변환
    return resampled.astype(np.int16).tobytes()
