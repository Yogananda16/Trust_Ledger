import os
from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs

load_dotenv()
client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))


def generate_briefing(text: str, output_path: str = "briefing.mp3") -> str:
    audio = client.text_to_speech.convert(
        text=text,
        voice_id="EXAVITQu4vr4xnSDxMaL",  # "George" - browse other voices in your ElevenLabs library if you want a different one
        model_id="eleven_multilingual_v2",
        output_format="mp3_44100_128",
    )
    with open(output_path, "wb") as f:
        for chunk in audio:
            f.write(chunk)
    return output_path
