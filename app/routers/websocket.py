import logging
import asyncio
from socketio import AsyncServer
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCIceCandidate
from app.audio.receiver import AudioReceiverTrack

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class PeerConnectionManager:
    def __init__(self):
        self.peer_connections = {}
        self.lock = asyncio.Lock()

    async def add(self, sid, pc):
        async with self.lock:
            self.peer_connections[sid] = pc

    async def get(self, sid):
        async with self.lock:
            return self.peer_connections.get(sid)

    async def remove(self, sid):
        async with self.lock:
            pc = self.peer_connections.pop(sid, None)
            if pc:
                await pc.close()


peer_connection_manager = PeerConnectionManager()


def register_handlers(sio: AsyncServer):
    @sio.event
    async def connect(sid, environ):
        logger.info(f"🔌 Connected: {sid}")

    @sio.event
    async def disconnect(sid):
        logger.info(f"❌ Disconnected: {sid}")
        await peer_connection_manager.remove(sid)

    @sio.event
    async def offer(sid, data):
        logger.info(f"📡 Offer from {sid}")
        pc = RTCPeerConnection()
        await peer_connection_manager.add(sid, pc)

        @pc.on("track")
        def on_track(track):
            logger.info(f"🎧 Track: {track.kind}")
            if track.kind == "audio":
                pc.addTrack(AudioReceiverTrack(track, sid))

        @pc.on("icecandidate")
        async def on_icecandidate(event):
            candidate = event.candidate
            if candidate:
                await sio.emit(
                    "ice_candidate",
                    {
                        "candidate": candidate.to_sdp(),
                        "sdpMid": candidate.sdpMid,
                        "sdpMLineIndex": candidate.sdpMLineIndex,
                    },
                    to=sid,
                )

        @pc.on("connectionstatechange")
        async def on_connectionstatechange():
            if pc.connectionState in ["disconnected", "failed", "closed"]:
                await peer_connection_manager.remove(sid)
                logger.info(f"❌ WebRTC 연결 종료 처리 완료: {sid}")

        offer = RTCSessionDescription(sdp=data["sdp"], type=data["type"])
        await pc.setRemoteDescription(offer)
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)

        await sio.emit(
            "answer",
            {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type},
            to=sid,
        )

    @sio.event
    async def ice_candidate(sid, candidate):
        rtc_candidate = RTCIceCandidate(
            sdpMid=candidate["sdpMid"],
            sdpMLineIndex=candidate["sdpMLineIndex"],
            candidate=candidate["candidate"],
        )
        pc = await peer_connection_manager.get(sid)
        if pc:
            await pc.addIceCandidate(rtc_candidate)
