import speech_recognition as sr
from datetime import datetime

def listen_continuously():
    recognizer = sr.Recognizer()
    mic = sr.Microphone()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"transcript_{timestamp}.txt"
    transcript = ""

    with mic as source:
        recognizer.adjust_for_ambient_noise(source)
        while True:
            try:
                print("🎧 Listening...")
                audio = recognizer.listen(source, timeout=20, phrase_time_limit=20)
                text = recognizer.recognize_google(audio)
                print(f"You said: {text}")

                if "stop listening" in text.lower():
                    print("🛑 Stopped listening.")
                    with open(filename, "w", encoding="utf-8") as f:
                        f.write(transcript.strip())
                    print(f"✅ Transcript saved to: {filename}")
                    break

                transcript += " " + text
                yield text

            except sr.UnknownValueError:
                print("🤔 Didn't catch that.")
                yield ""
            except sr.WaitTimeoutError:
                print("⌛ Timeout.")
                yield ""
