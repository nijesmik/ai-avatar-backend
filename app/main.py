import logging
from os import getenv

import socketio
from dotenv import load_dotenv
from fastapi import FastAPI

from app.connection.websocket import SocketEventHandler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()
allowed_origins = getenv("ALLOWED_ORIGINS", "*").split(",")
logger.info(f"Allowed origins: {allowed_origins}")

app = FastAPI()
sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins=allowed_origins)

handler = SocketEventHandler(sio)

sio.event(handler.connect)
sio.event(handler.disconnect)
sio.event(handler.offer)
sio.event(handler.ice_candidate)

sio_app = socketio.ASGIApp(sio, other_asgi_app=app)
