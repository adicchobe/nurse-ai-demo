import streamlit as st
import google.generativeai as genai
from gtts import gTTS
import os
import json
import io
import time

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="CareLingo", page_icon="🩺", layout="centered")

# --- 2. CLEAN STYLING (Single Column Focus) ---
st.markdown("""
<style>
    /* Card Style */
    .scenario-card {
        border: 1px solid #e0e0e0;
        border-radius: 12px;
        padding: 1.5rem;
        text-align: center;
        margin-bottom: 1rem;
        background-color: #fafafa;
        transition: transform 0.2s;
    }
    .scenario-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    
    /* Hide Input Hints */
    div[data-testid="InputInstructions"] > span { display: none; }
    
    /* Full Width Styled Buttons */
    .stButton button { 
        width: 100%; 
        font-weight: 600; 
        border-radius: 10px;
        height: 3rem;
    }
    
    /* Feedback Box Styling */
    div[data-testid="stExpander"] {
        border: 1px solid #e0e0e0;
        border-radius: 10px;
        background-color: #f8f9fa;
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
        st.markdown("<h2 style='text-align: center;'>🔒 Login</h2>", unsafe_allow_html=True)
        pwd = st.text_input("Password", type="password")
        if st.button("Enter CareLingo"):
            if pwd == st.secrets["APP_PASSWORD"]:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Incorrect Password")
        st.stop()

# --- 4. TOP SETTINGS MENU (Replaces Sidebar) ---
st.title("🩺 CareLingo")

# Collapsible Settings Menu
with st.expander("⚙️ Model & Settings"):
    c1, c2 = st.columns([2, 1])
    with c1:
        model_choice = st.selectbox(
            "AI Model",
            [
                "gemini-2.5-flash-native-audio-dialog", # Best (if available)
                "gemini-2.5-flash",
                "gemini-2.0-flash-exp",
                "gemini-1.5-flash"
            ],
            label_visibility="collapsed"
        )
    with c2:
        if st.button("🗑️ Reset Chat"):
            st.session_state.messages = []
            st.session_state.feedback = None
            st.rerun()
    st.caption(f"Currently using: {model_choice}")

# Initialize Model
model = genai.GenerativeModel(model_choice)

# --- 5. SESSION STATE ---
if "messages" not in st.session_state: st.session_state.messages = []
if "scenario" not in st.session_state: st.session_state.scenario = None
if "feedback" not in st.session_state: st.session_state.feedback = None
if "last_audio_id" not in st.session_state: st.session_state.last_audio_id = None

# --- 6. SCENARIOS ---
SCENARIOS = {
    "Admission": {"icon": "📋", "title": "Admission", "role": "Herr Müller", "goal": "Collect medical history."},
    "Medication": {"icon": "💊", "title": "Medication", "role": "Frau Schneider", "goal": "Explain why meds are needed."},
    "Emergency": {"icon": "🚨", "title": "Emergency", "role": "Visitor", "goal": "Get vitals fast."}
}

# --- 7. LOGIC ---
def process_audio(audio_bytes, scenario_key):
    try:
        # 1. Transcribe
        prompt = "Transcribe this German audio exactly. Output ONLY the German text."
        resp = model.generate_content([prompt, {"mime_type": "audio/mp3", "data": audio_bytes}])
        text = resp.text.strip()
        
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
        res = model.generate_content(f"{analysis_prompt}\nUser: {text}", generation_config={"response_mime_type": "application/json"})
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

# Scenario Selection View
if not st.session_state.scenario:
    st.markdown("### Choose a Practice Scenario")
    st.markdown("---")
    
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f"<div class='scenario-card'><h1>{SCENARIOS['Admission']['icon']}</h1></div>", unsafe_allow_html=True)
        if st.button("Admission"):
            st.session_state.scenario = "Admission"
            st.rerun()
    with c2:
        st.markdown(f"<div class='scenario-card'><h1>{SCENARIOS['Medication']['icon']}</h1></div>", unsafe_allow_html=True)
        if st.button("Medication"):
            st.session_state.scenario = "Medication"
            st.rerun()
    with c3:
        st.markdown(f"<div class='scenario-card'><h1>{SCENARIOS['Emergency']['icon']}</h1></div>", unsafe_allow_html=True)
        if st.button("Emergency"):
            st.session_state.scenario = "Emergency"
            st.rerun()

# Active Chat View
else:
    curr = SCENARIOS[st.session_state.scenario]
    
    # Navigation Header
    c1, c2 = st.columns([1, 3])
    with c1:
        if st.button("← Back"):
            st.session_state.scenario = None
            st.session_state.messages = []
            st.session_state.feedback = None
            st.rerun()
    with c2:
        st.markdown(f"**{curr['title']}** | {curr['goal']}")
    
    st.divider()

    # Chat Area
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    # Feedback Area (With Contextual Retry)
    if st.session_state.feedback:
        f = st.session_state.feedback
        with st.expander("📊 Teacher's Feedback", expanded=True):
            # Metrics
            cols = st.columns(3)
            cols[0].metric("Grammar", f"{f.get('grammar',0)}/10")
            cols[1].metric("Politeness", f"{f.get('politeness',0)}/10")
            cols[2].metric("Medical", f"{f.get('medical',0)}/10")
            
            # Advice
            st.info(f"💡 {f.get('critique', '')}")
            st.success(f"🗣️ Better: \"{f.get('better_phrase', '')}\"")
            
            # Contextual Retry Button
            st.markdown("---")
            if st.button("↩️ Retry Last Turn"):
                if len(st.session_state.messages) >= 2:
                    st.session_state.messages.pop()
                    st.session_state.messages.pop()
                    st.session_state.feedback = None
                    st.rerun()

    # Audio Input (Bottom)
    st.markdown("###")
    audio_val = st.audio_input("Tap to Speak...")

    if audio_val:
        if st.session_state.last_audio_id != audio_val.file_id:
            st.session_state.last_audio_id = audio_val.file_id
            
            with st.status("🔄 Processing...", expanded=True) as status:
                st.write(f"Connecting to **{model_choice}**...")
                
                user_text, ai_data = process_audio(audio_val.read(), st.session_state.scenario)
                
                if user_text and isinstance(ai_data, dict):
                    status.update(label="Complete!", state="complete", expanded=False)
                    st.session_state.messages.append({"role": "user", "content": user_text})
                    st.session_state.feedback = ai_data["feedback"]
                    st.session_state.messages.append({"role": "assistant", "content": ai_data["response_text"]})
                    
                    mp3 = text_to_speech(ai_data["response_text"])
                    if mp3: st.audio(mp3, format="audio/mp3", autoplay=True)
                    time.sleep(1)
                    st.rerun()
                else:
                    status.update(label="Failed", state="error")
                    st.error(f"Error: {ai_data}")
                    st.caption("Tip: Switch models in the top 'Settings' menu.")
