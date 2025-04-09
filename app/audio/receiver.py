from aiortc import MediaStreamTrack
import logging
import webrtcvad

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class AudioReceiverTrack(MediaStreamTrack):
    kind = "audio"
    vad = webrtcvad.Vad(3)

    def __init__(self, track, sid):
        super().__init__()
        self.track = track
        self.sid = sid
        self.in_speech = False
        self.speech_count = 0

    async def recv(self):
        frame = await self.track.recv()
        pcm = frame.to_ndarray().tobytes()
        chunk = pcm[:320]
        is_speech = self.vad.is_speech(chunk, 16000)

        if is_speech:
            if not self.in_speech:
                logger.debug("🟢 발화 시작")
                self.in_speech = True

            self.speech_count = 0

        elif self.in_speech:
            self.speech_count += 1
            if self.speech_count > 50:  # 50 * 20ms = 1s
                logger.debug("🔴 발화 종료")
                self.in_speech = False
                self.speech_count = 0

        return frame
