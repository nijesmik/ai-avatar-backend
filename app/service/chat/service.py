import asyncio

from app.websocket.emit import emit_speech_message

from .message import Messages
from .type import Provider


class ChatService:
    def __init__(self, sid):
        self.sid = sid
        self._emit_task = None

    def _init_messages(
        self, messages: Messages | None, provider: Provider, system_prompt: str = None
    ):
        if not messages:
            return Messages(provider, system_prompt)
        messages.system_prompt = system_prompt
        messages.provider = provider
        return messages

    def emit_message(self, message: str):
        self._emit_task = asyncio.create_task(
            emit_speech_message(self.sid, "model", message)
        )

    async def wait_emit_message(self):
        if self._emit_task:
            await self._emit_task
            self._emit_task = None

    async def send_utterance(self, utterance: str):
        pass

    async def send_message_stream(self, message: str):
        pass
