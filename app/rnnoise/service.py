import ctypes

import numpy as np

from app.config import RNNOISE_PATH

# 라이브러리 로드
lib = ctypes.cdll.LoadLibrary(RNNOISE_PATH)

# RNNoise 객체 생성
lib.rnnoise_create.restype = ctypes.c_void_p
lib.rnnoise_destroy.argtypes = [ctypes.c_void_p]
lib.rnnoise_process_frame.argtypes = [
    ctypes.c_void_p,
    ctypes.POINTER(ctypes.c_float),
    ctypes.POINTER(ctypes.c_float),
]

FRAME_SIZE = 480  # 30ms @ 16kHz


class RNNoiseBuffer:
    _frame_size = FRAME_SIZE

    def __init__(self):
        self.buffer: np.ndarray = None
        self.write_ptr = 0
        self.read_ptr = 0

    def slice(self, pcm: np.ndarray):
        size = self.size + len(pcm)
        if size < self._frame_size:
            self.buffer = pcm
            self.write_ptr = len(pcm)
            self.read_ptr = 0
            return None
        else:
            chunk = np.empty(self._frame_size, dtype=np.float32)
            chunk[: self.size] = self.buffer[self.read_ptr : self.write_ptr]
            read_size = self._frame_size - self.size
            chunk[self.size :] = pcm[:read_size]
            self.buffer = pcm
            self.write_ptr = len(pcm)
            self.read_ptr = read_size
            return chunk

    @property
    def size(self):
        return self.write_ptr - self.read_ptr


class RNNoise:
    _frame_size = FRAME_SIZE

    def __init__(self):
        self._state = lib.rnnoise_create()
        self._buffer = RNNoiseBuffer()

    def __del__(self):
        if self._state:
            lib.rnnoise_destroy(self._state)
            self._state = None

    def process(self, input: np.ndarray, time=2):
        assert (
            input.dtype == np.float32
        ), f"RNNoise only supports float32, but got {input.dtype}"

        size = self._frame_size * time
        assert input.shape == (
            size,
        ), f"RNNoise expects input shape of ({size},), but got {input.shape}"

        output = np.empty(size, dtype=np.float32)

        for i in range(time):
            offset = i * self._frame_size
            frame_in = input[offset : offset + self._frame_size]
            frame_out = output[offset : offset + self._frame_size]

            ptr_in = frame_in.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
            ptr_out = frame_out.ctypes.data_as(ctypes.POINTER(ctypes.c_float))

            lib.rnnoise_process_frame(self._state, ptr_out, ptr_in)

        return output

    def _deprecated(self, pcm: np.ndarray):
        input = self._buffer.slice(pcm)
        if input is None:
            return None

        input_ptr = input.ctypes.data_as(ctypes.POINTER(ctypes.c_float))

        output = np.zeros(self._frame_size, dtype=np.float32)
        output_ptr = output.ctypes.data_as(ctypes.POINTER(ctypes.c_float))

        lib.rnnoise_process_frame(self._state, output_ptr, input_ptr)

        return output.astype(np.int16).tobytes()
