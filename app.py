import streamlit as st
import google.generativeai as genai
from gtts import gTTS
import os
import json
import io

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="CareLingo: Diagnostic", page_icon="🩺", layout="centered")

# Load API Key
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("🚨 Gemini API Key missing! Add 'GEMINI_API_KEY' to Streamlit Secrets.")
    st.stop()

# --- DIAGNOSTIC SIDEBAR ---
with st.sidebar:
    st.header("🛠️ Diagnostic Mode")
    st.write(f"**Library Version:** {genai.__version__}")
    
    # Try to list available models
    try:
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        st.success(f"✅ Found {len(models)} models")
        model_name = st.selectbox("Select Model:", models, index=0 if models else None)
    except Exception as e:
        st.error(f"Error listing models: {e}")
        model_name = "models/gemini-1.5-flash" # Fallback default

    st.info("Recommended: models/gemini-1.5-flash")

# Initialize Selected Model
model = genai.GenerativeModel(model_name)

# Session State
if "messages" not in st.session_state: st.session_state.messages = []
if "scenario" not in st.session_state: st.session_state.scenario = None
if "feedback" not in st.session_state: st.session_state.feedback = None

# --- 2. SCENARIOS ---
SCENARIOS = {
    "1. Anamnese (Admission)": {
        "role": "You are a new patient, Herr Müller. You are anxious and speak only German.",
        "goal": "Collect patient history.",
        "icon": "📝"
    },
    "2. Medikamentengabe (Medication)": {
        "role": "You are Frau Schneider. You refuse to take pills.",
        "goal": "Explain why medication is needed.",
        "icon": "💊"
    }
}

# --- 3. HELPER FUNCTIONS ---
def transcribe_audio_with_gemini(audio_bytes):
    try:
        prompt = "Transcribe this German audio exactly."
        response = model.generate_content([
            prompt,
            {"mime_type": "audio/mp3", "data": audio_bytes}
        ])
        return response.text.strip()
    except Exception as e:
        st.error(f"Transcription Error: {e}")
        return None

def get_ai_response(user_text, scenario_key):
    scenario_data = SCENARIOS[scenario_key]
    system_prompt = f"""
    ACT AS: {scenario_data['role']}
    Respond in German. Then output JSON with feedback.
    Example JSON: {{"response_text": "...", "feedback": {{ "critique": "..." }} }}
    """
    try:
        response = model.generate_content(
            f"{system_prompt}\nUser said: {user_text}", 
            generation_config={"response_mime_type": "application/json"}
        )
        return json.loads(response.text)
    except Exception as e:
        st.error(f"AI Logic Error: {e}")
        return None

def text_to_speech_free(text):
    try:
        tts = gTTS(text=text, lang='de')
        mp3_fp = io.BytesIO()
        tts.write_to_fp(mp3_fp)
        mp3_fp.seek(0)
        return mp3_fp
    except Exception as e:
        st.error(f"TTS Error: {e}")
        return None

# --- 4. MAIN UI ---
st.title("🩺 CareLingo (Diagnostic)")

if not st.session_state.scenario:
    st.info("👈 Select a scenario in the sidebar (if visible) or click below.")
    # Quick start if sidebar is confusing
    cols = st.columns(2)
    if cols[0].button("Start Admission"):
        st.session_state.scenario = "1. Anamnese (Admission)"
        st.rerun()
else:
    scen = SCENARIOS[st.session_state.scenario]
    st.subheader(f"{scen['icon']} {st.session_state.scenario}")
    
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    st.divider()
    audio_value = st.audio_input("Reply in German...")

    if audio_value:
        with st.spinner(f"Listening with {model_name}..."):
            audio_bytes = audio_value.read()
            user_text = transcribe_audio_with_gemini(audio_bytes)
        
        if user_text:
            st.session_state.messages.append({"role": "user", "content": user_text})
            with st.spinner("Thinking..."):
                ai_data = get_ai_response(user_text, st.session_state.scenario)
                if ai_data:
                    resp_text = ai_data["response_text"]
                    audio_stream = text_to_speech_free(resp_text)
                    st.session_state.messages.append({"role": "assistant", "content": resp_text})
                    if audio_stream:
                        st.audio(audio_stream, format="audio/mp3", autoplay=True)
            st.rerun()
