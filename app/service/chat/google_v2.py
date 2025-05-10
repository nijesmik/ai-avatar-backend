from time import time

from google import genai

from app.config import GEMINI_API_KEY
from app.util.time import log_time

from .google import system_instruction
from .message import Messages
from .service import ChatService
from .type import ModelList, Provider


class Google(ChatService):
    api_key = GEMINI_API_KEY
    config = {
        "system_instruction": system_instruction,
    }

    def __init__(self, sid, messages: Messages = None):
        super().__init__(sid)
        self.client = genai.Client(api_key=self.api_key)
        self.messages = self._init_messages(messages, Provider.Google)
        self.model = ModelList.Google.Gemini_2_Flash_Lite

    async def send_message_stream(self, message: str):
        self.messages.add("user", message)

        start_time = time()
        response = await self.client.aio.models.generate_content_stream(
            model=self.model,
            contents=self.messages.get(),
            config=self.config,
        )

        buffer = []
        async for chunk in response:
            log_time(start_time, "Google")
            start_time = None
            yield chunk.text
            buffer.append(chunk.text)

        self.messages.add("assistant", "".join(buffer))

    async def send_utterance(self, utterance: str):
        self.messages.add("user", utterance)

        start_time = time()
        response = await self.client.aio.models.generate_content(
            model=self.model,
            contents=self.messages.get(),
            config=self.config,
        )
        log_time(start_time, "Google")

        self.messages.add("assistant", response.text)
        self.emit_message(response.text)
        return response.text
