import streamlit as st
import google.generativeai as genai
from gtts import gTTS
import os
import json
import io
import time

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="CareLingo", page_icon="🩺", layout="centered")

# --- 2. THEME-AWARE CSS (The Fix) ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

    /* --- SCENARIO CARDS (Theme Adaptive) --- */
    .scenario-card {
        background-color: #ffffff; /* Default Light */
        border: 1px solid #e5e7eb;
        border-radius: 12px;
        padding: 20px;
        text-align: center;
        height: 280px; /* FIXED HEIGHT for alignment */
        display: flex;
        flex-direction: column;
        justify-content: flex-start;
        align-items: center;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        margin-bottom: 10px;
        transition: transform 0.2s;
    }
    
    .scenario-icon { font-size: 3rem; margin-bottom: 10px; }
    .scenario-title { font-weight: 700; font-size: 1.1rem; margin-bottom: 10px; color: #111827; }
    .scenario-desc { font-size: 0.9rem; color: #4b5563; line-height: 1.4; }

    /* --- DARK MODE OVERRIDES --- */
    @media (prefers-color-scheme: dark) {
        .scenario-card {
            background-color: #262730;
            border-color: #41444e;
            box-shadow: none;
        }
        .scenario-title { color: #f9fafb; }
        .scenario-desc { color: #d1d5db; }
    }

    /* --- BUTTONS (Centered & Full Width) --- */
    div.stButton > button {
        width: 100%;
        border-radius: 8px;
        font-weight: 600;
        border: 1px solid rgba(128, 128, 128, 0.2);
        padding: 0.5rem 1rem;
        margin-top: 0px; /* Remove default margin */
    }
    div.stButton > button:hover {
        border-color: #FF4B4B;
        color: #FF4B4B;
        transform: translateY(-2px);
    }

    /* --- ACTION ZONE (The Recorder Alert) --- */
    .action-zone {
        background-color: rgba(255, 75, 75, 0.05); /* Light red tint */
        border: 2px dashed #FF4B4B;
        border-radius: 12px;
        padding: 20px;
        text-align: center;
        margin-top: 25px;
    }
    .action-text {
        font-weight: 700;
        color: #FF4B4B;
        text-transform: uppercase;
        letter-spacing: 1px;
        font-size: 0.9rem;
        margin-bottom: 10px;
        display: block;
    }
    
    /* Animation */
    .finger-anim { font-size: 2rem; display: block; margin: 0 auto; animation: bounce 1.5s infinite; }
    @keyframes bounce { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-10px); } }

    /* UTILS */
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
            if st.form_submit_button("Start Practice! 🚀"):
                if pwd == st.secrets["APP_PASSWORD"]:
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("⚠️ Invalid Code")
        st.stop()

# --- 4. SETTINGS ---
st.title("🩺 CareLingo")

with st.expander("⚙️ Settings", expanded=False):
    c1, c2 = st.columns([3, 1])
    with c1:
        # Green Bar models from your screenshot
        model_choice = st.selectbox("AI Model:", [
            "gemini-2.5-flash-lite", 
            "gemini-3-flash", 
            "gemini-2.0-flash-exp", 
            "gemini-1.5-flash"
        ])
    with c2:
        st.write("") 
        if st.button("↻ Reset"):
            st.session_state.clear()
            st.rerun()

model = genai.GenerativeModel(model_choice)

# --- 5. SCENARIO DATA ---
SCENARIOS = {
    "Admission": {
        "title": "Initial Admission",
        "role": "Herr Müller",
        "desc": "Herr Müller (72) is clutching his chest bag tightly. He refuses to sit on the bed and looks terrified of the equipment.",
        "task": "Calm him down and convince him to sit.",
        "avatar": "👴", "icon": "📋"
    },
    "Medication": {
        "title": "Medication Dispute",
        "role": "Frau Schneider",
        "desc": "Frau Schneider has pushed her pill cup away. She insists: 'The blue pill gives me terrible headaches!'",
        "task": "Address side-effects empathetically.",
        "avatar": "👵", "icon": "💊"
    },
    "Emergency": {
        "title": "Code Blue Triage",
        "role": "Panicked Relative",
        "desc": "A visitor screams: 'My husband collapsed in the hallway!' They are hyperventilating.",
        "task": "Get location and symptoms immediately.",
        "avatar": "🏃", "icon": "🚨"
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

# === SCREEN 1: SELECTION (Fixed Alignment) ===
if not st.session_state.scenario:
    st.subheader("Select a Scenario")
    st.info("Each scenario is a 5-turn micro-simulation.")
    
    cols = st.columns(3)
    keys = list(SCENARIOS.keys())
    
    for i, col in enumerate(cols):
        key = keys[i]
        data = SCENARIOS[key]
        with col:
            # 1. The Visual Card
            st.markdown(f"""
            <div class="scenario-card">
                <div class="scenario-icon">{data['icon']}</div>
                <div class="scenario-title">{data['title']}</div>
                <div class="scenario-desc">{data['desc']}</div>
            </div>
            """, unsafe_allow_html=True)
            
            # 2. The Button (Centered & Full Width under card)
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

    # Context
    if not st.session_state.messages:
        st.info(f"**GOAL:** {curr['task']}")

    # Chat
    for msg in st.session_state.messages:
        role = "assistant" if msg["role"] == "assistant" else "user"
        avatar = curr['avatar'] if role == "assistant" else "🧑‍⚕️"
        with st.chat_message(role, avatar=avatar):
            st.write(msg["content"])

    # Feedback
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

    # --- ACTION ZONE (Fixed Dark Mode Visibility) ---
    if st.session_state.turn_count < MAX_TURNS:
        st.markdown(f"""
        <div class="action-zone">
            <span class="action-text">⚠️ Mandatory Action</span>
            <div class="finger-anim">👇</div>
            <div style="font-weight:600; margin-bottom:10px; color: #FF4B4B;">Tap below to respond to {curr['role']}</div>
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
