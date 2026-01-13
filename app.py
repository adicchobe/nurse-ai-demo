import streamlit as st
import google.generativeai as genai
from gtts import gTTS
import os
import json
import io
import time

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="CareLingo", page_icon="🩺", layout="centered")

# --- 2. PROFESSIONAL STYLING ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    
    .stButton button {
        width: 100%;
        border-radius: 12px;
        border: 1px solid rgba(128, 128, 128, 0.2);
        transition: all 0.2s ease;
    }
    .stButton button:hover {
        border-color: #FF4B4B;
        color: #FF4B4B;
        transform: translateY(-2px);
    }
    
    .scenario-desc {
        font-size: 0.85rem;
        opacity: 0.8;
        text-align: center;
        margin-bottom: 10px;
    }
    
    .limit-badge {
        font-size: 0.75rem;
        background-color: #f0f2f6;
        color: #555;
        padding: 2px 8px;
        border-radius: 10px;
        display: block;
        width: fit-content;
        margin: 0 auto 15px auto;
    }

    div[data-testid="InputInstructions"] > span { display: none; }
    
    .recorder-cue {
        color: #FF4B4B;
        font-weight: bold;
        text-align: center;
        font-size: 0.8rem;
        letter-spacing: 1px;
        animation: pulse 2s infinite;
        margin-bottom: 5px;
    }
    @keyframes pulse { 0% {opacity: 1;} 50% {opacity: 0.6;} 100% {opacity: 1;} }
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
        st.markdown("<br><h1 style='text-align: center;'>🔐 CareLingo Login</h1>", unsafe_allow_html=True)
        pwd = st.text_input("Password", type="password")
        if st.button("Start Shift"):
            if pwd == st.secrets["APP_PASSWORD"]:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Access Denied")
        st.stop()

# --- 4. SETTINGS ---
st.title("🩺 CareLingo")

with st.expander("⚙️ System Settings", expanded=False):
    c1, c2 = st.columns([3, 1])
    with c1:
        model_choice = st.selectbox("Active AI Brain:", [
            "gemini-2.5-flash-native-audio-dialog",
            "gemini-2.5-flash",
            "gemini-2.0-flash-exp",
            "gemini-1.5-flash"
        ])
    with c2:
        st.write("")
        if st.button("🗑️ Reset All"):
            st.session_state.messages = []
            st.session_state.feedback = None
            st.session_state.turn_count = 0
            st.rerun()

model = genai.GenerativeModel(model_choice)

# --- 5. STATE ---
if "messages" not in st.session_state: st.session_state.messages = []
if "scenario" not in st.session_state: st.session_state.scenario = None
if "feedback" not in st.session_state: st.session_state.feedback = None
if "last_audio_id" not in st.session_state: st.session_state.last_audio_id = None
if "turn_count" not in st.session_state: st.session_state.turn_count = 0

MAX_TURNS = 5

# --- 6. SCENARIO DATA ---
SCENARIOS = {
    "Admission": {
        "icon": "📋", "title": "Admission", "role": "Herr Müller", "avatar": "👴",
        "desc": "Anxious new patient. Collect history.",
        "goal": "Collect history & build trust."
    },
    "Medication": {
        "icon": "💊", "title": "Medication", "role": "Frau Schneider", "avatar": "👵",
        "desc": "Refuses heart meds. Explain necessity.",
        "goal": "Negotiate medication intake."
    },
    "Emergency": {
        "icon": "🚨", "title": "Emergency", "role": "Panicked Visitor", "avatar": "🏃",
        "desc": "Husband collapsed. Get vitals NOW.",
        "goal": "Get vitals (Symptoms, Age) fast."
    }
}

# --- 7. LOGIC (NOW WITH MEMORY) ---
def process_audio(audio_bytes, scenario_key, history_messages):
    try:
        # 1. Transcribe Audio
        prompt = "Transcribe this German audio exactly. Output ONLY the German text."
        resp = model.generate_content([prompt, {"mime_type": "audio/mp3", "data": audio_bytes}])
        text = resp.text.strip()
        
        # 2. Build Context String from History
        # We format previous messages so the AI remembers the conversation
        context_str = ""
        for msg in history_messages:
            role_label = "Nurse (User)" if msg["role"] == "user" else "Patient"
            context_str += f"{role_label}: {msg['content']}\n"
        
        # 3. Analysis with Context
        scen = SCENARIOS[scenario_key]
        analysis_prompt = f"""
        You are a German Nurse Tutor Simulation.
        
        SCENARIO CONTEXT:
        - Role: {scen['role']} (Patient)
        - Student Goal: {scen['goal']}
        
        CONVERSATION HISTORY SO FAR:
        {context_str}
        
        CURRENT INPUT FROM NURSE (USER):
        "{text}"
        
        TASK:
        1. Reply naturally as the Patient to the Nurse's current input. Remember the history.
        2. Grade the Nurse's specific German grammar/politeness in this turn.
        
        OUTPUT JSON: {{
            "response_text": "German reply as patient",
            "feedback": {{
                "grammar": (1-10), "politeness": (1-10), "medical": (1-10),
                "critique": "Tip in English", "better_phrase": "Correction"
            }}
        }}
        """
        res = model.generate_content(analysis_prompt, generation_config={"response_mime_type": "application/json"})
        data = json.loads(res.text)
        return text, data
    except Exception as e:
        return None, str(e)

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

