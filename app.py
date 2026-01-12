import streamlit as st
import google.generativeai as genai
from gtts import gTTS
import os
import json
import io

# --- 1. APP CONFIGURATION & STYLING ---
st.set_page_config(page_title="CareLingo", page_icon="🩺", layout="centered")

# Custom "Apple-esque" CSS
st.markdown("""
<style>
    /* Global Font & Background */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    
    /* Clean Header */
    .main-header {
        font-weight: 700;
        font-size: 2.5rem;
        color: #1E293B;
        text-align: center;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1.1rem;
        color: #64748B;
        text-align: center;
        margin-bottom: 2rem;
    }

    /* Card Styling (Apple Style) */
    .stButton button {
        background-color: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 16px;
        padding: 1rem;
        font-weight: 600;
        color: #334155;
        transition: all 0.2s ease;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        width: 100%;
    }
    
    .stButton button:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
        border-color: #3B82F6;
        color: #3B82F6;
    }

    /* Feedback Box Styling (Glassmorphism) */
    .feedback-box {
        background: rgba(255, 255, 255, 0.8);
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 1.5rem;
        margin-top: 1.5rem;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
    }
    
    /* Metrics */
    div[data-testid="stMetricValue"] {
        font-size: 1.8rem;
        font-weight: 700;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. AUTHENTICATION & API SETUP ---
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
        user_pwd = st.text_input("Password", type="password")
        if st.button("Enter Access"):
            if user_pwd == st.secrets["APP_PASSWORD"]:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Access Denied.")
        st.stop()

# --- 3. LOGIC: MODEL HUNTER ---
# (Keeping your robust logic, just hiding it from the UI view)
@st.cache_resource
def get_best_model():
    # Priority: Unlimited Native -> Unlimited Preview -> Standard
    candidates = [
        "gemini-2.5-flash-native-audio-dialog",
        "gemini-2.0-flash-exp",
        "models/gemini-1.5-flash",
        "gemini-1.5-flash"
    ]
    for name in candidates:
        try:
            model = genai.GenerativeModel(name)
            model.generate_content("Ping")
            return model, name
        except:
            continue
    return None, None

model, model_name = get_best_model()
if not model:
    st.error("❌ Service Unavailable. Please check API Quota.")
    st.stop()

# --- 4. SESSION MANAGEMENT ---
if "messages" not in st.session_state: st.session_state.messages = []
if "scenario" not in st.session_state: st.session_state.scenario = None
if "feedback" not in st.session_state: st.session_state.feedback = None
if "last_audio_id" not in st.session_state: st.session_state.last_audio_id = None
if "recording_count" not in st.session_state: st.session_state.recording_count = 0
MAX_RECORDINGS = 20

# --- 5. SCENARIO DATA (Enhanced Visuals) ---
SCENARIOS = {
    "Admission": {
        "title": "Patient Admission",
        "desc": "Collect history from an anxious new patient.",
        "role": "You are Herr Müller. Anxious, speaks only German.",
        "goal": "Get medical history.",
        "icon": "📋"
    },
    "Medication": {
        "title": "Medication Refusal",
        "desc": "Convince a patient to take their pills.",
        "role": "You are Frau Schneider. You refuse pills.",
        "goal": "Explain necessity.",
        "icon": "💊"
    },
    "Emergency": {
        "title": "Emergency Triage",
        "desc": "Handle a collapsed visitor scenario.",
        "role": "Visitor whose husband collapsed.",
        "goal": "Get vitals fast.",
        "icon": "🚨"
    }
}

# --- 6. CORE AI FUNCTIONS ---
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
    Roleplay as: {scen['role']}
    Goal: {scen['goal']}
    Language: German.
    Output JSON: {{
        "response_text": "German reply",
        "feedback": {{
            "grammar": (1-10), "politeness": (1-10), "medical": (1-10),
            "critique": "Short English tip", "better_phrase": "German correction"
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

# --- 7. MAIN UI LAYOUT ---

# Header
st.markdown('<div class="main-header">🩺 CareLingo</div>', unsafe_allow_html=True)

# Scenario Selection (The "Apple" Grid)
if not st.session_state.scenario:
    st.markdown('<div class="sub-header">Select a scenario to begin practice</div>', unsafe_allow_html=True)
    
    # 3-Column Layout for "Cards"
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.write(f"# {SCENARIOS['Admission']['icon']}")
        if st.button("Start Admission", use_container_width=True):
            st.session_state.scenario = "Admission"
            st.rerun()
        st.caption(SCENARIOS['Admission']['desc'])
        
    with col2:
        st.write(f"# {SCENARIOS['Medication']['icon']}")
        if st.button("Start Medication", use_container_width=True):
            st.session_state.scenario = "Medication"
            st.rerun()
        st.caption(SCENARIOS['Medication']['desc'])
        
    with col3:
        st.write(f"# {SCENARIOS['Emergency']['icon']}")
        if st.button("Start Emergency", use_container_width=True):
            st.session_state.scenario = "Emergency"
            st.rerun()
        st.caption(SCENARIOS['Emergency']['desc'])

# Active Session View
else:
    curr_scen = SCENARIOS[st.session_state.scenario]
    
    # Top Bar: Back Button & Progress
    c1, c2 = st.columns([1, 4])
    with c1:
        if st.button("← End Session"):
            st.session_state.scenario = None
            st.session_state.messages = []
            st.session_state.feedback = None
            st.rerun()
    with c2:
        # Styled Progress
        prog = st.session_state.recording_count / MAX_RECORDINGS
        st.progress(prog)
        st.caption(f"Session Progress: {st.session_state.recording_count}/{MAX_RECORDINGS}")

    st.markdown("---")
    
    # Context Header
    st.markdown(f"### {curr_scen['icon']} {curr_scen['title']}")
    st.info(f"**Your Role:** Nurse | **Goal:** {curr_scen['goal']}")

    # Chat Area
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"], avatar="👤" if msg["role"]=="user" else "🤖"):
            st.write(msg["content"])

    # Teacher Feedback Card (The Visual Upgrade)
    if st.session_state.feedback:
        f = st.session_state.feedback
        st.markdown('<div class="feedback-box">', unsafe_allow_html=True)
        st.markdown("##### 👩‍🏫 Analysis")
        
        # Metrics Row
        m1, m2, m3 = st.columns(3)
        m1.metric("Grammar", f"{f.get('grammar',0)}/10", delta_color="normal")
        m2.metric("Politeness", f"{f.get('politeness',0)}/10", delta_color="normal")
        m3.metric("Medical", f"{f.get('medical',0)}/10", delta_color="normal")
        
        # Correction Box
        st.warning(f"💡 **Tip:** {f.get('critique', 'N/A')}")
        st.success(f"🗣️ **Try saying:** \"{f.get('better_phrase', 'N/A')}\"")
        
        st.markdown('</div>', unsafe_allow_html=True)

        # "Redo" Logic (Bonus Feature)
        if st.button("🔄 Redo Last Turn", help="Remove the last exchange and try again"):
            if len(st.session_state.messages) >= 2:
                st.session_state.messages.pop()
                st.session_state.messages.pop()
                st.session_state.feedback = None
                st.session_state.recording_count -= 1
                st.rerun()

    # Input Area
    st.markdown("###") # Spacer
    audio_val = st.audio_input("Tap to Speak...")
    
    if audio_val:
        # Processing Logic (Unchanged)
        audio_bytes = audio_val.read()
        aid = hash(audio_bytes)
        if aid != st.session_state.last_audio_id:
            st.session_state.last_audio_id = aid
            st.session_state.recording_count += 1
            
            with st.spinner("Listening..."):
                txt = transcribe_audio(audio_bytes)
            
            if txt:
                st.session_state.messages.append({"role": "user", "content": txt})
                with st.spinner("Analyzing..."):
                    ai_dat = get_feedback(txt, st.session_state.scenario)
                    if ai_dat:
                        resp = ai_dat["response_text"]
                        st.session_state.feedback = ai_dat["feedback"]
                        st.session_state.messages.append({"role": "assistant", "content": resp})
                        aud_st = text_to_speech(resp)
                        if aud_st: st.audio(aud_st, format="audio/mp3", autoplay=True)
                st.rerun()
