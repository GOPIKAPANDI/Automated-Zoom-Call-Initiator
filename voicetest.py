import pyttsx3
import speech_recognition as sr
import requests

# Initialize text-to-speech engine
engine = pyttsx3.init('sapi5')
voices = engine.getProperty('voices')
engine.setProperty('voice', voices[0].id)

def speak(audio):
    engine.say(audio)
    engine.runAndWait()

def listen():
    recognizer = sr.Recognizer()
    microphone = sr.Microphone()

    with microphone as source:
        print("Listening...")
        recognizer.adjust_for_ambient_noise(source)
        audio = recognizer.listen(source)

    try:
        query = recognizer.recognize_google(audio).lower()
        print(f"You said: {query}")
        return query
    except sr.UnknownValueError:
        speak("Sorry, I did not understand that.")
        return None
    except sr.RequestError:
        speak("Sorry, my speech service is down.")
        return None    

while True:
    command = listen()
    
    if command == "show data":
        try:
            response = requests.post("http://localhost:8000/set_command/show data")
            if response.status_code == 200:
                speak("Command sent to show data.")
        except Exception as e:
            speak(f"Failed to send command: {str(e)}")
