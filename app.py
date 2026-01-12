import streamlit as st
import google.generativeai as genai
from gtts import gTTS
import os
import json
import io

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="CareLingo", page_icon="🩺", layout="centered")

# Load API Key
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("🚨 Gemini API Key missing! Add 'GEMINI_API_KEY' to Streamlit Secrets.")
    st.stop()

# --- PASSWORD PROTECTION ---
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

# --- 2. HARDCODED MODEL CONNECTION (The Fix) ---
# We try the alias that worked for you before.
@st.cache_resource
def load_hardcoded_model():
    # These are the 3 most common names. It will use the first one that works.
    candidates = [
        "gemini-1.5-flash",          # The standard alias
        "models/gemini-1.5-flash",   # The explicit path
        "gemini-1.5-flash-001"       # The versioned ID
    ]
    for name in candidates:
        try:
            model = genai.GenerativeModel(name)
            model.generate_content("Test") # Quick connection check
            return model
        except:
            continue
    return None

model = load_hardcoded_model()

if not model:
    st.error("❌ Error: Could not connect to Gemini 1.5 Flash. Please check API Key quota.")
    st.stop()

# --- 3. SESSION STATE ---
if "messages" not in st.session_state: st.session_state.messages = []
if "scenario" not in st.session_state: st.session_state.scenario = None
if "feedback" not in st.session_state: st.session_state.feedback = None
if "last_audio_id" not in st.session_state: st.session_state.last_audio_id = None
if "recording_count" not in st.session_state: st.session_state.recording_count = 0
MAX_RECORDINGS = 10

# --- 4. SCENARIOS ---
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
    },
    "3. Notfall (Emergency)": {
        "role": "You are a visitor whose husband collapsed.",
        "goal": "Get details fast.",
        "icon": "🚨"
    }
}

# --- 5. HELPER FUNCTIONS ---
def transcribe_audio(audio_bytes):
    try:
        prompt = "Transcribe this German audio exactly. Output
