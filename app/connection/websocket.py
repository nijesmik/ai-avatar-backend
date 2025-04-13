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
        pc = RTCPeerConnection()
        await self.peer_connection_manager.add(sid, pc)

        @pc.on("track")
        def on_track(track):
            logger.info(f"🎧 Track: {track.kind}")
            if track.kind == "audio":
                pc.addTrack(AudioReceiverTrack(track, sid))

        @pc.on("icecandidate")
        async def on_icecandidate(event):
            candidate = event.candidate
            if candidate:
                await self.sio.emit(
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
                await self.peer_connection_manager.remove(sid)
                logger.info(f"❌ WebRTC 연결 종료 처리 완료: {sid}")

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
