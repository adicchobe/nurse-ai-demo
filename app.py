import streamlit as st
import google.generativeai as genai
from gtts import gTTS
import os
import json
import io
import time

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="CareLingo", page_icon="🩺", layout="centered")

# --- 2. ADVANCED UX & ANIMATION CSS ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&family=Caveat:wght@600&display=swap');
    
    /* 1. Global Reset & Fonts */
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    
    /* 2. Button Micro-Interactions (Hover States) */
    .stButton button {
        width: 100%;
        border-radius: 12px;
        border: 1px solid rgba(0,0,0,0.08);
        background: linear-gradient(145deg, #ffffff, #f0f0f0);
        box-shadow: 2px 2px 5px rgba(0,0,0,0.05);
        transition: all 0.2s cubic-bezier(0.175, 0.885, 0.32, 1.275); /* Bouncy feel */
        color: #333;
        font-weight: 600;
    }
    .stButton button:hover {
        transform: translateY(-3px) scale(1.01);
        box-shadow: 0 10px 20px rgba(0,0,0,0.1);
        border-color: #FF4B4B;
        color: #FF4B4B;
        background: white;
    }
    .stButton button:active {
        transform: translateY(-1px);
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
    }

    /* 3. Scenario Cards (Selection Screen) */
    .scenario-card {
        background: white;
        border-radius: 16px;
        padding: 20px;
        border: 1px solid #eee;
        text-align: center;
        transition: transform 0.3s ease;
        height: 100%;
    }
    .scenario-title { font-weight: 700; font-size: 1.1rem; color: #1f2937; margin: 10px 0; }
    .scenario-text { font-size: 0.9rem; color: #6b7280; line-height: 1.4; margin-bottom: 15px; }
    .badge {
        background-color: #e0f2fe; color: #0284c7;
        padding: 4px 8px; border-radius: 6px; font-size: 0.75rem; font-weight: 600;
        display: inline-block; margin-bottom: 10px;
    }

    /* 4. COMPARTMENTALIZATION: Teacher Zone (The "Clipboard" Look) */
    .teacher-clipboard {
        background-color: #fffbeb; /* Light Yellow Paper */
        border: 1px solid #fcd34d;
        border-radius: 12px;
        padding: 20px;
        margin-top: 20px;
        box-shadow: 4px 4px 0px rgba(0,0,0,0.05);
        position: relative;
        animation: slideUp 0.5s ease-out;
    }
    .teacher-clipboard::before {
        content: "📝 INSTRUCTOR NOTES";
        position: absolute;
        top: -12px;
        left: 20px;
        background: #f59e0b;
        color: white;
        padding: 2px 10px;
        border-radius: 4px;
        font-size: 0.7rem;
        font-weight: bold;
    }
    
    /* 5. Recording State Visuals */
    .rec-container {
        border: 2px dashed #e5e7eb;
        border-radius: 12px;
        padding: 15px;
        text-align: center;
        background: #f9fafb;
        margin-top: 20px;
        position: relative;
    }
    .rec-live-dot {
        height: 12px; width: 12px;
        background-color: #ef4444;
        border-radius: 50%;
        display: inline-block;
        margin-right: 8px;
        animation: blink 1.5s infinite;
    }
    
    /* Animations */
    @keyframes slideUp { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }
    @keyframes blink { 0% { opacity: 1; } 50% { opacity: 0.4; } 100% { opacity: 1; } }

    /* Hide standard elements */
    div[data-testid="InputInstructions"] > span { display: none; }
</style>
""", unsafe_allow_html=True)

# --- 3. AUTHENTICATION (Form-Based) ---
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

# --- 4. SETTINGS & MODEL ---
st.title("🩺 CareLingo")

# Collapsed settings to reduce noise
with st.expander("⚙️ Simulation Settings", expanded=False):
    c1, c2 = st.columns([3, 1])
    with c1:
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

# --- 5. SCENARIO DATA (Detailed) ---
SCENARIOS = {
    "Admission": {
        "title": "Initial Admission",
        "difficulty": "Beginner",
        "role": "Herr Müller (72, Anxious)",
        "context": "Herr Müller has just arrived in the ward. He is clutching his bag tightly and looking around nervously. He refuses to sit on the bed.",
        "task": "Build rapport, convince him to sit down, and ask for his full name and date of birth.",
        "avatar": "👴",
        "icon": "📋"
    },
    "Medication": {
        "title": "Medication Dispute",
        "difficulty": "Intermediate",
        "role": "Frau Schneider (Stubborn)",
        "context": "Frau Schneider has pushed her pill cup away. She claims the 'blue pill' gives her headaches and she won't take it today.",
        "task": "Empathize with her side effects, but explain the critical importance of the heart medication without being aggressive.",
        "avatar": "👵",
        "icon": "💊"
    },
    "Emergency": {
        "title": "Code Blue Triage",
        "difficulty": "Advanced",
        "role": "Panicked Relative",
        "context": "A visitor runs to the nurses' station screaming. Their partner has collapsed in the hallway and is not moving.",
        "task": "Take immediate control. Get the exact location, check for breathing info, and dispatch the team. Be concise.",
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
        # 1. Transcribe
        prompt = "Transcribe this German audio exactly. Output ONLY the German text."
        resp = model.generate_content([prompt, {"mime_type": "audio/mp3", "data": audio_bytes}])
        text = resp.text.strip()
        
        # 2. History Context
        history_txt = "\n".join([f"{m['role']}: {m['content']}" for m in history])
        
        # 3. Analyze
        scen = SCENARIOS[scenario_key]
        analysis_prompt = f"""
        Simulation Context:
        Role: {scen['role']}
        Situation: {scen['context']}
        Student Task: {scen['task']}
        
        History:
        {history_txt}
        
        Current User Input: "{text}"
        
        Output JSON:
        1. "response_text": Reply as the patient.
        2. "feedback": Grade the user (grammar/politeness/medical) and give a tip.
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

# === SCREEN 1: DETAILED SELECTION ===
if not st.session_state.scenario:
    st.subheader("Select Simulation Scenario")
    st.info("Each scenario is a 5-turn micro-simulation designed to test specific skills.")
    
    cols = st.columns(3)
    keys = list(SCENARIOS.keys())
    
    for i, col in enumerate(cols):
        key = keys[i]
        data = SCENARIOS[key]
        with col:
            # HTML Card for Visuals
            st.markdown(f"""
            <div class="scenario-card">
                <div style="font-size:2.5rem; margin-bottom:10px;">{data['icon']}</div>
                <div class="badge">{data['difficulty']}</div>
                <div class="scenario-title">{data['title']}</div>
                <div class="scenario-text">{data['task'][:80]}...</div>
            </div>
            """, unsafe_allow_html=True)
            
            # The actual button handles the logic
            if st.button(f"Start {key}", key=f"btn_{key}"):
                st.session_state.scenario = key
                st.session_state.turn_count = 0
                st.rerun()

# === SCREEN 2: ACTIVE SIMULATION ===
else:
    curr = SCENARIOS[st.session_state.scenario]
    
    # 1. Header Bar
    c1, c2 = st.columns([1, 5])
    with c1:
        if st.button("← Exit"):
            st.session_state.clear()
            st.rerun()
    with c2:
        # Progress Bar Visual
        progress = st.session_state.turn_count / MAX_TURNS
        st.progress(progress, text=f"Interaction Progress: {st.session_state.turn_count}/{MAX_TURNS}")

    # 2. Context Card (Always visible at top)
    if not st.session_state.messages:
        st.markdown(f"""
        <div style="background:#f8fafc; padding:20px; border-radius:12px; border-left: 5px solid #3b82f6; margin-bottom:20px;">
            <h4>{curr['avatar']} Patient: {curr['role']}</h4>
            <p><strong>Situation:</strong> {curr['context']}</p>
            <p><strong>Your Mission:</strong> {curr['task']}</p>
        </div>
        """, unsafe_allow_html=True)

    # 3. Chat Zone (The Patient)
    for msg in st.session_state.messages:
        role = "assistant" if msg["role"] == "assistant" else "user"
        avatar = curr['avatar'] if role == "assistant" else "🧑‍⚕️"
        with st.chat_message(role, avatar=avatar):
            st.write(msg["content"])

    # 4. Teacher Zone (Compartmentalized)
    if st.session_state.feedback:
        f = st.session_state.feedback
        st.markdown(f"""
        <div class="teacher-clipboard">
            <div style="display:flex; justify-content:space-between; margin-bottom:10px;">
                <div>🔤 Grammar: <b>{f.get('grammar')}/10</b></div>
                <div>🤝 Politeness: <b>{f.get('politeness')}/10</b></div>
                <div>🩺 Medical: <b>{f.get('medical')}/10</b></div>
            </div>
            <div style="background:rgba(255,255,255,0.5); padding:10px; border-radius:8px;">
                <i>"{f.get('critique')}"</i>
            </div>
            <div style="margin-top:10px; color:#059669; font-weight:bold;">
                Try saying: "{f.get('better_phrase')}"
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Retry Button inside the teacher zone logic
        col_r1, col_r2 = st.columns([3,1])
        with col_r2:
             if st.button("↺ Retry Turn"):
                st.session_state.messages.pop()
                st.session_state.messages.pop()
                st.session_state.feedback = None
                st.session_state.turn_count -= 1
                st.rerun()

    # 5. Input Zone (Styled Container)
    st.markdown("<div class='rec-container'>", unsafe_allow_html=True)
    
    if st.session_state.turn_count < MAX_TURNS:
        st.markdown('<div><span class="rec-live-dot"></span><b>TAP MICROPHONE TO RESPOND</b></div>', unsafe_allow_html=True)
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
        st.success("✅ Simulation Complete. Great work!")
        if st.button("Start New Scenario"):
            st.session_state.clear()
            st.rerun()
            
    st.markdown("</div>", unsafe_allow_html=True)
