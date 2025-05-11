import asyncio
import logging
import re

from app.websocket.emit import emit_speech_message

from .google_v2 import Google
from .groq import Groq
from .type import Model, Provider

logger = logging.getLogger(__name__)


class ChatService:
    LAST_PUNCTUATION_PATTERN = re.compile(r"[.?!](?!.*[.?!])\s*")
    PUNCTUATION_WITH_SPACES_PATTERN = re.compile(r"^\s+|([,.!?])\s+")

    def __init__(self, sid):
        self.sid = sid
        self.llm = Groq()
        self.messages = self.llm.messages
        self._emit_task = None

    def change_model(self, model: Model):
        provider = model.provider()

        if self.llm.model.provider() == provider:
            self.llm.model = model
            return

        if provider == Provider.Google:
            self.llm = Google(self.messages, model)
        elif provider == Provider.Groq:
            self.llm = Groq(self.messages)

    def _emit_response(self, message: str):
        self._emit_task = asyncio.create_task(
            emit_speech_message(self.sid, "model", message)
        )

    async def wait_emit_message(self):
        if self._emit_task:
            await self._emit_task
            self._emit_task = None

    async def send_utterance(self, utterance: str):
        try:
            response = await self.llm.send_message(utterance)
            self._emit_response(response)
            result = self.PUNCTUATION_WITH_SPACES_PATTERN.sub(r"\1", response)

        except Exception as e:
            logger.error(f"⚠️ LLM Error: {e}")
            result = "서버 오류가 발생했습니다.잠시 후 다시 시도해 주세요."

        yield result

    async def send_utterance_stream(self, utterance: str):
        try:
            response = self.llm.send_message_stream(utterance)

            buffer = ""
            async for chunk in response:
                buffer += chunk
                result, buffer = self._slice_sentences(buffer)
                if result:
                    yield result

            while buffer:
                result, buffer = self._slice_sentences(buffer)
                if not result:
                    break
                yield result

            self._emit_response(self.messages.last_message.content)

        except Exception as e:
            logger.error(f"⚠️ LLM Error: {e}")
            self.messages.pop()
            yield "서버 오류가 발생했습니다.잠시 후 다시 시도해 주세요."

    def _slice_sentences(self, buffer: str):
        match = self.LAST_PUNCTUATION_PATTERN.search(buffer)
        if not match:
            return (None, buffer)

        end_index = match.end()
        result = self.PUNCTUATION_WITH_SPACES_PATTERN.sub(r"\1", buffer[:end_index])
        return (result, buffer[end_index:])
