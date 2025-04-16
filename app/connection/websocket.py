import logging
from socketio import AsyncServer
from aiortc import RTCSessionDescription, RTCIceCandidate
from app.connection.webrtc import PeerConnectionManager

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class SocketEventHandler:
    def __init__(self, sio: AsyncServer):
        self.sio = sio
        self.peer_connection_manager = PeerConnectionManager(sio)

    async def connect(self, sid, environ):
        logger.info(f"🔌 Connected: {sid}")

    async def disconnect(self, sid):
        logger.info(f"❌ Disconnected: {sid}")
        await self.peer_connection_manager.remove(sid)

    async def offer(self, sid, data):
        pc = await self.peer_connection_manager.create(sid)

        offer = RTCSessionDescription(sdp=data["sdp"], type=data["type"])
        await pc.setRemoteDescription(offer)
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)

        await self.sio.emit(
            "answer",
            {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type},
            to=sid,
        )

    async def ice_candidate(self, sid, data):
        candidate = RTCIceCandidate(
            sdpMid=data["sdpMid"],
            sdpMLineIndex=data["sdpMLineIndex"],
            candidate=data["candidate"],
        )
        pc = await self.peer_connection_manager.get(sid)
        if pc:
            await pc.addIceCandidate(candidate)
