from src.services.tts import generate_speech

audio = generate_speech("Hello! I am your AI voice assistant.")

with open("test_audio.ulaw", "wb") as file:
    file.write(audio)

print("ElevenLabs audio generated successfully!")
