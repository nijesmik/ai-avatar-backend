import asyncio
import logging
from array import array
from os import getenv
from typing import AsyncIterator

import azure.cognitiveservices.speech as speechsdk
import numpy as np

from app.audio.track import AudioTrack
from app.websocket import sio as socket

from .callback import StreamCallback
from .viseme import Viseme
from .voice import SynthesisVoiceKorean

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class TTSAudioTrack(AudioTrack):
    def __init__(self, sid):
        super().__init__()
        self.sid = sid
        self.loop = asyncio.get_running_loop()

        self.queue = asyncio.Queue()
        self.buffer = array("h")
        self.is_pending = asyncio.Event()
        self.is_pending.set()

        self.speech_config = speechsdk.SpeechConfig(
            subscription=getenv("AZURE_SPEECH_KEY"),
            region=getenv("AZURE_SPEECH_REGION"),
        )
        self.set_voice("male")
        self.speech_config.set_speech_synthesis_output_format(
            speechsdk.SpeechSynthesisOutputFormat.Raw48Khz16BitMonoPcm
        )

        self.stream_callback = StreamCallback(self.queue)

    async def recv(self):
        if self.is_pending.is_set():
            logger.debug("💡 TTS is done")
            await self.event.wait()
        pcm = await self.get_pcm(self.samples_per_frame)
        await self.sleep()
        return self.create_frame(pcm)

    async def get_pcm(self, size: int) -> np.ndarray:
        while len(self.buffer) < size:
            chunk = await self.queue.get()
            if chunk is None:
                self.is_pending.set()
                break
            self.buffer.frombytes(chunk)

        read_size = min(len(self.buffer), size)
        view = np.frombuffer(self.buffer, dtype=np.int16)
        pcm = view[:read_size].copy()
        self.buffer = array("h", memoryview(self.buffer)[read_size:])

        if read_size < size:
            padded = np.zeros(size, dtype=np.int16)
            padded[:read_size] = pcm
            return padded

        return pcm

    async def run_synthesis(self, response: AsyncIterator[str]):
        await self.reset_audio()
        self.is_pending.clear()

        async for chunk in response:
            await self._run_synthesis_once(chunk)
            self.emit_viseme(Viseme(animation="", audio_offset=0, viseme_id=-1))
        await self.queue.put(None)
        await self.is_pending.wait()

    async def _run_synthesis_once(self, text: str):
        audio_stream = speechsdk.audio.PushAudioOutputStream(self.stream_callback)
        audio_config = speechsdk.audio.AudioOutputConfig(stream=audio_stream)
        synthesizer = speechsdk.SpeechSynthesizer(self.speech_config, audio_config)
        synthesizer.viseme_received.connect(self.emit_viseme)
        future = synthesizer.speak_text_async(text)
        result = await asyncio.to_thread(future.get)

        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            logger.debug("Speech synthesized for text [{}]".format(text))
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

    def emit_viseme(self, event: speechsdk.SpeechSynthesisVisemeEventArgs):
        asyncio.run_coroutine_threadsafe(
            socket.emit(
                "viseme",
                {
                    "animation": event.animation,
                    "audio_offset": event.audio_offset / 10000,
                    "viseme_id": event.viseme_id,
                },
                to=self.sid,
            ),
            self.loop,
        )

    def set_voice(self, gender: str):
        if gender == "male":
            self.speech_config.speech_synthesis_voice_name = SynthesisVoiceKorean.InJoon
            return
        if gender == "female":
            self.speech_config.speech_synthesis_voice_name = (
                SynthesisVoiceKorean.SunHi
            )
            return
