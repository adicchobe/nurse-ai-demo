import streamlit as st
import google.generativeai as genai
from gtts import gTTS
import os
import json
import io
import time

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="CareLingo", page_icon="🩺", layout="centered")

# --- 2. HIGH-IMPACT CSS ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    
    /* 1. Centered Scenario Cards */
    .scenario-card {
        background: white;
        border-radius: 12px;
        padding: 20px;
        border: 1px solid #e5e7eb;
        text-align: center; /* Center align everything */
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        height: 100%;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        margin-bottom: 15px;
    }
    .scenario-icon { font-size: 3rem; margin-bottom: 10px; }
    .scenario-title { font-weight: 700; font-size: 1.1rem; color: #111; margin-bottom: 5px; }
    .scenario-desc { font-size: 0.9rem; color: #666; margin-bottom: 20px; line-height: 1.4; }
    
    /* 2. Buttons */
    .stButton button {
        width: 100%;
        border-radius: 25px; /* Pill shape for CTA */
        border: none;
        background-color: #f3f4f6;
        color: #374151;
        font-weight: 600;
        transition: all 0.2s;
        margin-top: 10px;
    }
    .stButton button:hover {
        background-color: #3b82f6; /* Blue hover */
        color: white;
        transform: scale(1.02);
        box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
    }
    
    /* 3. THE RECORDER "ALERT" STATE */
    .action-zone {
        background-color: #fff7ed; /* Light Orange/Yellow background */
        border: 2px solid #fdba74; /* Orange Border */
        border-radius: 12px;
        padding: 20px;
        text-align: center;
        margin-top: 20px;
        animation: slideIn 0.5s ease-out;
    }
    .action-header {
        color: #c2410c; /* Dark Orange Text */
        font-weight: 700;
        text-transform: uppercase;
        font-size: 0.85rem;
        letter-spacing: 1px;
        margin-bottom: 10px;
    }
    
    /* 4. The Finger Animation */
    .finger-point {
        font-size: 2rem;
        display: block;
        margin: 0 auto;
        animation: bounce 1.5s infinite;
    }
    
    @keyframes bounce {
        0%, 100% { transform: translateY(0); }
        50% { transform: translateY(-10px); }
    }
    @keyframes slideIn { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }

    /* Hide standard input hints */
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
        st.markdown("<br><br><h1 style='text-align: center;'>🔐 CareLingo</h1>", unsafe_allow_html=True)
        with st.form("login"):
            pwd = st.text_input("Enter Access Code", type="password")
            if st.form_submit_button("Start Practice Session 🚀"):
                if pwd == st.secrets["APP_PASSWORD"]:
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("⚠️ Invalid Code")
        st.stop()

# --- 4. MODEL SETTINGS ---
st.title("🩺 CareLingo")

# Collapsed settings
with st.expander("⚙️ Settings", expanded=False):
    c1, c2 = st.columns([3, 1])
    with c1:
        # Prioritizing the "Green" models from your screenshot
        model_choice = st.selectbox("AI Model:", [
            "gemini-2.5-flash-lite", 
            "gemini-2.0-flash-exp", 
            "gemini-1.5-flash"
        ])
    with c2:
        st.write("") 
        if st.button("↻ Reset"):
            st.session_state.clear()
            st.rerun()

model = genai.GenerativeModel(model_choice)

# --- 5. SCENARIO DATA (Specific & Narrative) ---
SCENARIOS = {
    "Admission": {
        "title": "Initial Admission",
        "difficulty": "Beginner",
        "role": "Herr Müller",
        "desc": "Herr Müller is clutching his chest bag tightly and refuses to sit on the bed. He looks terrified.",
        "task": "Calm him down and convince him to sit.",
        "avatar": "👴",
        "icon": "📋"
    },
    "Medication": {
        "title": "Medication Dispute",
        "difficulty": "Intermediate",
        "role": "Frau Schneider",
        "desc": "Frau Schneider has thrown her pills on the floor. She says: 'These blue ones kill my stomach!'",
        "task": "Address her side-effect concerns empathetically.",
        "avatar": "👵",
        "icon": "💊"
    },
    "Emergency": {
        "title": "Code Blue Triage",
        "difficulty": "Advanced",
        "role": "Panicked Relative",
        "desc": "A visitor screams: 'He collapsed in the hallway!' They are hyperventilating.",
        "task": "Get the location and symptoms immediately.",
        "avatar": "🏃",
        "icon": "🚨"
    }
}

# --- 6. STATE ---
if "messages" not in st.session_state: st.session_state.messages = []
if "scenario" not in st.session_state: st.session_state.scenario = None
if "feedback" not in st.session_state: st.session_state.feedback = None
if "last_audio_id" not in st.session_state: st.session_state.last_audio_id = None
if "turn_count" not in st.session_state: st.session_state.turn_count = 0
MAX_TURNS = 5

# --- 7. LOGIC ---
def process_audio(audio_bytes, scenario_key, history):
    try:
        prompt = "Transcribe this German audio exactly. Output ONLY the German text."
        resp = model.generate_content([prompt, {"mime_type": "audio/mp3", "data": audio_bytes}])
        text = resp.text.strip()
        
        history_txt = "\n".join([f"{m['role']}: {m['content']}" for m in history])
        scen = SCENARIOS[scenario_key]
        
        analysis_prompt = f"""
        Context: Roleplay {scen['role']}. Situation: {scen['desc']}
        History: {history_txt}
        User said: "{text}"
        
        Task:
        1. Reply as patient.
        2. Grade user (grammar/politeness/medical).
        Output JSON: "response_text", "feedback" (grammar, politeness, medical, critique, better_phrase)
        """
        res = model.generate_content(analysis_prompt, generation_config={"response_mime_type": "application/json"})
        return text, json.loads(res.text)
    except:
        return None, None

def text_to_speech(text):
    try:
        tts = gTTS(text=text, lang='de')
        buf = io.BytesIO()
        tts.write_to_fp(buf)
        buf.seek(0)
        return buf
    except:
        return None

# --- 8. UI FLOW ---

# === SCREEN 1: CENTERED CARDS ===
if not st.session_state.scenario:
    st.subheader("Select a Scenario")
    
    # Grid Layout
    cols = st.columns(3)
    keys = list(SCENARIOS.keys())
    
    for i, col in enumerate(cols):
        key = keys[i]
        data = SCENARIOS[key]
        with col:
            # The Card Visual
            st.markdown(f"""
            <div class="scenario-card">
                <div>
                    <div class="scenario-icon">{data['icon']}</div>
                    <div class="scenario-title">{data['title']}</div>
                    <hr style="margin: 10px 0; border: 0; border-top: 1px solid #eee;">
                    <div class="scenario-desc">{data['desc']}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # The Button (Centered below the visual via CSS)
            if st.button(f"Select {key}", key=f"btn_{key}"):
                st.session_state.scenario = key
                st.session_state.turn_count = 0
                st.rerun()

# === SCREEN 2: ACTIVE SIMULATION ===
else:
    curr = SCENARIOS[st.session_state.scenario]
    
    # Header
    c1, c2 = st.columns([1, 5])
    with c1:
        if st.button("← Back"):
            st.session_state.clear()
            st.rerun()
    with c2:
        st.progress(st.session_state.turn_count / MAX_TURNS, text=f"Turn {st.session_state.turn_count}/{MAX_TURNS}")

    # Context Header
    if not st.session_state.messages:
        st.info(f"**SITUATION:** {curr['desc']} | **GOAL:** {curr['task']}")

    # Chat
    for msg in st.session_state.messages:
        role = "assistant" if msg["role"] == "assistant" else "user"
        avatar = curr['avatar'] if role == "assistant" else "🧑‍⚕️"
        with st.chat_message(role, avatar=avatar):
            st.write(msg["content"])

    # Feedback Zone
    if st.session_state.feedback:
        f = st.session_state.feedback
        with st.expander("📝 Instructor Feedback", expanded=True):
            cols = st.columns(3)
            cols[0].metric("Grammar", f"{f.get('grammar')}/10")
            cols[1].metric("Politeness", f"{f.get('politeness')}/10")
            cols[2].metric("Medical", f"{f.get('medical')}/10")
            st.warning(f"💡 {f.get('critique')}")
            st.success(f"🗣️ Better: \"{f.get('better_phrase')}\"")
            if st.button("↺ Retry Turn"):
                st.session_state.messages.pop()
                st.session_state.messages.pop()
                st.session_state.feedback = None
                st.session_state.turn_count -= 1
                st.rerun()

    # --- THE ALERT RECORDER ZONE ---
    if st.session_state.turn_count < MAX_TURNS:
        st.markdown(f"""
        <div class="action-zone">
            <div class="action-header">⚠️ Action Required</div>
            <div class="finger-point">👇</div>
            <div style="font-weight:600; margin-bottom:10px;">Tap below to respond to {curr['role']}</div>
        </div>
        """, unsafe_allow_html=True)
        
        # Audio Input
        audio_val = st.audio_input("Record", label_visibility="collapsed")
        
        if audio_val:
            if st.session_state.last_audio_id != audio_val.file_id:
                st.session_state.last_audio_id = audio_val.file_id
                
                with st.spinner("Processing..."):
                    user_text, ai_data = process_audio(audio_val.read(), st.session_state.scenario, st.session_state.messages)
                    
                    if user_text and ai_data:
                        st.session_state.turn_count += 1
                        st.session_state.messages.append({"role": "user", "content": user_text})
                        st.session_state.feedback = ai_data["feedback"]
                        st.session_state.messages.append({"role": "assistant", "content": ai_data["response_text"]})
                        
                        mp3 = text_to_speech(ai_data["response_text"])
                        if mp3: st.audio(mp3, format="audio/mp3", autoplay=True)
                        time.sleep(0.5)
                        st.rerun()
    else:
        st.success("✅ Simulation Complete!")
        if st.button("Start New"):
            st.session_state.clear()
            st.rerun()
