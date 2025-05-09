from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict


class Provider(Enum):
    Google = auto()
    Groq = auto()


ROLE_MAP = {
    Provider.Google: {
        "user": "user",
        "assistant": "model",
    },
}


@dataclass
class Message:
    role: str
    content: str
    _cache: Dict[Provider, Dict] = field(default_factory=dict, init=False, repr=False)

    def to_dict(self, provider: Provider) -> dict:
        if provider in self._cache:
            return self._cache[provider]

        if provider is Provider.Google:
            self._cache[provider] = {
                "role": ROLE_MAP[provider][self.role],
                "parts": [{"text": self.content}],
            }
        else:  # Provider.OPENAI
            self._cache[provider] = {"role": self.role, "content": self.content}

        return self._cache[provider]


class Messages:
    def __init__(self, provider: Provider):
        self.messages: list[Message] = []
        self._provider = provider
        self._system_prompt = None

    def add(self, role: str, content: str):
        message = Message(role, content)
        self.messages.append(message)

    def get(self) -> list:
        messages = []
        if self.system_prompt and self._provider is Provider.Groq:
            messages.append({"role": "system", "content": self._system_prompt})
        messages.extend(message.to_dict(self._provider) for message in self.messages)
        return messages

    @property
    def provider(self) -> Provider:
        return self._provider

    @provider.setter
    def provider(self, provider: Provider):
        self._provider = provider

    @property
    def system_prompt(self) -> str:
        return self._system_prompt

    @system_prompt.setter
    def system_prompt(self, system_prompt: str):
        self._system_prompt = system_prompt
