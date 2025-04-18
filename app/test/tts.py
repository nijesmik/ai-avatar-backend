import json
import wave
from os import getenv

import azure.cognitiveservices.speech as speechsdk
import numpy as np
from dotenv import load_dotenv

load_dotenv()


class _Callback(speechsdk.audio.PushAudioOutputStreamCallback):
    def __init__(self):
        super().__init__()
        self.wave_file = wave.open("./.recordings/tts_output.wav", "wb")
        self.wave_file.setnchannels(1)
        self.wave_file.setsampwidth(2)  # 16bit = 2bytes
        self.wave_file.setframerate(48000)

    def write(self, audio_buffer: memoryview) -> int:
        pcm = np.frombuffer(audio_buffer, dtype=np.int16)
        self.wave_file.writeframes(pcm.tobytes())

        return len(audio_buffer)

    def close(self):
        self.wave_file.close()


text = "안녕하세요.반갑습니다."

speech_config = speechsdk.SpeechConfig(
    subscription=getenv("AZURE_SPEECH_KEY"),
    region=getenv("AZURE_SPEECH_REGION"),
)
speech_config.speech_synthesis_voice_name = "ko-KR-InJoonNeural"
speech_config.set_speech_synthesis_output_format(
    speechsdk.SpeechSynthesisOutputFormat.Raw48Khz16BitMonoPcm
)

audio_stream = speechsdk.audio.PushAudioOutputStream(_Callback())
audio_config = speechsdk.audio.AudioOutputConfig(stream=audio_stream)
synthesizer = speechsdk.SpeechSynthesizer(speech_config, audio_config)

viseme = []

def viseme_callback(event: speechsdk.SpeechSynthesisVisemeEventArgs):
    viseme.append(
        {
            "animation": event.animation,
            "audio_offset": event.audio_offset / 10000,
            "viseme_id": event.viseme_id,
        }
    )

synthesizer.viseme_received.connect(viseme_callback)

speech_synthesis_result = synthesizer.speak_text_async(text).get()

if speech_synthesis_result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
    print("Speech synthesized for text [{}]".format(text))
    with open("./.recordings/viseme_data.json", "w", encoding="utf-8") as f:
        json.dump(viseme, f, ensure_ascii=False, indent=2)

elif speech_synthesis_result.reason == speechsdk.ResultReason.Canceled:
    cancellation_details = speech_synthesis_result.cancellation_details
    print("Speech synthesis canceled: {}".format(cancellation_details.reason))
    if cancellation_details.reason == speechsdk.CancellationReason.Error:
        if cancellation_details.error_details:
            print("Error details: {}".format(cancellation_details.error_details))
            print("Did you set the speech resource key and region values?")
