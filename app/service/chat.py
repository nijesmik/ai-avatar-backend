import asyncio
import logging
import re
from os import getenv
from time import time

from google import genai

from app.util.time import log_time
from app.websocket.emit import emit_speech_message

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

system_instruction = f"""
You are a friendly AI avatar having a voice conversation with the user.

Please follow these rules when generating your response:

1. Do not use emojis (e.g., 😊, 🤖) or decorative symbols (e.g., ★, ♡).
2. Keep your sentences short and natural — like spoken language.
3. Avoid slang, abbreviations, or foreign words that might confuse speech synthesis.
4. Use proper punctuation like commas and periods for natural rhythm.
5. The response will be spoken using text-to-speech (TTS), so make sure all words are clearly pronounceable.
"""


class ChatService:
    client = genai.Client(api_key=getenv("GEMINI_API_KEY"))
    regex = re.compile(r"(.*?[\.!?])(\s+|$)")

    def __init__(self, sid):
        self.chat = self.create_voice_chat_model()
        self.sid = sid
        self._emit_task = None

    def create_voice_chat_model(self):
        return self.client.aio.chats.create(
            model="gemini-2.0-flash-lite",
            config={
                "system_instruction": system_instruction,
            },
        )

    async def send_message(self, message: str):
        response = await self.chat.send_message_stream(
            message,
        )

        async for chunk in response:
            logger.debug(f"💬 text: {chunk.text}")
            yield chunk.text

    async def send_utterance_stream(self, utterance: str):
        start_time = time()
        response = await self.chat.send_message_stream(utterance)
        result = []
        buffer = ""

        async for chunk in response:
            result.append(chunk.text)
            buffer += chunk.text

            match = self.regex.match(buffer)
            if match:
                log_time(start_time, "LLM")
                start_time = None
                yield match.group(1).strip()
                buffer = buffer[match.end() :]

        while buffer:
            match = self.regex.match(buffer)
            if not match:
                break

            yield match.group(1)
            buffer = buffer[match.end() :]

        self._emit_task = asyncio.create_task(
            emit_speech_message(self.sid, "model", "".join(result))
        )

    async def send_utterance(self, utterance: str):
        start_time = time()
        response = await self.chat.send_message(utterance)
        log_time(start_time, "LLM")

        self._emit_task = asyncio.create_task(
            emit_speech_message(self.sid, "model", response.text)
        )
        return response.text

    async def wait_emit_task(self):
        if self._emit_task:
            await self._emit_task
            self._emit_task = None
