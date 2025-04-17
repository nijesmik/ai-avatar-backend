import asyncio
import logging
from array import array
from os import getenv

import azure.cognitiveservices.speech as speechsdk
import numpy as np

from app.audio.track import AudioTrack
from app.audio.tts_voice import AzureTTSVoiceKorean
from app.audio.utils import WavFileWriter

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class TTSAudioTrack(AudioTrack):
    def __init__(self, text: str):
        super().__init__()
        self.text = text
        self.queue = asyncio.Queue()
        self.buffer = array("h")

        self.speech_config = speechsdk.SpeechConfig(
            subscription=getenv("AZURE_SPEECH_KEY"),
            region=getenv("AZURE_SPEECH_REGION"),
        )
        self.speech_config.speech_synthesis_voice_name = AzureTTSVoiceKorean.InJoon
        self.speech_config.set_speech_synthesis_output_format(
            speechsdk.SpeechSynthesisOutputFormat.Raw48Khz16BitMonoPcm
        )

    async def recv(self):
        pcm = await self.get_pcm(self.samples_per_frame)
        await self.sleep()
        return self.create_frame(pcm)

    async def get_pcm(self, size: int) -> np.ndarray:
        while len(self.buffer) < size:
            chunk = await self.queue.get()
            if chunk is None:
                break
            self.buffer.extend(array("h", chunk))

        pcm = array("h", self.buffer[:size])
        del self.buffer[:size]

        padding = size - len(pcm)
        if padding > 0:
            pcm.extend(array("h", (0 for _ in range(padding))))

        return np.frombuffer(memoryview(pcm), dtype=np.int16)

    async def run_synthesis(self):
        audio_stream = speechsdk.audio.PushAudioOutputStream(_Callback(self.queue))
        audio_config = speechsdk.audio.AudioOutputConfig(stream=audio_stream)
        synthesizer = speechsdk.SpeechSynthesizer(self.speech_config, audio_config)
        future = synthesizer.speak_text_async(self.text)
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


class _Callback(speechsdk.audio.PushAudioOutputStreamCallback):
    def __init__(self, queue: asyncio.Queue, debug=False):
        super().__init__()
        self.queue = queue
        self.loop = asyncio.get_running_loop()
        self.debug = debug
        self.wav = None
        if debug:
            self.wav = WavFileWriter(path_prefix="original")

    def write(self, audio_buffer: memoryview) -> int:
        chunk = audio_buffer.tobytes()
        asyncio.run_coroutine_threadsafe(self.queue.put(chunk), self.loop)

        if self.debug:
            self.wav.write(chunk)

        return len(audio_buffer)

    def close(self):
        asyncio.run_coroutine_threadsafe(self.queue.put(None), self.loop)

        if self.debug:
            self.wav.close()
