from __future__ import annotations
import os, json, base64, io
from typing import Optional, Dict, Any
import logging

# Make Google Cloud optional: import lazily and provide clear errors if missing
try:
    from google.oauth2 import service_account  # type: ignore
    from google.cloud import speech, texttospeech  # type: ignore
except Exception:  # Libraries not installed
    service_account = None  # type: ignore
    speech = None  # type: ignore
    texttospeech = None  # type: ignore

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
    
    try:
        creds = _credentials()
        client = speech.SpeechClient(credentials=creds) if creds else speech.SpeechClient()
        language = language_code or os.getenv("GOOGLE_STT_LANGUAGE", "es-ES")  # Default to Spanish

        audio = speech.RecognitionAudio(content=bytes_data)
        config = speech.RecognitionConfig(
            language_code=language,
            enable_automatic_punctuation=True,
            model="latest_long",
            audio_channel_count=1,
            enable_spoken_punctuation=True,
            enable_spoken_emojis=False,
            use_enhanced=True,  # Use enhanced model for better accuracy
            sample_rate_hertz=16000,  # Common sample rate
            encoding=speech.RecognitionConfig.AudioEncoding.WEBM_OPUS,  # Support for webm
        )
        
        logger.info(f"Transcribing audio with language: {language}")
        resp = client.recognize(config=config, audio=audio)
        
        if resp.results:
            text = " ".join([r.alternatives[0].transcript for r in resp.results])
            confidence = resp.results[0].alternatives[0].confidence if resp.results[0].alternatives else 0.0
            logger.info(f"Transcription completed with confidence: {confidence:.2f}")
            return text.strip()
        else:
            logger.warning("No transcription results returned")
            return ""
            
    except Exception as e:
        logger.error(f"Transcription error: {str(e)}")
        raise RuntimeError(f"Failed to transcribe audio: {str(e)}")

def tts_google(text: str, language_code: Optional[str] = None, voice_name: Optional[str] = None) -> bytes:
    """Synthesize speech → MP3 bytes."""
    if texttospeech is None:
        raise RuntimeError(
            "Google Cloud Text-to-Speech is not installed. Install with: pip install google-cloud-texttospeech google-auth"
        )
    
    try:
        creds = _credentials()
        client = texttospeech.TextToSpeechClient(credentials=creds) if creds else texttospeech.TextToSpeechClient()

        lang = language_code or os.getenv("GOOGLE_TTS_LANGUAGE", "es-ES")  # Default to Spanish
        name = voice_name or os.getenv("GOOGLE_TTS_VOICE", "es-ES-Standard-A")  # Spanish voice
        
        voice = texttospeech.VoiceSelectionParams(
            language_code=lang, 
            name=name or None,
            ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL
        )
        
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=1.0,  # Normal speed
            pitch=0.0,  # Normal pitch
            volume_gain_db=0.0  # Normal volume
        )
        
        synthesis_input = texttospeech.SynthesisInput(text=text)
        
        logger.info(f"Synthesizing speech for text: {text[:50]}...")
        resp = client.synthesize_speech(input=synthesis_input, voice=voice, audio_config=audio_config)
        
        logger.info("Speech synthesis completed successfully")
        return resp.audio_content
        
    except Exception as e:
        logger.error(f"TTS error: {str(e)}")
        raise RuntimeError(f"Failed to synthesize speech: {str(e)}")

def process_voice_input(audio_data: bytes, language_code: Optional[str] = None) -> Dict[str, Any]:
    """
    Process voice input from frontend and return structured response.
    Uses Whisper for local transcription (no Google Cloud required).
    """
    try:
        # Use Whisper for transcription
        transcribed_text = transcribe_whisper(audio_data, language_code)
        
        if not transcribed_text:
            return {
                "success": False,
                "error": "No se pudo transcribir el audio. Por favor, intenta de nuevo.",
                "text": ""
            }
        
        # Clean up the transcribed text
        cleaned_text = transcribed_text.strip()
        
        return {
            "success": True,
            "text": cleaned_text,
            "confidence": "high",
            "language": language_code or "es"
        }
        
    except Exception as e:
        logger.error(f"Voice processing error: {str(e)}")
        return {
            "success": False,
            "error": f"Error procesando el audio: {str(e)}",
            "text": ""
        }

def transcribe_with_openai_api(audio_data: bytes, language_code: Optional[str] = None) -> str:
    """
    Transcribe audio using OpenAI API as fallback when local processing fails.
    """
    try:
        import openai
        import tempfile
        import os
        from dotenv import load_dotenv
        
        # Load environment variables from .env file
        load_dotenv()
        
        # Create temporary file for audio data
        with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as temp_file:
            temp_file.write(audio_data)
            temp_file_path = temp_file.name
        
        try:
            # Check if API key is configured
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise Exception("OPENAI_API_KEY not configured. Please set it as environment variable or in .env file")
            
            logger.info(f"Using OpenAI API with key: {api_key[:20]}...")
            
            # Create OpenAI client
            client = openai.OpenAI(api_key=api_key)
            
            # Use OpenAI API for transcription
            # Convert language code to ISO-639-1 format (2 letters only)
            lang = language_code or "es"
            if lang and '-' in lang:
                lang = lang.split('-')[0]  # Convert 'es-ES' to 'es'
            
            with open(temp_file_path, "rb") as audio_file:
                transcript = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language=lang
                )
            
            logger.info(f"OpenAI API transcription result: {transcript.text[:50]}...")
            
            return transcript.text
            
        finally:
            # Clean up temporary file
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
                
    except Exception as e:
        logger.error(f"OpenAI API transcription error: {str(e)}")
        raise RuntimeError(f"Failed to transcribe audio with OpenAI API: {str(e)}")

