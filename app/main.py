import logging

import socketio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import allowed_origins
from app.routers import health
from app.websocket import SocketEventHandler, sio

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/v1/health")

handler = SocketEventHandler(sio)

sio.event(handler.connect)
sio.event(handler.disconnect)
sio.event(handler.offer)
sio.event(handler.ice_candidate)
sio.event(handler.voice)
sio.event(handler.message)
sio.event(handler.model)

sio_app = socketio.ASGIApp(sio, other_asgi_app=app)
