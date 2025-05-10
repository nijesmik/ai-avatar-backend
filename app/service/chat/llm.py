from abc import ABC, abstractmethod

from .message import Messages
from .type import Provider


class LLMService(ABC):
    def _init_messages(
        self, messages: Messages | None, provider: Provider, system_prompt: str = None
    ):
        if not messages:
            return Messages(provider, system_prompt)
        messages.system_prompt = system_prompt
        messages.provider = provider
        return messages

    @abstractmethod
    async def send_message(self, utterance: str):
        pass

    @abstractmethod
    async def send_message_stream(self, message: str):
        pass
