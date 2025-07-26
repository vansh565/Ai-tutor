import pyttsx3
import speech_recognition as sr

engine = pyttsx3.init()

def speak(text):
    engine.say(text)
    engine.runAndWait()

def take_command():
    r = sr.Recognizer()
    with sr.Microphone() as source:
        print("👂 Listening...")
        audio = r.listen(source)
    try:
        query = r.recognize_google(audio)
        return query.lower()
    except:
        return "error"

def answer_student(query, transcript):
    if "explain" in query:
        topic = query.split("explain")[-1]
        speak(f"Let me explain {topic}")
        # Optional: search and send to Gemini for clarification
