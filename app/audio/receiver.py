from aiortc import MediaStreamTrack

class AudioReceiverTrack(MediaStreamTrack):
    kind = "audio"

    def __init__(self, track, sid):
        super().__init__()
        self.track = track
        self.sid = sid

    async def recv(self):
        frame = await self.track.recv()
        return frame
