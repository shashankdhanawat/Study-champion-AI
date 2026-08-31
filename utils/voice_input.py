def transcribe_audio(audio_bytes):
    """Best-effort audio transcription with a clear fallback."""
    try:
        import speech_recognition as sr
        import io
        recognizer = sr.Recognizer()
        with sr.AudioFile(io.BytesIO(audio_bytes)) as source:
            audio = recognizer.record(source)
        return recognizer.recognize_google(audio), None
    except ImportError:
        return "", "Install SpeechRecognition to transcribe voice questions."
    except Exception:
        return "", "Voice could not be transcribed. Please type your question instead."
