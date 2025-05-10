from dataclasses import dataclass

from .type import Provider

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

    def to_dict(self, provider: Provider) -> dict:
        if provider is Provider.Google:
            return {
                "role": ROLE_MAP[provider][self.role],
                "parts": [{"text": self.content}],
            }

        return {"role": self.role, "content": self.content}


class Messages:
    def __init__(self, provider: Provider, system_prompt: str = None):
        self.messages: list[Message] = []
        self._provider = provider
        self._system_prompt = system_prompt
        self._cache = self._init_cache()

    def _init_cache(self) -> list[dict]:
        cache = []
        if self._system_prompt and self._provider is Provider.Groq:
            cache.append({"role": "system", "content": self._system_prompt})
        return cache

    def add(self, role: str, content: str):
        message = Message(role, content)
        self.messages.append(message)
        self._cache.append(message.to_dict(self._provider))

    def add_user_input(self, input: str):
        self.add("user", input)

    def add_model_output(self, output: str):
        self.add("assistant", output)

    def get(self):
        return self._cache

    @property
    def provider(self) -> Provider:
        return self._provider

    @provider.setter
    def provider(self, provider: Provider):
        self._provider = provider
        self._cache = self._init_cache()
        self._cache.extend(message.to_dict(self._provider) for message in self.messages)

    @property
    def system_prompt(self) -> str:
        return self._system_prompt

    @system_prompt.setter
    def system_prompt(self, system_prompt: str):
        self._system_prompt = system_prompt
