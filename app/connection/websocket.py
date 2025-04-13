import logging
from socketio import AsyncServer
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCIceCandidate
from app.audio.receiver import AudioReceiverTrack
from app.connection.webrtc import PeerConnectionManager

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class SocketEventHandler:
    def __init__(self, sio: AsyncServer):
        self.sio = sio
        self.peer_connection_manager = PeerConnectionManager()

    async def connect(self, sid, environ):
        logger.info(f"🔌 Connected: {sid}")

    async def disconnect(self, sid):
        logger.info(f"❌ Disconnected: {sid}")
        await self.peer_connection_manager.remove(sid)

    async def offer(self, sid, data):
        logger.info(f"📡 Offer from {sid}")

        async def emit_icecandidate(data):
            await self.sio.emit(
                "ice_candidate",
                data,
                to=sid,
            )

        pc = await self.peer_connection_manager.create(
            sid,
            emit_icecandidate
        )

        offer = RTCSessionDescription(sdp=data["sdp"], type=data["type"])
        await pc.setRemoteDescription(offer)
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)

        await self.sio.emit(
            "answer",
            {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type},
            to=sid,
        )

    async def ice_candidate(self, sid, candidate):
        rtc_candidate = RTCIceCandidate(
            sdpMid=candidate["sdpMid"],
            sdpMLineIndex=candidate["sdpMLineIndex"],
            candidate=candidate["candidate"],
        )
        pc = await self.peer_connection_manager.get(sid)
        if pc:
            await pc.addIceCandidate(rtc_candidate)
