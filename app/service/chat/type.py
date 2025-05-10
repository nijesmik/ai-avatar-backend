from enum import Enum, auto


class Provider(Enum):
    Google = auto()
    Groq = auto()


class Model(str, Enum):
    def equal(self, model) -> bool:
        if isinstance(model, Model):
            return self.value == model.value
        return self.value == model

    @classmethod
    def provider(cls) -> Provider:
        return Provider[cls.__name__]


class ModelList:
    class Google(Model):
        Gemini_2_Flash = "gemini-2.0-flash"
        Gemini_2_Flash_Lite = "gemini-2.0-flash-lite"
        Gemini_1Dot5_Flash_8b = "gemini-1.5-flash-8b"

    class Groq(Model):
        Llama_3Dot1_8b_Instant = "llama-3.1-8b-instant"
        Llama3_8b_8192 = "llama3-8b-8192"
        Gemma2_9b_It = "gemma2-9b-it"
