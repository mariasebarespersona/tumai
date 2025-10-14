from __future__ import annotations
import os, json
from typing import Optional

# Make Google Cloud optional: import lazily and provide clear errors if missing
try:
    from google.oauth2 import service_account  # type: ignore
    from google.cloud import speech, texttospeech  # type: ignore
except Exception:  # Libraries not installed
    service_account = None  # type: ignore
    speech = None  # type: ignore
    texttospeech = None  # type: ignore

def _credentials():
    if os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON") and service_account is not None:
        info = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])
        return service_account.Credentials.from_service_account_info(info)
    # else use ADC (incl. GOOGLE_APPLICATION_CREDENTIALS)
    return None

def transcribe_google_wav(bytes_data: bytes, language_code: Optional[str] = None) -> str:
    """Transcribe WAV/LINEAR16/FLAC/MP3/OGG with Google STT."""
    if speech is None:
        raise RuntimeError(
            "Google Cloud Speech is not installed. Install with: pip install google-cloud-speech google-auth"
        )
    creds = _credentials()
    client = speech.SpeechClient(credentials=creds) if creds else speech.SpeechClient()
    language = language_code or os.getenv("GOOGLE_STT_LANGUAGE", "en-US")

    audio = speech.RecognitionAudio(content=bytes_data)
    config = speech.RecognitionConfig(
        language_code=language,
        enable_automatic_punctuation=True,
        model="latest_long",
        audio_channel_count=1,
        enable_spoken_punctuation=True,
        enable_spoken_emojis=False,
    )
    resp = client.recognize(config=config, audio=audio)
    text = " ".join([r.alternatives[0].transcript for r in resp.results]) if resp.results else ""
    return text

def tts_google(text: str, language_code: Optional[str] = None, voice_name: Optional[str] = None) -> bytes:
    """Synthesize speech → MP3 bytes."""
    if texttospeech is None:
        raise RuntimeError(
            "Google Cloud Text-to-Speech is not installed. Install with: pip install google-cloud-texttospeech google-auth"
        )
    creds = _credentials()
    client = texttospeech.TextToSpeechClient(credentials=creds) if creds else texttospeech.TextToSpeechClient()

    lang = language_code or os.getenv("GOOGLE_TTS_LANGUAGE", "en-US")
    name = voice_name or os.getenv("GOOGLE_TTS_VOICE", "")
    voice = texttospeech.VoiceSelectionParams(language_code=lang, name=name or None)
    audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.MP3)
    synthesis_input = texttospeech.SynthesisInput(text=text)
    resp = client.synthesize_speech(input=synthesis_input, voice=voice, audio_config=audio_config)
    return resp.audio_content