def transcribe_whisper(audio_data: bytes, language_code: Optional[str] = None) -> str:
    """
    Transcribe audio using OpenAI Whisper (local, no API keys required).
    """
    try:
        # First, try OpenAI API if available (fastest and most reliable)
        try:
            from dotenv import load_dotenv
            import os
            load_dotenv()
            api_key = os.getenv("OPENAI_API_KEY")
            if api_key:
                logger.info("OpenAI API key found, trying API transcription first...")
                try:
                    result = transcribe_with_openai_api(audio_data, language_code)
                    logger.info("OpenAI API transcription completed successfully")
                    return result
                except Exception as inner_error:
                    logger.error(f"OpenAI API transcription failed: {inner_error}", exc_info=True)
                    raise
            else:
                logger.warning("No OpenAI API key found in environment")
        except Exception as api_error:
            logger.error(f"OpenAI API error: {api_error}", exc_info=True)
            logger.warning("Falling back to local methods")
        
        # Fallback to local Whisper processing
        import whisper
        import tempfile
        import os
        import ssl
        import urllib.request
        import io
        
        # Fix SSL certificate issues for model downloading
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        urllib.request.install_opener(urllib.request.build_opener(urllib.request.HTTPSHandler(context=ssl_context)))
        
        # Load Whisper model (base model is good balance of speed/accuracy)
        model = whisper.load_model("base")
        
        # Try to handle WebM format using PyAV (av library)
        try:
            import av
            import librosa
            import soundfile as sf
            import numpy as np
            
            # Try to extract audio from WebM using PyAV
            audio_data_io = io.BytesIO(audio_data)
            
            try:
                # Open WebM file with PyAV
                container = av.open(audio_data_io, format='webm')
                audio_stream = container.streams.audio[0]
                
                # Extract audio frames
                audio_frames = []
                for frame in container.decode(audio_stream):
                    # Convert frame to numpy array
                    audio_array = frame.to_ndarray()
                    if len(audio_array.shape) > 1:
                        # Convert stereo to mono
                        audio_array = np.mean(audio_array, axis=0)
                    audio_frames.append(audio_array)
                
                if audio_frames:
                    # Concatenate all audio frames
                    audio_combined = np.concatenate(audio_frames)
                    
                    # Resample to 16kHz if needed
                    if audio_stream.sample_rate != 16000:
                        import librosa
                        audio_resampled = librosa.resample(audio_combined, orig_sr=audio_stream.sample_rate, target_sr=16000)
                    else:
                        audio_resampled = audio_combined
                    
                    # Create temporary file for converted audio
                    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                        sf.write(temp_file.name, audio_resampled, 16000, format='WAV')
                        temp_file_path = temp_file.name
                        
                    logger.info("Successfully extracted audio from WebM using PyAV")
                else:
                    raise Exception("No audio frames found in WebM")
                
            except Exception as av_error:
                logger.warning(f"PyAV extraction failed: {av_error}, trying librosa")
                
                # Fallback to librosa with different formats
                formats_to_try = ['wav', 'mp3', 'flac', 'ogg']
                y, sr = None, None
                
                for fmt in formats_to_try:
                    try:
                        audio_data_io.seek(0)  # Reset stream position
                        y, sr = librosa.load(audio_data_io, sr=16000, format=fmt)
                        logger.info(f"Successfully loaded audio as {fmt} format")
                        break
                    except Exception as fmt_error:
                        logger.debug(f"Failed to load as {fmt}: {fmt_error}")
                        continue
                
                if y is None:
                    raise Exception("Could not load audio in any supported format")
                
                # Create temporary file for converted audio
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                    sf.write(temp_file.name, y, sr, format='WAV')
                    temp_file_path = temp_file.name
            
        except Exception as e:
            # Final fallback: try OpenAI API for transcription
            logger.warning(f"All local audio conversion methods failed: {e}, trying OpenAI API")
            try:
                logger.info("Attempting OpenAI API transcription...")
                result = transcribe_with_openai_api(audio_data, language_code)
                logger.info("OpenAI API transcription successful")
                return result
            except Exception as api_error:
                logger.error(f"OpenAI API transcription also failed: {api_error}")
                # Last resort: try to use original data as WAV
                logger.warning("Using direct approach as last resort")
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                    temp_file.write(audio_data)
                    temp_file_path = temp_file.name
        
        try:
            # Transcribe the audio
            result = model.transcribe(
                temp_file_path,
                language=language_code or "es",  # Spanish by default
                fp16=False  # Use fp32 for better compatibility
            )
            
            return result["text"]
            
        except Exception as e:
            # If ffmpeg is missing, try to provide a helpful error message
            if "ffmpeg" in str(e).lower() or "no such file" in str(e).lower():
                raise RuntimeError(
                    "ffmpeg is required for audio processing. Please install it with: "
                    "brew install ffmpeg (if you have Homebrew) or download from https://ffmpeg.org/"
                )
            else:
                raise e
            
        finally:
            # Clean up temporary file
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
                
    except Exception as e:
        logger.error(f"Whisper transcription error: {str(e)}")
        raise RuntimeError(f"Failed to transcribe audio with Whisper: {str(e)}")

def create_voice_response(text: str, language_code: Optional[str] = None) -> Dict[str, Any]:
    """
    Create a voice response for the given text.
    Returns both the text and audio data.
    """
    try:
        # Generate speech
        audio_bytes = tts_google(text, language_code)
        audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')
        
        return {
            "success": True,
            "text": text,
            "audio_b64": audio_b64,
            "language": language_code or "es-ES"
        }
        
    except Exception as e:
        logger.error(f"Voice response creation error: {str(e)}")
        return {
            "success": False,
            "error": f"Error generando respuesta de voz: {str(e)}",
            "text": text,
            "audio_b64": None
        }