# === SCREEN 1: SELECTION ===
if not st.session_state.scenario:
    st.markdown("### 👋 Select Shift Task")
    st.info("Choose a scenario. All tasks are timed for 5 exchanges.")
    
    c1, c2, c3 = st.columns(3)
    
    with c1:
        if st.button(f"{SCENARIOS['Admission']['icon']} Admission"):
            st.session_state.scenario = "Admission"
            st.session_state.turn_count = 0
            st.rerun()
        st.markdown(f"<div class='scenario-desc'>{SCENARIOS['Admission']['desc']}</div>", unsafe_allow_html=True)
        st.markdown("<span class='limit-badge'>⏱️ 5 Turns</span>", unsafe_allow_html=True)

    with c2:
        if st.button(f"{SCENARIOS['Medication']['icon']} Medication"):
            st.session_state.scenario = "Medication"
            st.session_state.turn_count = 0
            st.rerun()
        st.markdown(f"<div class='scenario-desc'>{SCENARIOS['Medication']['desc']}</div>", unsafe_allow_html=True)
        st.markdown("<span class='limit-badge'>⏱️ 5 Turns</span>", unsafe_allow_html=True)

    with c3:
        if st.button(f"{SCENARIOS['Emergency']['icon']} Emergency"):
            st.session_state.scenario = "Emergency"
            st.session_state.turn_count = 0
            st.rerun()
        st.markdown(f"<div class='scenario-desc'>{SCENARIOS['Emergency']['desc']}</div>", unsafe_allow_html=True)
        st.markdown("<span class='limit-badge'>⏱️ 5 Turns</span>", unsafe_allow_html=True)

# === SCREEN 2: PRACTICE ===
else:
    curr = SCENARIOS[st.session_state.scenario]
    
    # Header
    c1, c2 = st.columns([1, 4])
    with c1:
        if st.button("← Exit"):
            st.session_state.scenario = None
            st.session_state.messages = []
            st.session_state.feedback = None
            st.rerun()
    with c2:
        turns_left = MAX_TURNS - st.session_state.turn_count
        color = "red" if turns_left <= 1 else "#555"
        st.markdown(f"**{curr['title']}** | <span style='color:{color}'>Turn {st.session_state.turn_count}/{MAX_TURNS}</span>", unsafe_allow_html=True)
    
    st.divider()

    # Intro
    if not st.session_state.messages:
        st.markdown(f"""
        <div style='text-align:center; padding:15px; border:1px dashed #ddd; border-radius:10px; margin-bottom:15px;'>
            <h3>{curr['avatar']} Speaking to: {curr['role']}</h3>
            <p><strong>Goal:</strong> {curr['goal']}</p>
            <p style='font-size:0.9rem; color:#666;'>Tap microphone to start.</p>
        </div>
        """, unsafe_allow_html=True)

    # Chat History
    for msg in st.session_state.messages:
        if msg["role"] == "user":
            with st.chat_message("user", avatar="🧑‍⚕️"):
                st.write("**You (Nurse):**")
                st.write(msg["content"])
        else:
            with st.chat_message("assistant", avatar=curr['avatar']):
                st.write(f"**{curr['role']}:**")
                st.write(msg["content"])

    # Feedback
    if st.session_state.feedback:
        f = st.session_state.feedback
        with st.container():
            st.markdown("---")
            st.markdown("##### 📝 Teacher's Notes")
            with st.expander("View Analysis", expanded=True):
                c1, c2, c3 = st.columns(3)
                c1.metric("Grammar", f"{f.get('grammar',0)}/10")
                c2.metric("Politeness", f"{f.get('politeness',0)}/10")
                c3.metric("Medical", f"{f.get('medical',0)}/10")
                st.info(f"💡 {f.get('critique', '')}")
                st.success(f"✅ Better: \"{f.get('better_phrase', '')}\"")
                
                if st.button("↩️ Retry Turn"):
                    if len(st.session_state.messages) >= 2:
                        st.session_state.messages.pop()
                        st.session_state.messages.pop()
                        st.session_state.feedback = None
                        st.session_state.turn_count -= 1
                        st.rerun()

    # Input
    st.markdown("###")
    if st.session_state.turn_count < MAX_TURNS:
        st.markdown("<div class='recorder-cue'>👇 TAP TO SPEAK</div>", unsafe_allow_html=True)
        audio_val = st.audio_input("Record", label_visibility="collapsed")

        if audio_val:
            if st.session_state.last_audio_id != audio_val.file_id:
                st.session_state.last_audio_id = audio_val.file_id
                
                with st.status("🔄 Processing...", expanded=True) as status:
                    # Pass HISTORY to the processor
                    user_text, ai_data = process_audio(
                        audio_val.read(), 
                        st.session_state.scenario, 
                        st.session_state.messages # <--- MEMORY PASSED HERE
                    )
                    
                    if user_text and isinstance(ai_data, dict):
                        status.update(label="Done!", state="complete", expanded=False)
                        st.session_state.turn_count += 1
                        st.session_state.messages.append({"role": "user", "content": user_text})
                        st.session_state.feedback = ai_data["feedback"]
                        st.session_state.messages.append({"role": "assistant", "content": ai_data["response_text"]})
                        
                        mp3 = text_to_speech(ai_data["response_text"])
                        if mp3: st.audio(mp3, format="audio/mp3", autoplay=True)
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        status.update(label="Error", state="error")
                        st.error(f"Error: {ai_data}")
    else:
        st.warning("🛑 Shift limit reached.")
        if st.button("Start New Shift"):
            st.session_state.turn_count = 0
            st.session_state.messages = []
            st.session_state.feedback = None
            st.rerun()
