import streamlit as st
import google.generativeai as genai
from gtts import gTTS
import os
import json
import io
import time

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="CareLingo", page_icon="🩺", layout="centered")

# --- 2. SAFE STYLING (Works in Light AND Dark Mode) ---
st.markdown("""
<style>
    /* Clean Card Styling that adapts to theme */
    .scenario-card {
        border: 1px solid rgba(128, 128, 128, 0.2);
        border-radius: 12px;
        padding: 20px;
        text-align: center;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
        transition: transform 0.2s;
    }
    .scenario-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 12px rgba(0, 0, 0, 0.1);
    }
    
    /* Hide the 'Press Enter' hint */
    div[data-testid="InputInstructions"] > span { display: none; }
    
    /* Make buttons full width and styled */
    div.stButton > button {
        width: 100%;
        border-radius: 8px;
        font-weight: 600;
        padding: 0.5rem 1rem;
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
        st.markdown("# 🔒 Login")
        with st.form("login_form"):
            pwd = st.text_input("Password", type="password")
            if st.form_submit_button("Enter"):
                if pwd == st.secrets["APP_PASSWORD"]:
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("Incorrect Password")
        st.stop()

# --- 4. ROBUST MODEL CONNECTION ---
@st.cache_resource
def load_model():
    # Simple list of models to try. No complex logic.
    candidates = ["gemini-1.5-flash", "models/gemini-1.5-flash", "gemini-2.0-flash-exp"]
    for name in candidates:
        try:
            model = genai.GenerativeModel(name)
            model.generate_content("Ping") # Test connection
            return model
        except:
            continue
    return None

model = load_model()
if not model:
    st.error("⚠️ AI Service is busy. Please refresh the page.")
    st.stop()

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

# --- 7. CORE LOGIC ---
def process_audio(audio_bytes, scenario_key):
    # 1. Transcribe
    prompt = "Transcribe this German audio exactly. Output ONLY the German text."
    try:
        resp = model.generate_content([prompt, {"mime_type": "audio/mp3", "data": audio_bytes}])
        text = resp.text.strip()
    except:
        return None, None

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

# SCENARIO SELECTOR (Grid Layout)
if not st.session_state.scenario:
    st.markdown("### Select a Scenario")
    
    c1, c2, c3 = st.columns(3)
    
    with c1:
        st.markdown(f"<div class='scenario-card' style='font-size: 3rem;'>{SCENARIOS['Admission']['icon']}</div>", unsafe_allow_html=True)
        if st.button("Admission"):
            st.session_state.scenario = "Admission"
            st.rerun()
            
    with c2:
        st.markdown(f"<div class='scenario-card' style='font-size: 3rem;'>{SCENARIOS['Medication']['icon']}</div>", unsafe_allow_html=True)
        if st.button("Medication"):
            st.session_state.scenario = "Medication"
            st.rerun()
            
    with c3:
        st.markdown(f"<div class='scenario-card' style='font-size: 3rem;'>{SCENARIOS['Emergency']['icon']}</div>", unsafe_allow_html=True)
        if st.button("Emergency"):
            st.session_state.scenario = "Emergency"
            st.rerun()

# ACTIVE SESSION
else:
    curr = SCENARIOS[st.session_state.scenario]
    
    # Navigation
    col_back, col_info = st.columns([1, 4])
    with col_back:
        if st.button("← Back"):
            st.session_state.scenario = None
            st.session_state.messages = []
            st.session_state.feedback = None
            st.rerun()
    with col_info:
        st.info(f"**{curr['icon']} {curr['title']}** | Goal: {curr['goal']}")

    st.divider()

    # Chat History
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"], avatar="👤" if msg["role"]=="user" else "🤖"):
            st.write(msg["content"])

    # Feedback Display (Card)
    if st.session_state.feedback:
        f = st.session_state.feedback
        with st.expander("📊 Teacher's Feedback", expanded=True):
            cols = st.columns(3)
            cols[0].metric("Grammar", f"{f.get('grammar',0)}/10")
            cols[1].metric("Politeness", f"{f.get('politeness',0)}/10")
            cols[2].metric("Medical", f"{f.get('medical',0)}/10")
            st.warning(f"💡 {f.get('critique', 'N/A')}")
            st.success(f"🗣️ Better: \"{f.get('better_phrase', 'N/A')}\"")
    
    # Audio Input Area
    st.markdown("###")
    audio_val = st.audio_input("Tap to Speak...")
    
    if audio_val:
        # Check for new audio
        current_id = hash(audio_val.getvalue())
        if current_id != st.session_state.last_audio_id:
            st.session_state.last_audio_id = current_id
            
            # --- THE UX FIX: VISUAL FEEDBACK ---
            with st.status("✅ Audio captured! Processing...", expanded=True) as status:
                
                st.write("📝 Transcribing audio...")
                user_text, ai_data = process_audio(audio_val.read(), st.session_state.scenario)
                
                if user_text and ai_data:
                    st.write("🧠 Generating feedback...")
                    st.session_state.messages.append({"role": "user", "content": user_text})
                    st.session_state.feedback = ai_data["feedback"]
                    st.session_state.messages.append({"role": "assistant", "content": ai_data["response_text"]})
                    
                    # Generate Audio Reply
                    mp3 = text_to_speech(ai_data["response_text"])
                    status.update(label="Done!", state="complete", expanded=False)
                    
                    if mp3:
                        st.audio(mp3, format="audio/mp3", autoplay=True)
                    
                    time.sleep(1) # Brief pause so user sees "Done"
                    st.rerun()
                else:
                    status.update(label="Error processing audio", state="error")
