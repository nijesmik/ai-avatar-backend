from time import time

from .server import sio


async def emit_speech_message(to, role, message):
    await sio.emit(
        "message",
        {
            "role": role,
            "content": {
                "text": message,
                "type": "speech",
            },
            "time": int(time() * 1000),
        },
        to=to,
    )
