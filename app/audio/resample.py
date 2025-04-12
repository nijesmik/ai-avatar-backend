import numpy as np
from scipy.signal import resample_poly


def resample_to_16k(pcm_48k: bytes) -> bytes:
    # stereo, 48kHz, 16bit PCM → numpy 배열
    audio_np = np.frombuffer(pcm_48k, dtype=np.int16).reshape(-1, 2)

    # stereo → mono (단순 평균)
    mono = audio_np.mean(axis=1).astype(np.int16)

    # 48kHz → 16kHz (다운샘플링)
    resampled = resample_poly(mono, up=1, down=3)

    # 다시 bytes로 변환
    return resampled.astype(np.int16).tobytes()
