from enum import Enum
from time import time

import openai

from app.config import GROQ_API_KEY
from app.util.time import log_time

from .service import ChatService

system_instruction_ko = f"""
Assistant는 사용자의 질문에 항상 한국어로 대답합니다. 문장은 짧고 자연스럽게 말하듯이 말합니다. 외래어, 줄임말, 이모지를 사용하지 않습니다. 음성 합성에 적합하도록 모든 단어는 발음하기 쉽게 표현하고, 정확한 문장부호를 사용해 말의 리듬을 자연스럽게 만듭니다.

예시:
사용자: 안녕하세요.
어시스턴트: 안녕하세요. 무엇을 도와드릴까요?

사용자: 오늘 날씨 어때요?
어시스턴트: 오늘은 맑고 선선해요. 산책하기 좋을 것 같아요.
"""

system_instruction_en = f"""
You are a friendly AI avatar having a voice conversation with the user.

Please follow these rules when generating your response:

1. Speak in Korean.
2. DO NOT USE EMOJIS (e.g., 😊, 🤖) or decorative symbols (e.g., ★, ♡).
3. Keep your sentences short and natural — like spoken language.
4. Avoid slang, abbreviations, or foreign words that might confuse speech synthesis.
5. Use proper punctuation like commas and periods for natural rhythm.
6. The response will be spoken using text-to-speech (TTS), so make sure all words are clearly pronounceable.
"""


class GroqAIModel(str, Enum):
    Llama_3Dot1_8b_Instant = "llama-3.1-8b-instant"
    Llama3_8b_8192 = "llama3-8b-8192"
    Gemma2_9b_It = "gemma2-9b-it"


class Groq(ChatService):
    def __init__(self, sid):
        super().__init__(sid)
        self.client = openai.AsyncOpenAI(
            base_url="https://api.groq.com/openai/v1", api_key=GROQ_API_KEY
        )
        self.model = GroqAIModel.Gemma2_9b_It
        self.messages = [{"role": "system", "content": system_instruction_en}]

    async def send_utterance(self, utterance: str):
        self.messages.append({"role": "user", "content": utterance})

        start_time = time()
        response = await self.client.chat.completions.create(
            model=self.model, messages=self.messages
        )
        log_time(start_time, "Groq")

        answer = response.choices[0].message.content
        self.messages.append({"role": "assistant", "content": answer})

        self.emit_message(answer)
        return answer

    async def send_message_stream(self, message: str):
        self.messages.append({"role": "user", "content": message})

        start_time = time()
        stream = await self.client.chat.completions.create(
            model=self.model, messages=self.messages, stream=True
        )

        buffer = []
        async for chunk in stream:
            log_time(start_time, "Groq")
            start_time = None
            answer = chunk.choices[0].delta.content
            yield answer

        self.messages.append({"role": "assistant", "content": "".join(buffer)})
