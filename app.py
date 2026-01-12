import streamlit as st
import google.generativeai as genai
from gtts import gTTS
import os
import json
import io

# --- 1. CONFIGURATION & STYLE ---
st.set_page_config(page_title="CareLingo", page_icon="🩺", layout="centered")

# Custom CSS for "Apple-esque" Dark Mode Support
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    
    /* Adaptive Headers */
    .main-header {
        font-weight: 700;
        font-size: 2.5rem;
        text-align: center;
        margin-bottom: 0.5rem;
        background: -webkit-linear-gradient(45deg, #3B82F6, #8B5CF6);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    
    .sub-header {
        font-size: 1.1rem;
        text-align: center;
        margin-bottom: 2rem;
        opacity: 0.8;
    }

    /* Scenario Cards (Dark Mode Friendly) */
    .scenario-card {
        background-color: #1E293B; /* Slate 800 */
        padding: 1.5rem;
        border-radius: 16px;
        border: 1px solid #334155;
        text-align: center;
        transition: transform 0.2s;
        color: white;
    }
    
    /* Styled Buttons */
    .stButton button {
        border-radius: 12px;
        font-weight: 600;
        width: 100%;
        border: 1px solid #475569;
        transition: all 0.2s;
    }
    
    /* Feedback Box */
    .feedback-container {
        background: rgba(255, 255, 255, 0.05); /* Subtle glass effect */
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 16px;
        padding: 1.5rem;
        margin-top: 2rem;
    }
    
    /* Hide the 'Press Enter to apply' text */
    .stDeployButton {display:none;}
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
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown("<h1 style='text-align: center;'>🔒 Login</h1>", unsafe_allow_html=True)
        
        # FIXED: Using a form aligns the button perfectly
        with st.form("login_form"):
            user_pwd = st.text_input("Enter Access Password", type="password")
            submit = st.form_submit_button("Enter CareLingo", use_container_width=True)
            
            if submit:
                if user_pwd == st.secrets["APP_PASSWORD"]:
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("Incorrect Password")
        st.stop()

# --- 3. ROBUST MODEL LOADER (The Fix) ---
@st.cache_resource
def load_working_model():
    # Priority list: Unlimited -> Experimental -> Standard
    candidates = [
        "gemini-2.5-flash-native-audio-dialog", 
        "gemini-2.0-flash-exp",
        "gemini-1.5-flash",
        "models/gemini-1.5-flash"
    ]
    for name in candidates:
        try:
            model = genai.GenerativeModel(name)
            # Silent Test
            model.generate_content("Hi")
            return model
        except:
            continue
    return None

model = load_working_model()

if not model:
    st.error("⚠️ AI Service Busy. Please wait 1 minute and refresh.")
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
    except Exception as e:
        # Pass actual error to UI for debugging if needed, but keep it clean
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

# --- 7. UI LAYOUT ---

# Header
st.markdown('<div class="main-header">CareLingo</div>', unsafe_allow_html=True)

if not st.session_state.scenario:
    st.markdown('<div class="sub-header">Select a scenario to begin practice</div>', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown(f"<div style='text-align:center; font-size:3rem;'>{SCENARIOS['Admission']['icon']}</div>", unsafe_allow_html=True)
        if st.button("Start Admission", use_container_width=True):
            st.session_state.scenario = "Admission"
            st.rerun()
        st.markdown(f"<div style='text-align:center; opacity:0.7;'>{SCENARIOS['Admission']['desc']}</div>", unsafe_allow_html=True)

    with col2:
        st.markdown(f"<div style='text-align:center; font-size:3rem;'>{SCENARIOS['Medication']['icon']}</div>", unsafe_allow_html=True)
        if st.button("Start Medication", use_container_width=True):
            st.session_state.scenario = "Medication"
            st.rerun()
        st.markdown(f"<div style='text-align:center; opacity:0.7;'>{SCENARIOS['Medication']['desc']}</div>", unsafe_allow_html=True)

    with col3:
        st.markdown(f"<div style='text-align:center; font-size:3rem;'>{SCENARIOS['Emergency']['icon']}</div>", unsafe_allow_html=True)
        if st.button("Start Emergency", use_container_width=True):
            st.session_state.scenario = "Emergency"
            st.rerun()
        st.markdown(f"<div style='text-align:center; opacity:0.7;'>{SCENARIOS['Emergency']['desc']}</div>", unsafe_allow_html=True)

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
        st.markdown(f"**{curr['icon']} {curr['title']}**")
    
    st.divider()

    # Chat Area
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"], avatar="👤" if msg["role"]=="user" else "🤖"):
            st.write(msg["content"])
    
    # Visual Feedback
    if st.session_state.feedback:
        f = st.session_state.feedback
        st.markdown('<div class="feedback-container">', unsafe_allow_html=True)
        st.caption("TEACHER'S ANALYSIS")
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Grammar", f"{f.get('grammar',0)}/10")
        m2.metric("Politeness", f"{f.get('politeness',0)}/10")
        m3.metric("Medical", f"{f.get('medical',0)}/10")
        
        st.markdown("---")
        st.info(f"💡 {f.get('critique', 'N/A')}")
        st.success(f"🗣️ **Better:** \"{f.get('better_phrase', 'N/A')}\"")
        
        if st.button("🔄 Redo Last Turn"):
            if len(st.session_state.messages) >= 2:
                st.session_state.messages.pop()
                st.session_state.messages.pop()
                st.session_state.feedback = None
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

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
                with st.spinner("Analyzing..."):
                    data = get_feedback(txt, st.session_state.scenario)
                    if data:
                        st.session_state.feedback = data["feedback"]
                        st.session_state.messages.append({"role": "assistant", "content": data["response_text"]})
                        
                        mp3 = text_to_speech(data["response_text"])
                        if mp3: st.audio(mp3, format="audio/mp3", autoplay=True)
                st.rerun()
            else:
                st.error("Could not hear audio. Please try again.")
