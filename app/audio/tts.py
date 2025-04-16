import asyncio
import logging
import time
from fractions import Fraction
from os import getenv

import azure.cognitiveservices.speech as speechsdk
import numpy as np
from aiortc import MediaStreamTrack
from av import AudioFrame

from app.audio.tts_voice import AzureTTSVoiceKorean

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class TTSAudioTrack(MediaStreamTrack):
    kind = "audio"
    _SAMPLE_RATE = 48000
    _SAMPLES_PER_FRAME = 960

    def __init__(self, text: str):
        super().__init__()
        self.text = text
        self.queue = asyncio.Queue()
        self.buffer = np.array([], dtype=np.int16)

        speech_config = speechsdk.SpeechConfig(
            subscription=getenv("AZURE_SPEECH_KEY"),
            region=getenv("AZURE_SPEECH_REGION"),
        )
        speech_config.speech_synthesis_voice_name = AzureTTSVoiceKorean.InJoon
        speech_config.set_speech_synthesis_output_format(
            speechsdk.SpeechSynthesisOutputFormat.Raw48Khz16BitMonoPcm
        )
        self.audio_stream = speechsdk.audio.PushAudioOutputStream(_Callback(self.queue))
        audio_config = speechsdk.audio.AudioOutputConfig(stream=self.audio_stream)
        self.synthesizer = speechsdk.SpeechSynthesizer(speech_config, audio_config)

    async def recv(self):
        pcm = await self.get_pcm(self._SAMPLES_PER_FRAME)

        frame = AudioFrame(format="s16", layout="mono", samples=self._SAMPLES_PER_FRAME)
        frame.sample_rate = self._SAMPLE_RATE
        frame.time_base = Fraction(1, self._SAMPLE_RATE)
        frame.planes[0].update(pcm.tobytes())

        return frame

    async def get_pcm(self, size: int) -> np.ndarray:
        while len(self.buffer) < size:
            chunk = await self.queue.get()
            if chunk is None:
                break
            self.buffer = np.concatenate([self.buffer, chunk])

        pcm = self.buffer[:size]
        self.buffer = self.buffer[size:]

        if len(pcm) < size:
            pcm = np.pad(pcm, (0, size - len(pcm)), mode="constant", constant_values=0)

        return pcm

    async def run_synthesis(self):
        future = self.synthesizer.speak_text_async(self.text)
        result = await asyncio.to_thread(future.get)

        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            logger.debug("Speech synthesized for text [{}]".format(self.text))
        elif result.reason == speechsdk.ResultReason.Canceled:
            cancellation_details = result.cancellation_details
            logger.info(
                "Speech synthesis canceled: {}".format(cancellation_details.reason)
            )
            if cancellation_details.reason == speechsdk.CancellationReason.Error:
                if cancellation_details.error_details:
                    logger.error(
                        "Error details: {}".format(cancellation_details.error_details)
                    )

    async def run(self):
        await self.run_synthesis()


class _Callback(speechsdk.audio.PushAudioOutputStreamCallback):
    def __init__(self, queue: asyncio.Queue):
        super().__init__()
        self.queue = queue
        self.loop = asyncio.get_running_loop()

    def write(self, audio_buffer: memoryview) -> int:
        pcm = np.frombuffer(audio_buffer, dtype=np.int16)
        asyncio.run_coroutine_threadsafe(self.queue.put(pcm), self.loop)

        logger.debug(f"write called with {len(audio_buffer)} bytes")
        return len(audio_buffer)

    def close(self):
        asyncio.run_coroutine_threadsafe(self.queue.put(None), self.loop)
