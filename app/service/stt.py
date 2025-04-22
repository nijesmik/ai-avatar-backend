import json
import logging
from os import getenv

import grpc.aio

import nest_pb2
import nest_pb2_grpc

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class STTService:
    _METADATA = (("authorization", f"Bearer {getenv("CLOVA_SPEECH_SECRET_KEY")}"),)

    def __init__(self):
        self._pcm_iter = None

    async def _generate_requests(self):
        yield nest_pb2.NestRequest(
            type=nest_pb2.RequestType.CONFIG,
            config=nest_pb2.NestConfig(
                config=json.dumps({"transcription": {"language": "ko"}})
            ),
        )

        async for pcm, seq_id, ep_flag in self._pcm_iter:
            logger.debug(f"seq_id: {seq_id}, ep_flag: {ep_flag}")
            yield nest_pb2.NestRequest(
                type=nest_pb2.RequestType.DATA,
                data=nest_pb2.NestData(
                    chunk=pcm,
                    extra_contents=json.dumps({"seqId": seq_id, "epFlag": ep_flag}),
                ),
            )

    async def run(self, pcm_iter):
        self._pcm_iter = pcm_iter

        channel = grpc.aio.secure_channel(
            "clovaspeech-gw.ncloud.com:50051", grpc.ssl_channel_credentials()
        )
        stub = nest_pb2_grpc.NestServiceStub(channel)

        stt = []

        try:
            # 서버로부터 응답을 반복 처리
            responses = stub.recognize(
                self._generate_requests(), metadata=self._METADATA
            )
            async for response in responses:
                content = json.loads(response.contents)
                transcription = content.get("transcription")
                if not transcription:
                    logger.info(f"response: {content}")
                    continue

                text = transcription.get("text")
                if text:
                    stt.append(text)
                    logger.debug(f"🔹 Partial: {text}")
                else:
                    logger.info(f"response: {content}")

        except grpc.aio.AioRpcError as e:
            # gRPC 오류 처리
            logger.error(f"Error: {e.details()}")
        finally:
            await channel.close()  # 작업이 끝나면 채널 닫기

        if not stt[-1].endswith((".", "!", "?")):
            stt[-1] += "."

        return "".join(stt)
