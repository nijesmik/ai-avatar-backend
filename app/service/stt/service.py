import json
import logging
from os import getenv

import grpc.aio
from google import genai
from google.genai import types

from . import nest_pb2, nest_pb2_grpc

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class STTService:
    _METADATA = (("authorization", f"Bearer {getenv("CLOVA_SPEECH_SECRET_KEY")}"),)
    client = genai.Client(api_key=getenv("GEMINI_API_KEY"))

    def __init__(self):
        self.channel = grpc.aio.secure_channel(
            "clovaspeech-gw.ncloud.com:50051", grpc.ssl_channel_credentials()
        )
        self.stub = nest_pb2_grpc.NestServiceStub(self.channel)

    def __del__(self):
        if self.channel:
            self.channel.close()

    async def close(self):
        if self.channel:
            await self.channel.close()
            self.channel = None
            logger.info("❌ gRPC channel closed")

    def _generate_config(self):
        return nest_pb2.NestRequest(
            type=nest_pb2.RequestType.CONFIG,
            config=nest_pb2.NestConfig(
                config=json.dumps(
                    {
                        "transcription": {
                            "language": "ko",
                        },
                        "semanticEpd": {
                            "useWordEpd": True,
                            "usePeriodEpd": True,
                            "gapThreshold": 2000,
                        },
                    }
                )
            ),
        )

    async def _generate_requests(self, pcm_iter):
        yield self._generate_config()

        async for pcm, seq_id, ep_flag in pcm_iter:
            yield nest_pb2.NestRequest(
                type=nest_pb2.RequestType.DATA,
                data=nest_pb2.NestData(
                    chunk=pcm,
                    extra_contents=json.dumps({"seqId": seq_id, "epFlag": ep_flag}),
                ),
            )

    async def run(self, pcm_iter):
        buffer = []

        try:
            # 서버로부터 응답을 반복 처리
            responses = self.stub.recognize(
                self._generate_requests(pcm_iter), metadata=self._METADATA
            )
            async for response in responses:
                content = json.loads(response.contents)
                transcription = content.get("transcription")
                if not transcription:
                    logger.info(f"response: {content}")
                    continue

                text = transcription.get("text")
                if text:
                    buffer.append(text)
                else:
                    logger.info(f"response: {content}")

        except grpc.aio.AioRpcError as e:
            # gRPC 오류 처리
            logger.error(f"Error: {e.details()}")

        result = "".join(buffer)
        return result

    async def correct_text(self, result: str):
        response = await self.client.aio.models.generate_content(
            model="gemini-2.0-flash-lite",
            contents=result,
            config=types.GenerateContentConfig(
                system_instruction=[
                    "문장의 오타를 수정하고, 문장이 끝나면 어울리는 문장 부호(마침표, 물음표, 느낌표 등)를 자연스럽게 추가해 주세요.",
                    "존댓말과 반말 등 말투는 그대로 유지해 주세요.",
                    "문장을 바꾸거나 해석하지 말고, 최대한 원래 의미를 유지해 주세요.",
                ]
            ),
        )

        return response.text.strip()
