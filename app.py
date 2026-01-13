import streamlit as st
import google.generativeai as genai
from gtts import gTTS
import os
import json
import io

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="CareLingo", page_icon="🩺", layout="centered")

# --- 2. CLEAN STYLING (No risky overrides) ---
st.markdown("""
<style>
    /* Clean Card Style for Scenarios */
    .scenario-card {
        border: 1px solid rgba(128, 128, 128, 0.2);
        border-radius: 12px;
        padding: 1rem;
        text-align: center;
        margin-bottom: 10px;
    }
    
    /* Hide the 'Press Enter' hint on inputs */
    div[data-testid="InputInstructions"] > span { display: none; }
    
    /* Make buttons look good */
    .stButton button {
        width: 100%;
        font-weight: 600;
        border-radius: 8px;
    }
</style>
""", unsafe_allow_html=True)

# --- 3. AUTHENTICATION ---
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("🚨 System Error: API Key Missing.")
    st.stop()

if "APP_PASSWORD" in st.secrets:
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    
    if not st.session_state.authenticated:
        st.title("🔒 Login")
        with st.form("login_form"):
            pwd = st.text_input("Password", type="password")
            if st.form_submit_button("Login"):
                if pwd == st.secrets["APP_PASSWORD"]:
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("Incorrect Password")
        st.stop()

# --- 4. LAZY MODEL LOADING (Prevents Startup Crash) ---
# We do NOT ping the server here. We just set up the object.
def get_model():
    # Primary model (Stable)
    return genai.GenerativeModel("gemini-1.5-flash")

model = get_model()

# --- 5. SESSION STATE ---
if "messages" not in st.session_state: st.session_state.messages = []
if "scenario" not in st.session_state: st.session_state.scenario = None
if "feedback" not in st.session_state: st.session_state.feedback = None
if "last_audio_id" not in st.session_state: st.session_state.last_audio_id = None

# --- 6. SCENARIOS ---
SCENARIOS = {
    "Admission": {"icon": "📋", "title": "Patient Admission", "role": "Herr Müller (Anxious)", "goal": "Collect medical history."},
    "Medication": {"icon": "💊", "title": "Medication Refusal", "role": "Frau Schneider (Stubborn)", "goal": "Explain why meds are needed."},
    "Emergency": {"icon": "🚨", "title": "Emergency Triage", "role": "Visitor (Husband collapsed)", "goal": "Get vitals fast."}
}

# --- 7. LOGIC ---
def process_audio(audio_bytes, scenario_key):
    # 1. Transcribe
    try:
        prompt = "Transcribe this German audio exactly. Output ONLY the German text."
        # Note: We call the API here for the first time
        resp = model.generate_content([prompt, {"mime_type": "audio/mp3", "data": audio_bytes}])
        text = resp.text.strip()
    except Exception as e:
        return None, f"Transcription Error: {str(e)}"

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
    try:
        res = model.generate_content(f"{analysis_prompt}\nUser: {text}", generation_config={"response_mime_type": "application/json"})
        data = json.loads(res.text)
        return text, data
    except Exception as e:
        return text, None

def text_to_speech(text):
    try:
        tts = gTTS(text=text, lang='de')
        buf = io.BytesIO()
        tts.write_to_fp(buf)
        buf.seek(0)
        return buf
    except:
        return None

# --- 8. MAIN UI ---
st.title("🩺 CareLingo")

# SCENARIO SELECTOR
if not st.session_state.scenario:
    st.subheader("Select Scenario")
    
    c1, c2, c3 = st.columns(3)
    
    with c1:
        st.markdown(f"<div class='scenario-card' style='font-size:3rem'>{SCENARIOS['Admission']['icon']}</div>", unsafe_allow_html=True)
        if st.button("Admission"):
            st.session
