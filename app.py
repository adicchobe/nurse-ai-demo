import streamlit as st
import google.generativeai as genai
from gtts import gTTS
import os
import json
import io

# --- 1. CONFIGURATION & STYLE ---
st.set_page_config(page_title="CareLingo", page_icon="🩺", layout="centered")

# Minimal, Safe CSS for Dark Mode & Clean Look
st.markdown("""
<style>
    /* Force simple white text for headers in Dark Mode */
    h1, h2, h3 {
        color: #FFFFFF !important;
    }
    
    /* Hide the annoying 'Press Enter to apply' text */
    div[data-testid="InputInstructions"] > span {
        display: none;
    }
    
    /* Scenario Cards Styling */
    .scenario-card {
        background-color: #1E293B;
        padding: 1rem;
        border-radius: 10px;
        border: 1px solid #334155;
        text-align: center;
        margin-bottom: 10px;
    }
    
    /* Clean up buttons */
    .stButton button {
        width: 100%;
        font-weight: 600;
        border-radius: 8px;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. AUTHENTICATION ---
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("🚨 System Error: API Key Missing.")
    st.stop()

if "APP_PASSWORD" in st.secrets:
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    
    if not st.session_state.authenticated:
        st.markdown("<h1 style='text-align: center;'>🔒 Login</h1>", unsafe_allow_html=True)
        
        # Using a Form forces the button to align perfectly with the input
        with st.form("login_form"):
            user_pwd = st.text_input("Enter Access Password", type="password")
            submitted = st.form_submit_button("Login")
            
            if submitted:
                if user_pwd == st.secrets["APP_PASSWORD"]:
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("Incorrect Password")
        st.stop()

# --- 3. RELIABLE MODEL CONNECTION ---
# No complex logic. Just connect to the one that works.
@st.cache_resource
def load_model():
    # Try the standard flash model first
    try:
        return genai.GenerativeModel("gemini-1.5-flash")
    except:
        return None

model = load_model()

if not model:
    st.error("⚠️ Connection Error. Please refresh the page.")
    st.stop()

# --- 4. SESSION STATE ---
if "messages" not in st.session_state: st.session_state.messages = []
if "scenario" not in st.session_state: st.session_state.scenario = None
if "feedback" not in st.session_state: st.session_state.feedback = None
if "last_audio_id" not in st.session_state: st.session_state.last_audio_id = None

# --- 5. SCENARIOS ---
SCENARIOS = {
    "Admission": {
        "title": "Patient Admission",
        "desc": "Collect history from an anxious patient.",
        "role": "You are Herr Müller. Anxious, speaks only German.",
        "goal": "Collect patient history.",
        "icon": "📋"
    },
    "Medication": {
        "title": "Medication Refusal",
        "desc": "Convince a patient to take pills.",
        "role": "You are Frau Schneider. You refuse pills.",
        "goal": "Explain necessity.",
        "icon": "💊"
    },
    "Emergency": {
        "title": "Emergency Triage",
        "desc": "Handle a collapsed visitor scenario.",
        "role": "You are a visitor whose husband collapsed.",
        "goal": "Get vitals fast.",
        "icon": "🚨"
    }
}

# --- 6. CORE LOGIC ---
def transcribe_audio(audio_bytes):
    try:
        prompt = "Transcribe this German audio exactly. Output ONLY the German text."
        response = model.generate_content([prompt, {"mime_type": "audio/mp3", "data": audio_bytes}])
        return response.text.strip()
    except:
        return None

def get_feedback(user_text, scenario_key):
    scen = SCENARIOS[scenario_key]
    system_prompt = f"""
    Act as a German tutor. Role: {scen['role']}. Goal: {scen['goal']}.
    1. Reply naturally in German (Short).
    2. Analyze user's German.
    Output JSON: {{
        "response_text": "German reply",
        "feedback": {{
            "grammar": (1-10), "politeness": (1-10), "medical": (1-10),
            "critique": "Tip in English", "better_phrase": "German correction"
        }}
    }}
    """
    try:
        res = model.generate_content(f"{system_prompt}\nUser: {user_text}", generation_config={"response_mime_type": "application/json"})
        return json.loads(res.text)
    except:
        return None

def text_to_speech(text):
    try:
        tts = gTTS(text=text, lang='de')
        buf = io.BytesIO()
        tts.write_to_fp(buf)
        buf.seek(0)
        return buf
    except:
        return None

# --- 7. MAIN UI ---
st.title("🩺 CareLingo")

if not st.session_state.scenario:
    st.subheader("Select a scenario to practice")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown(f"<div style='font-size:3rem; text-align:center;'>{SCENARIOS['Admission']['icon']}</div>", unsafe_allow_html=True)
        if st.button("Admission"):
            st.session_state.scenario = "Admission"
            st.rerun()
        st.caption(SCENARIOS['Admission']['desc'])

    with col2:
        st.markdown(f"<div style='font-size:3rem; text-align:center;'>{SCENARIOS['Medication']['icon']}</div>", unsafe_allow_html=True)
        if st.button("Medication"):
            st.session_state.scenario = "Medication"
            st.rerun()
        st.caption(SCENARIOS['Medication']['desc'])

    with col3:
        st.markdown(f"<div style='font-size:3rem; text-align:center;'>{SCENARIOS['Emergency']['icon']}</div>", unsafe_allow_html=True)
        if st.button("Emergency"):
            st.session_state.scenario = "Emergency"
            st.rerun()
        st.caption(SCENARIOS['Emergency']['desc'])

else:
    # Top Bar
    curr = SCENARIOS[st.session_state.scenario]
    c1, c2 = st.columns([1, 4])
    with c1:
        if st.button("← Back"):
            st.session_state.scenario = None
            st.session_state.messages = []
            st.session_state.feedback = None
            st.rerun()
    with c2:
        st.markdown(f"### {curr['icon']} {curr['title']}")
    
    st.divider()

    # Chat
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"], avatar="👤" if msg["role"]=="user" else "🤖"):
            st.write(msg["content"])
    
    # Feedback Card
    if st.session_state.feedback:
        f = st.session_state.feedback
        st.info("📊 **Teacher's Analysis**")
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Grammar", f"{f.get('grammar',0)}/10")
        c2.metric("Politeness", f"{f.get('politeness',0)}/10")
        c3.metric("Medical", f"{f.get('medical',0)}/10")
        
        st.warning(f"💡 **Tip:** {f.get('critique', 'N/A')}")
        st.success(f"🗣️ **Better:** \"{f.get('better_phrase', 'N/A')}\"")
        
        if st.button("🔄 Redo Last Turn"):
            if len(st.session_state.messages) >= 2:
                st.session_state.messages.pop()
                st.session_state.messages.pop()
                st.session_state.feedback = None
                st.rerun()

    # Audio Input
    st.markdown("###")
    audio = st.audio_input("Tap to Speak...")
    
    if audio:
        bytes_data = audio.read()
        aid = hash(bytes_data)
        if aid != st.session_state.last_audio_id:
            st.session_state.last_audio_id = aid
            
            with st.spinner("Listening..."):
                txt = transcribe_audio(bytes_data)
            
            if txt:
                st.session_state.messages.append({"role": "user", "content": txt})
                with st.spinner("Thinking..."):
                    data = get_feedback(txt, st.session_state.scenario)
                    if data:
                        st.session_state.feedback = data["feedback"]
                        st.session_state.messages.append({"role": "assistant", "content": data["response_text"]})
                        mp3 = text_to_speech(data["response_text"])
                        if mp3: st.audio(mp3, format="audio/mp3", autoplay=True)
                st.rerun()
