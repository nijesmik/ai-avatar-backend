import asyncio
import logging
from array import array
from os import getenv
from time import time
from typing import AsyncIterator

import azure.cognitiveservices.speech as speechsdk
import numpy as np

from app.audio.track import AudioTrack
from app.util.time import log_time
from app.websocket import sio as socket

from .callback import StreamCallback
from .viseme import Viseme
from .voice import SynthesisVoiceKorean

logger = logging.getLogger(__name__)


class TTSAudioTrack(AudioTrack):
    def __init__(self, sid, voice: SynthesisVoiceKorean):
        super().__init__()
        self.sid = sid
        self.loop = asyncio.get_running_loop()

        self.queues = asyncio.Queue()
        self.current_queue: asyncio.Queue = None
        self.buffer = array("h")
        self.is_pending = asyncio.Event()
        self.is_pending.set()
        self.is_first_queue = False

        self.speech_config = speechsdk.SpeechConfig(
            subscription=getenv("AZURE_SPEECH_KEY"),
            region=getenv("AZURE_SPEECH_REGION"),
        )
        self.voice = voice
        self.speech_config.set_speech_synthesis_output_format(
            speechsdk.SpeechSynthesisOutputFormat.Raw48Khz16BitMonoPcm
        )

        self.start_time = None

    async def recv(self):
        if self.is_pending.is_set():
            await self.event.wait()
        pcm = await self.get_pcm(self.samples_per_frame)
        await self.sleep()
        log_time(self.start_time, "TTS")
        self.start_time = None
        return self.create_frame(pcm)

    async def _handle_chunk(self, chunk: bytes):
        if chunk is not None:
            self.buffer.frombytes(chunk)
            return

        queue = await self.queues.get()
        if queue is None:
            self.is_pending.set()
            return True

        self.current_queue = queue
        return

    async def get_pcm(self, size: int) -> np.ndarray:
        while len(self.buffer) < size:
            chunk = await self.current_queue.get()
            if await self._handle_chunk(chunk):
                break

        if not self.buffer:
            return np.zeros(size, dtype=np.int16)

        read_size = min(len(self.buffer), size)
        view = np.frombuffer(self.buffer, dtype=np.int16)
        pcm = view[:read_size].copy()
        self.buffer = array("h", memoryview(self.buffer)[read_size:])

        if read_size < size:
            padded = np.zeros(size, dtype=np.int16)
            padded[:read_size] = pcm
            return padded

        qsize = self.current_queue.qsize()
        if np.all(pcm == 0) and qsize < 8:
            return await self.get_pcm(size)

        return pcm

    async def run_synthesis(self, response: AsyncIterator[str]):
        self.current_queue = asyncio.Queue()
        self.is_first_queue = True
        await self.reset_audio()
        self.is_pending.clear()

        self.start_time = True
        async for chunk in response:
            if self.start_time:
                self.start_time = time()
            await self._run_synthesis_once(chunk)

        await self.queues.put(None)
        await self.is_pending.wait()

    async def _get_queue(self):
        if self.is_first_queue:
            self.is_first_queue = False
            return self.current_queue
        queue = asyncio.Queue()
        await self.queues.put(queue)
        return queue

    async def _run_synthesis_once(self, text: str):
        queue = await self._get_queue()
        self.stream_callback = StreamCallback(queue)

        audio_stream = speechsdk.audio.PushAudioOutputStream(self.stream_callback)
        audio_config = speechsdk.audio.AudioOutputConfig(stream=audio_stream)
        synthesizer = speechsdk.SpeechSynthesizer(self.speech_config, audio_config)
        synthesizer.viseme_received.connect(self.emit_viseme)
        future = synthesizer.speak_text_async(text)
        result = await asyncio.to_thread(future.get)
        await queue.put(None)

        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            # logger.debug("Speech synthesized for text [{}]".format(text))
            self.emit_viseme(Viseme(animation="", audio_offset=0, viseme_id=-1))
            return

        if result.reason == speechsdk.ResultReason.Canceled:
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

    @property
    def voice(self):
        return self.speech_config.speech_synthesis_voice_name

    @voice.setter
    def voice(self, voice: SynthesisVoiceKorean):
        self.speech_config.speech_synthesis_voice_name = voice
