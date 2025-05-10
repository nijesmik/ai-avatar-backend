import logging
import re
from enum import Enum
from os import getenv
from time import time

from google import genai

from app.util.time import log_time

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


class GoogleAIModel(str, Enum):
    Gemini_2_Flash = "gemini-2.0-flash"
    Gemini_2_Flash_Lite = "gemini-2.0-flash-lite"
    Gemini_1Dot5_Flash_8b = "gemini-1.5-flash-8b"


class Google:
    client = genai.Client(api_key=getenv("GEMINI_API_KEY"))
    regex = re.compile(r"(.*?[\.!?])(\s+|$)")

    def __init__(self):
        self.chat = self.create_voice_chat_model()

    def create_voice_chat_model(self):
        return self.client.aio.chats.create(
            model=GoogleAIModel.Gemini_2_Flash_Lite,
            config={
                "system_instruction": system_instruction,
            },
        )

    async def send_message_stream(self, message: str):
        start_time = time()
        response = await self.chat.send_message_stream(
            message,
        )

        async for chunk in response:
            log_time(start_time, "Google")
            start_time = None
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
                log_time(start_time, "Google")
                start_time = None
                yield match.group(1).strip()
                buffer = buffer[match.end() :]

        while buffer:
            match = self.regex.match(buffer)
            if not match:
                break

            yield match.group(1)
            buffer = buffer[match.end() :]

    async def send_utterance(self, utterance: str):
        start_time = time()
        response = await self.chat.send_message(utterance)
        log_time(start_time, "Google")

        return response.text
