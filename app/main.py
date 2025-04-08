import logging
from dotenv import load_dotenv
from os import getenv
from fastapi import FastAPI
import socketio
from app.routers import websocket

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()
allowed_origins = getenv("ALLOWED_ORIGINS", "*").split(",")
logger.info(f"Allowed origins: {allowed_origins}")

app = FastAPI()
sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins=allowed_origins)

websocket.register_handlers(sio)

sio_app = socketio.ASGIApp(sio, other_asgi_app=app)
