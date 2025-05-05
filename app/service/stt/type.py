from dataclasses import dataclass


@dataclass
class STTResult:
    success: bool
    text: str = None
    reason: str = None
