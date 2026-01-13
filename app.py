import streamlit as st
import google.generativeai as genai
from gtts import gTTS
import os
import json
import io

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="CareLingo", page_icon="🩺", layout="centered")

# Custom CSS (Kept the Apple Look, but safe)
st.markdown("""
<style>
    /* Global Fonts & Colors */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    h1, h2, h3, h4 { color: #FFFFFF !important; }
    
    /* Scenario Cards */
    .scenario-card {
        background-color: #1E293B;
        padding: 1rem;
        border-radius: 12px;
        border: 1px solid #334155;
        text-align: center;
        margin-bottom: 10px;
    }
    
    /* Hide the 'Press Enter' hint */
    div[data-testid="InputInstructions"] > span { display: none; }
    
    /* Make buttons look clickable */
    .stButton button {
        width: 100%;
        font-weight: 600;
        border-radius: 8px;
        border: 1px solid #475569;
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
        with st.form("login"):
            pwd = st.text_input("Password", type="password")
            if st.form_submit_button("Enter"):
                if pwd == st.secrets["APP_PASSWORD"]:
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("Incorrect.")
        st.stop()

# --- 3. MODEL CONNECTION ---
@st.cache_resource
def load_model():
    return genai.GenerativeModel("gemini-1.5-flash")

model = load_model()

# --- 4. SESSION STATE ---
if "messages" not in st.session_state: st.session_state.messages = []
if "scenario" not in st.session_state: st.session_state.scenario = None
if "feedback" not in st.session_state: st.session_state.feedback = None
if "last_audio_id" not in st.session_state: st.session_state.last_audio_id = None

# --- 5. SCENARIOS ---
SCENARIOS = {
    "Admission": {"icon": "📋", "title": "Admission", "role": "Herr Müller (Anxious Patient)", "goal": "Get history."},
    "Medication": {"icon": "💊", "title": "Medication", "role": "Frau Schneider (Refuses Pills)", "goal": "Explain why."},
    "Emergency": {"icon": "🚨", "title": "Emergency", "role": "Visitor (Husband Collapsed)", "goal": "Get vitals."}
}

# --- 6. CORE FUNCTIONS ---
def process_conversation(audio_bytes, scenario_key):
    # 1. Transcribe
    prompt = "Transcribe German audio. Output ONLY text."
    try:
        resp = model.generate_content([prompt, {"mime_type": "audio/mp3", "data": audio_bytes}])
        user_text = resp.text.strip()
    except:
        return None, None, None

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
        res = model.generate_content(f"{analysis_prompt}\nUser: {user_text}", generation_config={"response_mime_type": "application/json"})
        data = json.loads(res.text)
        
        # 3. Audio Reply
        tts = gTTS(text=data["response_text"], lang='de')
        mp3 = io.BytesIO()
        tts.write_to_fp(mp3)
        mp3.seek(0)
        
        return user_text, data, mp3
    except:
        return user_text, None, None

# --- 7. MAIN UI ---
st.title("🩺 CareLingo")

# SCENARIO SELECTION
if not st.session_state.scenario:
    st.subheader("Select Scenario:")
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button(f"{SCENARIOS['Admission']['icon']} Admission"):
            st.session_state.scenario = "Admission"
            st.rerun()
    with c2:
        if st.button(f"{SCENARIOS['Medication']['icon']} Medication"):
            st.session_state.scenario = "Medication"
            st.rerun()
    with c3:
        if st.button(f"{SCENARIOS['Emergency']['icon']} Emergency"):
            st.session_state.scenario = "Emergency"
            st.rerun()

# ACTIVE PRACTICE
else:
    curr = SCENARIOS[st.session_state.scenario]
    
    # Header
    col_a, col_b = st.columns([1, 4])
    with col_a:
        if st.button("← Back"):
            st.session_state.scenario = None
            st.session_state.messages = []
            st.session_state.feedback = None
            st.rerun()
    with col_b:
        st.markdown(f"### {curr['title']}")
        st.caption(f"Role: Nurse | Goal: {curr['goal']}")
    
    st.divider()

    # Chat History
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])
            
    # Feedback Display
    if st.session_state.feedback:
        f = st.session_state.feedback
        with st.expander("📊 Teacher's Feedback", expanded=True):
            cols = st.columns(3)
            cols[0].metric("Grammar", f"{f.get('grammar',0)}/10")
            cols[1].metric("Politeness", f"{f.get('politeness',0)}/10")
            cols[2].metric("Medical", f"{f.get('medical',0)}/10")
            st.info(f"💡 {f.get('critique', '')}")
            st.success(f"🗣️ Better: \"{f.get('better_phrase', '')}\"")

    # INPUT AREA
    st.markdown("---")
    st.caption("👇 Tap microphone. Recording sends automatically when you click Done.")
    
    # The Audio Input
    audio = st.audio_input("Record Response", label_visibility="collapsed")
    
    # PROCESS LOGIC
    if audio:
        # Check if this is new audio
        file_id = hash(audio.getvalue())
        if file_id != st.session_state.last_audio_id:
            st.session_state.last_audio_id = file_id
            
            # SHOW STATUS (The UX Fix)
            status = st.status("✅ Audio captured! Processing...", expanded=True)
            
            status.write("📝 Transcribing...")
            user_text, ai_data, audio_reply = process_conversation(audio.read(), st.session_state.scenario)
            
            if user_text and ai_data:
                status.write("🧠 Analyzing...")
                # Update State
                st.session_state.messages.append({"role": "user", "content": user_text})
                st.session_state.feedback = ai_data["feedback"]
                st.session_state.messages.append({"role": "assistant", "content": ai_data["response_text"]})
                
                status.update(label="Complete!", state="complete", expanded=False)
                
                # Auto-play audio
                if audio_reply:
                    st.audio(audio_reply, format="audio/mp3", autoplay=True)
                
                st.rerun()
            else:
                status.update(label="Error connecting to AI", state="error")
