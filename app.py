import streamlit as st
import google.generativeai as genai
from gtts import gTTS
import os
import json
import io

# --- 1. APP CONFIGURATION & VISUALS ---
st.set_page_config(page_title="CareLingo", page_icon="🩺", layout="centered")

# Custom "Apple-esque" CSS (San Francisco Font, Rounded Cards, Soft Shadows)
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
        color: #1E293B;
    }
    
    /* Header Styling */
    .main-header {
        font-weight: 700;
        font-size: 2.2rem;
        color: #0F172A;
        text-align: center;
        letter-spacing: -0.02em;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1.0rem;
        color: #64748B;
        text-align: center;
        margin-bottom: 2.5rem;
    }

    /* Scenario Cards */
    .scenario-card {
        background-color: white;
        padding: 1.5rem;
        border-radius: 16px;
        border: 1px solid #E2E8F0;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        text-align: center;
        transition: transform 0.2s;
        height: 100%;
    }
    .scenario-icon {
        font-size: 2.5rem;
        margin-bottom: 1rem;
    }
    
    /* Buttons (Apple Style) */
    .stButton button {
        border-radius: 12px;
        font-weight: 600;
        border: 1px solid #E2E8F0;
        box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
        transition: all 0.2s;
    }
    .stButton button:hover {
        border-color: #3B82F6;
        color: #3B82F6;
        transform: translateY(-1px);
    }

    /* Feedback Card (Glass) */
    .feedback-container {
        background: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 16px;
        padding: 1.5rem;
        margin-top: 2rem;
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
        st.markdown("<h2 style='text-align: center;'>🔒 Login</h2>", unsafe_allow_html=True)
        user_pwd = st.text_input("Enter Password", type="password")
        if st.button("Enter CareLingo", use_container_width=True):
            if user_pwd == st.secrets["APP_PASSWORD"]:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Incorrect Password")
        st.stop()

# --- 3. SESSION STATE ---
if "messages" not in st.session_state: st.session_state.messages = []
if "scenario" not in st.session_state: st.session_state.scenario = None
if "feedback" not in st.session_state: st.session_state.feedback = None
if "last_audio_id" not in st.session_state: st.session_state.last_audio_id = None

# --- 4. SCENARIO DATA ---
SCENARIOS = {
    "Admission": {
        "title": "Patient Admission",
        "desc": "Collect medical history from a nervous new patient.",
        "role": "You are Herr Müller. You are anxious and speak only German.",
        "goal": "Collect patient history.",
        "icon": "📋"
    },
    "Medication": {
        "title": "Medication Refusal",
        "desc": "Convince a stubborn patient to take their pills.",
        "role": "You are Frau Schneider. You refuse to take pills.",
        "goal": "Explain why medication is needed.",
        "icon": "💊"
    },
    "Emergency": {
        "title": "Emergency Triage",
        "desc": "Gather vitals from a visitor whose husband collapsed.",
        "role": "You are a visitor whose husband collapsed.",
        "goal": "Get details fast.",
        "icon": "🚨"
    }
}

# --- 5. ROBUST AI FUNCTIONS ---
def get_model():
    # Silent fallback logic - no crashing allowed
    try:
        return genai.GenerativeModel("gemini-1.5-flash")
    except:
        return None

model = get_model()

def transcribe_audio(audio_bytes):
    try:
        prompt = "Transcribe this German audio exactly. Output ONLY the German text."
        response = model.generate_content([prompt, {"mime_type": "audio/mp3", "data": audio_bytes}])
        return response.text.strip()
    except Exception as e:
        return f"Error: {str(e)}"

def get_feedback(user_text, scenario_key):
    scen = SCENARIOS[scenario_key]
    system_prompt = f"""
    Act as a German tutor. 
    Scenario Role: {scen['role']}
    User Goal: {scen['goal']}
    
    1. Reply naturally in German (Keep it short).
    2. Analyze the user's German.
    
    Return JSON:
    {{
        "response_text": "German reply",
        "feedback": {{
            "grammar": (1-10), "politeness": (1-10), "medical": (1-10),
            "critique": "Short English tip", "better_phrase": "Correction"
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

# --- 6. MAIN UI LAYOUT ---

# Header
st.markdown('<div class="main-header">CareLingo</div>', unsafe_allow_html=True)

# SCENARIO SELECTION (Apple Grid Layout)
if not st.session_state.scenario:
    st.markdown('<div class="sub-header">Select a scenario to begin practice</div>', unsafe_allow_html=True)
    
    c1, c2, c3 = st.columns(3)
    
    with c1:
        st.markdown(f"<div class='scenario-icon'>{SCENARIOS['Admission']['icon']}</div>", unsafe_allow_html=True)
        if st.button("Start Admission", key="btn_adm", use_container_width=True):
            st.session_state.scenario = "Admission"
            st.rerun()
        st.caption(SCENARIOS['Admission']['desc'])
        
    with c2:
        st.markdown(f"<div class='scenario-icon'>{SCENARIOS['Medication']['icon']}</div>", unsafe_allow_html=True)
        if st.button("Start Medication", key="btn_med", use_container_width=True):
            st.session_state.scenario = "Medication"
            st.rerun()
        st.caption(SCENARIOS['Medication']['desc'])
        
    with c3:
        st.markdown(f"<div class='scenario-icon'>{SCENARIOS['Emergency']['icon']}</div>", unsafe_allow_html=True)
        if st.button("Start Emergency", key="btn_emg", use_container_width=True):
            st.session_state.scenario = "Emergency"
            st.rerun()
        st.caption(SCENARIOS['Emergency']['desc'])

# ACTIVE PRACTICE SESSION
else:
    scen_data = SCENARIOS[st.session_state.scenario]
    
    # Navigation Bar
    col_back, col_title = st.columns([1, 5])
    with col_back:
        if st.button("← End Session"):
            st.session_state.scenario = None
            st.session_state.messages = []
            st.session_state.feedback = None
            st.rerun()
            
    with col_title:
        st.markdown(f"**{scen_data['icon']} {scen_data['title']}**")
    
    st.divider()

    # Chat Interface
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"], avatar="👤" if msg["role"]=="user" else "🤖"):
            st.write(msg["content"])
            
    # VISUAL FEEDBACK CARD (The "Apple" Element)
    if st.session_state.feedback:
        f = st.session_state.feedback
        
        st.markdown('<div class="feedback-container">', unsafe_allow_html=True)
        st.caption("TEACHER'S ANALYSIS")
        
        # Big Scores
        c1, c2, c3 = st.columns(3)
        c1.metric("Grammar", f"{f.get('grammar',0)}/10")
        c2.metric("Politeness", f"{f.get('politeness',0)}/10")
        c3.metric("Medical", f"{f.get('medical',0)}/10")
        
        st.markdown("---")
        st.info(f"💡 **Tip:** {f.get('critique', 'N/A')}")
        st.success(f"🗣️ **Better:** \"{f.get('better_phrase', 'N/A')}\"")
        
        # Redo Button (Bonus Feature)
        if st.button("🔄 Redo Last Turn", help="Try this sentence again"):
            if len(st.session_state.messages) >= 2:
                st.session_state.messages.pop()
                st.session_state.messages.pop()
                st.session_state.feedback = None
                st.rerun()
                
        st.markdown('</div>', unsafe_allow_html=True)

    # Audio Input at Bottom
    st.markdown("###")
    audio_val = st.audio_input("Tap microphone to speak...")
    
    if audio_val:
        audio_bytes = audio_val.read()
        aid = hash(audio_bytes)
        
        if aid != st.session_state.last_audio_id:
            st.session_state.last_audio_id = aid
            
            with st.spinner("Listening..."):
                txt = transcribe_audio(audio_bytes)
            
            if txt and "Error" not in txt:
                st.session_state.messages.append({"role": "user", "content": txt})
                
                with st.spinner("Teacher is analyzing..."):
                    ai_dat = get_feedback(txt, st.session_state.scenario)
                    
                    if ai_dat:
                        resp = ai_dat["response_text"]
                        st.session_state.feedback = ai_dat["feedback"]
                        st.session_state.messages.append({"role": "assistant", "content": resp})
                        
                        aud = text_to_speech(resp)
                        if aud: st.audio(aud, format="audio/mp3", autoplay=True)
                st.rerun()
            elif "Error" in txt:
                st.error("Connection failed. Please try again.")
