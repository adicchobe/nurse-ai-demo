import streamlit as st
import google.generativeai as genai
from gtts import gTTS
import os
import json
import io

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="CareLingo", page_icon="🩺", layout="centered")

# --- 2. MINIMALIST STYLING (Safe & Clean) ---
st.markdown("""
<style>
    /* Global Font */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    
    /* Simple Card Style */
    .scenario-card {
        border: 1px solid #e0e0e0;
        border-radius: 10px;
        padding: 20px;
        text-align: center;
        margin-bottom: 10px;
    }
    
    /* Remove input instructions */
    div[data-testid="InputInstructions"] > span { display: none; }
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
        st.title("🔒 Login")
        pwd = st.text_input("Password", type="password")
        if st.button("Enter"):
            if pwd == st.secrets["APP_PASSWORD"]:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Incorrect Password")
        st.stop()

# --- 4. ROBUST MODEL CONNECTION ---
# This tries the experimental model (which is often unlimited) first, then falls back.
@st.cache_resource
def load_model():
    candidates = ["gemini-2.0-flash-exp", "gemini-1.5-flash", "models/gemini-1.5-flash"]
    for name in candidates:
        try:
            model = genai.GenerativeModel(name)
            model.generate_content("Ping") 
            return model
        except:
            continue
    return None

model = load_model()
if not model:
    st.error("⚠️ AI Service Busy. Please refresh.")
    st.stop()

# --- 5. SESSION STATE ---
if "messages" not in st.session_state: st.session_state.messages = []
if "scenario" not in st.session_state: st.session_state.scenario = None
if "feedback" not in st.session_state: st.session_state.feedback = None
if "last_audio_id" not in st.session_state: st.session_state.last_audio_id = None

# --- 6. SCENARIOS ---
SCENARIOS = {
    "Admission": {"icon": "📋", "title": "Admission", "role": "Herr Müller", "goal": "Collect medical history."},
    "Medication": {"icon": "💊", "title": "Medication", "role": "Frau Schneider", "goal": "Explain why meds are needed."},
    "Emergency": {"icon": "🚨", "title": "Emergency", "role": "Visitor", "goal": "Get vitals fast."}
}

# --- 7. CORE LOGIC ---
def process_audio(audio_bytes, scenario_key):
    # Transcribe
    try:
        prompt = "Transcribe this German audio exactly. Output ONLY the German text."
        resp = model.generate_content([prompt, {"mime_type": "audio/mp3", "data": audio_bytes}])
        text = resp.text.strip()
    except:
        return None, None

    # Analyze
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
    except:
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
        st.markdown(f"<div class='scenario-card'><h1>{SCENARIOS['Admission']['icon']}</h1></div>", unsafe_allow_html=True)
        if st.button("Admission"):
            st.session_state.scenario = "Admission"
            st.rerun()
    with c2:
        st.markdown(f"<div class='scenario-card'><h1>{SCENARIOS['Medication']['icon']}</h1></div>", unsafe_allow_html=True)
        if st.button("Medication"):
            st.session_state.scenario = "Medication"
            st.rerun()
    with c3:
        st.markdown(f"<div class='scenario-card'><h1>{SCENARIOS['Emergency']['icon']}</h1></div>", unsafe_allow_html=True)
        if st.button("Emergency"):
            st.session_state.scenario = "Emergency"
            st.rerun()

# ACTIVE SESSION
else:
    curr = SCENARIOS[st.session_state.scenario]
    
    # Header
    c1, c2 = st.columns([1, 4])
    with c1:
        if st.button("← Back"):
            st.session_state.scenario = None
            st.session_state.messages = []
            st.session_state.feedback = None
            st.rerun()
    with c2:
        st.markdown(f"### {curr['title']}")

    st.divider()

    # Chat History
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    # Feedback Card
    if st.session_state.feedback:
        f = st.session_state.feedback
        with st.expander("📊 Teacher's Feedback", expanded=True):
            cols = st.columns(3)
            cols[0].metric("Grammar", f"{f.get('grammar',0)}/10")
            cols[1].metric("Politeness", f"{f.get('politeness',0)}/10")
            cols[2].metric("Medical", f"{f.get('medical',0)}/10")
            st.info(f"💡 {f.get('critique', 'N/A')}")
            st.success(f"🗣️ Better: \"{f.get('better_phrase', 'N/A')}\"")

    # Audio Input
    st.markdown("###")
    audio_val = st.audio_input("Tap to Speak...")

    if audio_val:
        # Check for new audio
        if st.session_state.last_audio_id != audio_val.file_id:
            st.session_state.last_audio_id = audio_val.file_id
            
            with st.spinner("Processing..."):
                user_text, ai_data = process_audio(audio_val.read(), st.session_state.scenario)
                
                if user_text and ai_data:
                    st.session_state.messages.append({"role": "user", "content": user_text})
                    st.session_state.feedback = ai_data["feedback"]
                    st.session_state.messages.append({"role": "assistant", "content": ai_data["response_text"]})
                    
                    # Audio Reply
                    mp3 = text_to_speech(ai_data["response_text"])
                    if mp3:
                        st.audio(mp3, format="audio/mp3", autoplay=True)
                    
                    st.rerun()
