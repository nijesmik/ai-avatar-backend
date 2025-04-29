import socketio

from app.config import allowed_origins

sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins=allowed_origins)
