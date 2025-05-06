import ctypes

import numpy as np

from app.config import RNNOISE_PATH

FRAME_SIZE = 480


# RNNoise 객체 생성
class DenoiseState(ctypes.Structure):
    pass


class RNNoise:
    _frame_size = FRAME_SIZE

    _lib = ctypes.cdll.LoadLibrary(RNNOISE_PATH)
    _lib.rnnoise_create.argtypes = [ctypes.c_void_p]
    _lib.rnnoise_create.restype = ctypes.POINTER(DenoiseState)
    _lib.rnnoise_destroy.argtypes = [ctypes.POINTER(DenoiseState)]
    _lib.rnnoise_process_frame.argtypes = [
        ctypes.POINTER(DenoiseState),
        ctypes.POINTER(ctypes.c_float),
        ctypes.POINTER(ctypes.c_float),
    ]

    def __init__(self):
        self._state = self._lib.rnnoise_create(None)
        if not self._state:
            raise RuntimeError("❌ rnnoise_create returned NULL pointer")

    def __del__(self):
        if self._state:
            self._lib.rnnoise_destroy(self._state)
            self._state = None

    def process(self, input: np.ndarray, time=2):
        assert (
            input.dtype == np.float32
        ), f"RNNoise only supports float32, but got {input.dtype}"

        size = self._frame_size * time
        assert input.shape == (
            size,
        ), f"RNNoise expects input shape of ({size},), but got {input.shape}"

        input = np.ascontiguousarray(input)
        output = np.empty(size, dtype=np.float32)

        for i in range(time):
            offset = i * self._frame_size
            frame_in = input[offset : offset + self._frame_size]
            frame_out = output[offset : offset + self._frame_size]

            assert frame_in.flags.c_contiguous, "Input frame must be C-contiguous"
            assert frame_out.flags.c_contiguous, "Output frame must be C-contiguous"

            ptr_in = frame_in.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
            ptr_out = frame_out.ctypes.data_as(ctypes.POINTER(ctypes.c_float))

            self._lib.rnnoise_process_frame(self._state, ptr_out, ptr_in)

        return output
