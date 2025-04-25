from dataclasses import dataclass

@dataclass
class Viseme:
    animation: str
    audio_offset: int
    viseme_id: int