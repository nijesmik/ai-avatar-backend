from enum import Enum


class SynthesisVoiceKorean(str, Enum):
    SunHi = "ko-KR-SunHiNeural"  # 여성
    InJoon = "ko-KR-InJoonNeural"  # 남성
    HyunsuMultilingual = "ko-KR-HyunsuMultilingualNeural"  # 남성
    BongJin = "ko-KR-BongJinNeural"  # 남성
    GookMin = "ko-KR-GookMinNeural"  # 남성
    Hyunsu = "ko-KR-HyunsuNeural"  # 남성
    JiMin = "ko-KR-JiMinNeural"  # 여성
    SeoHyeon = "ko-KR-SeoHyeonNeural"  # 여성
    SoonBok = "ko-KR-SoonBokNeural"  # 여성
    YuJin = "ko-KR-YuJinNeural"  # 여성

    @classmethod
    def get(cls, gender: str, voice: str):
        if gender == "female":
            return SynthesisVoiceKorean.SunHi
        if voice == "InJoon":
            return SynthesisVoiceKorean.InJoon
        if voice == "Hyunsu":
            return SynthesisVoiceKorean.HyunsuMultilingual
        return None
