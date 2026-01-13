import streamlit as st
import google.generativeai as genai
from gtts import gTTS
import os
import json
import io
import time

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="CareLingo", page_icon="🩺", layout="centered")

# --- 2. PROFESSIONAL UX DESIGN (Hover Effects & Clickable Areas) ---
st.markdown("""
<style>
    /* Global Font */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    
    /* Hover Effects for Buttons */
    .stButton button {
        width: 100%;
        border-radius: 12px;
        border: 1px solid rgba(128, 128, 128, 0.2);
        transition: all 0.3s ease;
        /* background-color: transparent;  Let Streamlit handle bg for Dark Mode compatibility */
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    
    /* Make buttons pop on hover */
    .stButton button:hover {
        transform: translateY(-3px);
        box-shadow: 0 8px 16px rgba(0,0,0,0.1);
        border-color: #FF4B4B;
        color: #FF4B4B;
    }
    
    /* Scenario Description Text */
    .scenario-desc {
        font-size: 0.9rem;
        opacity: 0.8;
        margin-bottom: 20px;
        min-height: 3rem;
        text-align: center;
    }

    /* Hide confusing Input hints */
    div[data-testid="InputInstructions"] > span { display: none; }
    
    /* Highlight the Recorder */
    .recorder-cue {
        font-weight: 700;
        color: #FF4B4B;
        text-align: center;
        margin-bottom: 5px;
        animation: pulse 2s infinite;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    
    @keyframes pulse {
        0% { opacity: 1; transform: scale(1); }
        50% { opacity: 0.6; transform: scale(1.02); }
        100% { opacity: 1; transform: scale(1); }
    }
</style>
""", unsafe_allow_html=True)

# --- 3. AUTHENTICATION ---
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("🚨 API Key Missing.")
    st.stop()

if "APP_PASSWORD" in st.secrets:
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    
    if not st.session_state.authenticated:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown("<h1 style='text-align: center;'>🔐 CareLingo Login</h1>", unsafe_allow_html=True)
        pwd = st.text_input("Access Password", type="password")
        if st.button("Start Shift"):
            if pwd == st.secrets["APP_PASSWORD"]:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("⚠️ Access Denied")
        st.stop()

# --- 4. MODEL SETTINGS (Open by Default) ---
st.title("🩺 CareLingo")

# We use an expander that is OPEN by default so users see the model choice
with st.expander("⚙️ System Settings (Model Selection)", expanded=True):
    c1, c2 = st.columns([3, 1])
    with c1:
        model_choice = st.selectbox(
            "Active AI Brain:",
            [
                "gemini-2.5-flash-native-audio-dialog", # ⚡ Unlimited Live
                "gemini-2.5-flash",
                "gemini-2.0-flash-exp",
                "gemini-1.5-flash",
                "gemini-1.5-pro"
            ],
            index=0
        )
    with c2:
        st.write("") # Spacer
        if st.button("🗑️ Reset All"):
            st.session_state.messages = []
            st.session_state.feedback = None
            st.rerun()

model = genai.GenerativeModel(model_choice)

# --- 5. STATE MANAGEMENT ---
if "messages" not in st.session_state: st.session_state.messages = []
if "scenario" not in st.session_state: st.session_state.scenario = None
if "feedback" not in st.session_state: st.session_state.feedback = None
if "last_audio_id" not in st.session_state: st.session_state.last_audio_id = None

# --- 6. SCENARIO DATA (Empathetic & Clear) ---
SCENARIOS = {
    "Admission": {
        "icon": "📋", 
        "title": "Patient Admission", 
        "desc": "A new patient has just arrived. They are anxious. Your goal is to collect their medical history and calm them down.",
        "role": "Herr Müller (Anxious Patient)", 
        "goal": "Collect medical history & build trust."
    },
    "Medication": {
        "icon": "💊", 
        "title": "Medication Refusal", 
        "desc": "Frau Schneider refuses to take her heart medication. She says it makes her dizzy. Convince her safely.",
        "role": "Frau Schneider (Stubborn)", 
        "goal": "Explain necessity & negotiate."
    },
    "Emergency": {
        "icon": "🚨", 
        "title": "Emergency (Notfall)", 
        "desc": "A visitor runs to you: 'My husband collapsed!' You need to get vital details immediately to send the code team.",
        "role": "Visitor (Panicked)", 
        "goal": "Get vitals (Age, Symptoms) FAST."
    }
}

# --- 7. CORE LOGIC ---
def process_audio(audio_bytes, scenario_key):
    try:
        # 1. Transcribe
        prompt = "Transcribe this German audio exactly. Output ONLY the German text."
        resp = model.generate_content([prompt, {"mime_type": "audio/mp3", "data": audio_bytes}])
        text = resp.text.strip()
        
        # 2. Analyze
        scen = SCENARIOS[scenario_key]
        analysis_prompt = f"""
        Act as German Tutor. Role: {scen['role']}. Goal: {scen['goal']}.
        Output JSON: {{
            "response_text": "German reply",
            "feedback": {{
                "grammar": (1-10), "politeness": (1-10), "medical": (1-10),
                "critique": "Tip in English", "better_phrase": "German correction"
            }}
        }}
        """
