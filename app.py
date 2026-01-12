import streamlit as st
import google.generativeai as genai
from gtts import gTTS
import os
import json
import io

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="CareLingo: German Practice", page_icon="🩺", layout="centered")

# --- PASSWORD PROTECTION (Optional) ---
if "APP_PASSWORD" in st.secrets:
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    
    if not st.session_state.authenticated:
        st.title("🔒 Login Required")
        user_pwd = st.text_input("Enter Access Password", type="password")
        if st.button("Login"):
            if user_pwd == st.secrets["APP_PASSWORD"]:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Incorrect password.")
        st.stop()
        
# Load API Key
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("🚨 Gemini API Key missing! Add 'GEMINI_API_KEY' to Streamlit Secrets.")
    st.stop()

# Initialize Model (Gemini 1.5 Flash is fast and multimodal)
model = genai.GenerativeModel('gemini-1.5-flash')

# Session State
if "messages" not in st.session_state: st.session_state.messages = []
if "scenario" not in st.session_state: st.session_state.scenario = None
if "feedback" not in st.session_state: st.session_state.feedback = None

# --- 2. SCENARIOS ---
SCENARIOS = {
    "1. Anamnese (Admission)": {
        "role": "You are a new patient, Herr Müller, admitted for chest pain. You are anxious and speak only German.",
        "goal": "Collect patient history: Pain level, allergies, previous conditions.",
        "icon": "📝"
    },
    "2. Medikamentengabe (Medication)": {
        "role": "You are Frau Schneider, an elderly patient who refuses to take her new pills because she fears side effects.",
        "goal": "Explain why the medication is needed and calm her fears.",
        "icon": "💊"
    },
    "3. Notfall (Emergency)": {
        "role": "You are a panic-stricken visitor whose husband has just collapsed.",
        "goal": "Calm the visitor and get essential details acting fast.",
        "icon": "🚨"
    }
}

# --- 3. HELPER FUNCTIONS ---

def transcribe_audio_with_gemini(audio_bytes):
    """Uses Gemini 1.5 Flash to transcribe audio (Listen)"""
    try:
        # Gemini expects a specific dictionary format for inline data
        prompt = "Transcribe this German audio exactly. Output only the German text, no explanations."
        response = model.generate_content([
            prompt,
            {"mime_type": "audio/mp3", "data": audio_bytes}
        ])
        return response.text.strip()
    except Exception as e:
        st.error(f"Transcription Error: {e}")
        return None

def get_ai_response(user_text, scenario_key):
    """Generates the response + feedback (Brain)"""
    scenario_data = SCENARIOS[scenario_key]
    
    system_prompt = f"""
    You are a German language tutor for nurses.
    ACT AS: {scenario_data['role']}
    USER GOAL: {scenario_data['goal']}
    
    1. Respond naturally in German.
    2. Analyze the user's German input.
    
    Return ONLY JSON:
    {{
        "response_text": "Your German response character text",
        "feedback": {{
            "grammar_score": (1-10),
            "politeness_score": (1-10),
            "critique": "English tip on mistake",
            "better_phrase": "Better German phrase"
        }}
    }}
    """
    
    # Build history for context
    history_text = "\n".join([f"{m['role']}: {m['content']}" for m in st.session_state.messages[-4:]])
    full_prompt = f"{system_prompt}\n\nCONVERSATION HISTORY:\n{history_text}\n\nUSER SAID: {user_text}"

    try:
        response = model.generate_content(full_prompt, generation_config={"response_mime_type": "application/json"})
        return json.loads(response.text)
    except Exception as e:
        st.error(f"AI Logic Error: {e}")
        return None

def text_to_speech_free(text):
    """Uses gTTS (Free) to convert text to audio (Speak)"""
    try:
        tts = gTTS(text=text, lang='de')
        # Save to memory buffer instead of file
        mp3_fp = io.BytesIO()
        tts.write_to_fp(mp3_fp)
        mp3_fp.seek(0)
        return mp3_fp
    except Exception as e:
        st.error(f"TTS Error: {e}")
        return None

# --- 4. UI LAYOUT ---
with st.sidebar:
    st.title("🩺 CareLingo (Gemini)")
    selected_scenario = st.radio("Select Scenario:", list(SCENARIOS.keys()))
    if st.button("Start / Reset"):
        st.session_state.messages = []
        st.session_state.scenario = selected_scenario
        st.session_state.feedback = None
        st.rerun()
        
    if st.session_state.feedback:
        f = st.session_state.feedback
        st.divider()
        st.caption("🔍 Analysis")
        st.progress(f['grammar_score']/10, f"Grammar: {f['grammar_score']}")
        st.info(f"Tip: {f['critique']}")
        st.success(f"Better: {f['better_phrase']}")

if not st.session_state.scenario:
    st.info("👈 Select a scenario to start.")
else:
    # Chat Display
    scen = SCENARIOS[st.session_state.scenario]
    st.subheader(f"{scen['icon']} {st.session_state.scenario}")
    
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    # Input Area
    st.divider()
    audio_value = st.audio_input("🇩🇪 Reply in German...")

    if audio_value:
        # 1. Process Audio
        with st.spinner("Listening..."):
            audio_bytes = audio_value.read()
            user_text = transcribe_audio_with_gemini(audio_bytes)
        
        if user_text:
            st.session_state.messages.append({"role": "user", "content": user_text})
            
            # 2. Get AI Response
            with st.spinner("Thinking..."):
                ai_data = get_ai_response(user_text, st.session_state.scenario)
                
                if ai_data:
                    st.session_state.feedback = ai_data["feedback"]
                    resp_text = ai_data["response_text"]
                    
                    # 3. Speak (TTS)
                    audio_stream = text_to_speech_free(resp_text)
                    
                    st.session_state.messages.append({"role": "assistant", "content": resp_text})
                    if audio_stream:
                        st.audio(audio_stream, format="audio/mp3", autoplay=True)
            st.rerun()
