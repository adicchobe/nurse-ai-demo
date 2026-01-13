import streamlit as st
import google.generativeai as genai
from gtts import gTTS
import os
import json
import io
import time
import re

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="CareLingo", page_icon="🩺", layout="centered")

# --- 2. FINAL POLISH CSS (Theme-Aware & Aligned) ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

    /* Make buttons full width and interactive */
    div.stButton > button {
        width: 100%;
        border-radius: 8px;
        font-weight: 600;
        transition: all 0.2s;
    }
    
    /* Helper to ensure descriptions take up same space */
    .scenario-desc-box {
        min-height: 80px; 
        font-size: 0.9rem;
        opacity: 0.8;
        line-height: 1.5;
    }

    /* Hide default input instructions */
    div[data-testid="InputInstructions"] > span { display: none; }
    
    /* The Recorder Instruction Text */
    .recorder-label {
        font-weight: 600;
        color: #FF4B4B; 
        margin-bottom: 5px;
        display: flex;
        align-items: center;
        gap: 8px;
    }
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
        "role": "Herr Müller (72)",
        "desc": "Herr Müller is clutching his chest bag tightly. He looks terrified of the hospital equipment and refuses to sit down.",
        "task": "Calm him down, build rapport, and convince him to sit on the bed so you can check him.",
        "avatar": "👴", "icon": "📋"
    },
    "Medication": {
        "title": "Medication Dispute",
        "role": "Frau Schneider (65)",
        "desc": "Frau Schneider has pushed her pill cup away aggressively. She insists: 'The blue pill gives me terrible headaches! I won't take it.'",
        "task": "Acknowledge her side-effects, show empathy, but explain why the heart medication is non-negotiable today.",
        "avatar": "👵", "icon": "💊"
    },
    "Emergency": {
        "title": "Code Blue Triage",
        "role": "Panicked Relative",
        "desc": "A visitor runs to the nurses' station screaming/hyperventilating: 'My husband collapsed in the hallway! Help!'",
        "task": "Take control immediately. Get the exact location and patient status (breathing/conscious) in under 3 questions.",
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

# --- 7. LOGIC (WITH AUDIO FIX) ---
def clean_text_for_speech(text):
    # Fix 1: Remove markdown stars/bold
    text = text.replace("*", "").replace("#", "").replace("_", "")
    # Fix 2: Remove role labels like "Patient:"
    text = re.sub(r'^.*?:', '', text)
    # Fix 3: Remove brackets [coughs] which choke the audio player
    text = re.sub(r'\[.*?\]', '', text)
    text = re.sub(r'\(.*?\)', '', text)
    return text.strip()

def process_audio(audio_bytes, scenario_key, history):
    try:
        # 1. Transcribe
        prompt = "Transcribe this German audio exactly. Output ONLY the German text."
        resp = model.generate_content([prompt, {"mime_type": "audio/mp3", "data": audio_bytes}])
        text = resp.text.strip()
        
        history_txt = "\n".join([f"{m['role']}: {m['content']}" for m in history])
        scen = SCENARIOS[scenario_key]
        
        # 2. Analyze (Strict Constraint Added)
        analysis_prompt = f"""
        You are a German Medical Roleplay Simulation.
        
        SCENARIO:
        - Role: {scen['role']} (Patient)
        - Context: {scen['desc']}
        
        HISTORY:
        {history_txt}
        
        CURRENT USER AUDIO: "{text}"
        
        INSTRUCTIONS:
        1. Reply naturally as the Patient. **CRITICAL: KEEP REPLY UNDER 20 WORDS.** (Short responses prevent audio errors).
        2. Grade ONLY THE USER (The Nurse). Scores must be INTEGERS (1-10).
        
        OUTPUT JSON:
        {{
            "response_text": "German reply (Max 20 words)",
            "feedback": {{
                "grammar": (Integer 1-10), 
                "politeness": (Integer 1-10), 
                "medical": (Integer 1-10), 
                "critique": "Advice in English", 
                "better_phrase": "Correction in German"
            }}
        }}
        """
        res = model.generate_content(analysis_prompt, generation_config={"response_mime_type": "application/json"})
        return text, json.loads(res.text)
    except Exception as e:
        return None, None

def text_to_speech(text):
    try:
        # Fix 4: Clean text before generating audio
        clean_text = clean_text_for_speech(text)
        tts = gTTS(text=clean_text, lang='de', slow=False)
        buf = io.BytesIO()
        tts.write_to_fp(buf)
        buf.seek(0)
        return buf
    except:
        return None

# --- 8. UI FLOW ---

# === SCREEN 1: SELECTION (Native Containers = Perfect Alignment) ===
if not st.session_state.scenario:
    st.subheader("Select a Practice Scenario")
    st.info("Each scenario is a 5-turn micro-simulation.")
    
    cols = st.columns(3)
    keys = list(SCENARIOS.keys())
    
    for i, col in enumerate(cols):
        key = keys[i]
        data = SCENARIOS[key]
        with col:
            # Native Streamlit Container with Border -> Handles alignment automatically
            with st.container(border=True):
                st.markdown(f"<div style='font-size: 3rem; text-align: center;'>{data['icon']}</div>", unsafe_allow_html=True)
                st.markdown(f"<h4 style='text-align: center; margin:0;'>{data['title']}</h4>", unsafe_allow_html=True)
                # Fixed height box for description to ensure buttons align
                st.markdown(f"<div class='scenario-desc-box'>{data['desc']}</div>", unsafe_allow_html=True)
                
                # The button is naturally full width inside the container
                if st.button(f"Start {key}", key=f"btn_{key}"):
                    st.session_state.scenario = key
                    st.session_state.turn_count = 0
                    st.rerun()

# === SCREEN 2: ACTIVE SIMULATION ===
else:
    curr = SCENARIOS[st.session_state.scenario]
    
    # 1. Header Navigation
    c1, c2 = st.columns([1, 5])
    with c1:
        if st.button("← Back"):
            st.session_state.clear()
            st.rerun()
    with c2:
        st.progress(st.session_state.turn_count / MAX_TURNS, text=f"Interaction Progress: {st.session_state.turn_count}/{MAX_TURNS}")

    # 2. Context Header
    if not st.session_state.messages:
        with st.container(border=True):
            st.markdown(f"**GOAL:** {curr['task']}")

    # 3. Chat Zone
    for msg in st.session_state.messages:
        role = "assistant" if msg["role"] == "assistant" else "user"
        avatar = curr['avatar'] if role == "assistant" else "🧑‍⚕️"
        with st.chat_message(role, avatar=avatar):
            st.write(msg["content"])

    # 4. Feedback Zone
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

    # 5. SIMPLE RECORDER ZONE
    if st.session_state.turn_count < MAX_TURNS:
        st.markdown("---")
        # Your specific requested text
        st.markdown('<div class="recorder-label">Click on the 🎙️ icon below to converse and get feedback</div>', unsafe_allow_html=True)
        
        # Audio Input
        audio_val = st.audio_input("Record", label_visibility="collapsed")
        
        if audio_val:
            if st.session_state.last_audio_id != audio_val.file_id:
                st.session_state.last_audio_id = audio_val.file_id
                
                with st.spinner("🧠 Analyzing speech..."):
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
