import streamlit as st
import google.generativeai as genai
from gtts import gTTS
import os
import json
import io

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="CareLingo: German Practice", page_icon="🩺", layout="centered")

# Load API Key
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("🚨 Gemini API Key missing! Add 'GEMINI_API_KEY' to Streamlit Secrets.")
    st.stop()

# --- PASSWORD PROTECTION ---
if "APP_PASSWORD" in st.secrets:
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    
    if not st.session_state.authenticated:
        st.title("🔒 Login Required")
        user_pwd = st.text_input("Enter Access Password", type="password")
        if st.button("Login"):
            if user_pwd == st.secrets["APP_PASSWORD"]:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Incorrect password.")
        st.stop()

# --- SMART MODEL SELECTOR ---
try:
    available_models = [m.name for m in genai.list_models()]
    # Priority 1: Specific Stable 1.5 Flash
    if "models/gemini-1.5-flash-001" in available_models:
        model_name = "models/gemini-1.5-flash-001"
    # Priority 2: Generic 1.5 Flash
    elif "models/gemini-1.5-flash" in available_models:
        model_name = "models/gemini-1.5-flash"
    # Fallback
    else:
        model_name = "models/gemini-1.5-flash"

    model = genai.GenerativeModel(model_name)
except Exception as e:
    st.error(f"Error finding model: {e}")
    model = genai.GenerativeModel("models/gemini-1.5-flash")

# --- SESSION STATE ---
if "messages" not in st.session_state: st.session_state.messages = []
if "scenario" not in st.session_state: st.session_state.scenario = None
if "feedback" not in st.session_state: st.session_state.feedback = None
if "last_audio_id" not in st.session_state: st.session_state.last_audio_id = None
if "recording_count" not in st.session_state: st.session_state.recording_count = 0
MAX_RECORDINGS = 10

# --- 2. SCENARIOS ---
SCENARIOS = {
    "1. Anamnese (Admission)": {
        "role": "You are a new patient, Herr Müller. You are anxious and speak only German.",
        "goal": "Collect patient history.",
        "icon": "📝"
    },
    "2. Medikamentengabe (Medication)": {
        "role": "You are Frau Schneider. You refuse to take pills.",
        "goal": "Explain why medication is needed.",
        "icon": "💊"
    },
    "3. Notfall (Emergency)": {
        "role": "You are a visitor whose husband collapsed.",
        "goal": "Get details fast.",
        "icon": "🚨"
    }
}

# --- 3. HELPER FUNCTIONS ---
def transcribe_audio_with_gemini(audio_bytes):
    try:
        prompt = "Transcribe this German audio exactly."
        response = model.generate_content([
            prompt,
            {"mime_type": "audio/mp3", "data": audio_bytes}
        ])
        return response.text.strip()
    except Exception as e:
        st.error(f"Transcription Error: {e}")
        return None

def get_ai_response(user_text, scenario_key):
    scenario_data = SCENARIOS[scenario_key]
    
    # ENHANCED PROMPT: Demands detailed scoring
    system_prompt = f"""
    You are a strict German language tutor for nurses.
    ACT AS: {scenario_data['role']}
    USER GOAL: {scenario_data['goal']}
    
    1. Respond naturally in German (Keep it short, spoken style).
    2. Analyze the user's German input strictly.
    
    Output ONLY JSON:
    {{
        "response_text": "German text to speak back",
        "feedback": {{
            "grammar_score": (1-10 integer),
            "politeness_score": (1-10 integer, strict on 'Sie' vs 'Du'),
            "medical_score": (1-10 integer, use of correct terms),
            "critique": "Brief English explanation of the biggest mistake",
            "better_phrase": "The perfect German phrase they SHOULD have used"
        }}
    }}
    """
    
    try:
        response = model.generate_content(
            f"{system_prompt}\nUser said: {user_text}", 
            generation_config={"response_mime_type": "application/json"}
        )
        return json.loads(response.text)
    except Exception as e:
        st.error(f"AI Logic Error: {e}")
        return None

def text_to_speech_free(text):
    try:
        tts = gTTS(text=text, lang='de')
        mp3_fp = io.BytesIO()
        tts.write_to_fp(mp3_fp)
        mp3_fp.seek(0)
        return mp3_fp
    except Exception as e:
        st.error(f"TTS Error: {e}")
        return None

# --- 4. MAIN UI ---
st.title("🩺 CareLingo")

if not st.session_state.scenario:
    st.info("👈 Select a scenario to start.")
    cols = st.columns(len(SCENARIOS))
    for i, (key, val) in enumerate(SCENARIOS.items()):
        if cols[i].button(f"{val['icon']} {key.split(' ')[1]}"):
            st.session_state.scenario = key
            st.session_state.recording_count = 0
            st.rerun()
else:
    scen = SCENARIOS[st.session_state.scenario]
    st.subheader(f"{scen['icon']} {st.session_state.scenario}")
    
    # Progress Bar for Usage
    usage = st.session_state.recording_count
    st.progress(usage / MAX_RECORDINGS, text=f"Session Limit: {usage}/{MAX_RECORDINGS}")

    if usage >= MAX_RECORDINGS:
        st.warning("🛑 Limit reached! Please click 'Start / Reset' in the sidebar.")
    else:
        # Chat History
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])
        
        # --- DETAILED FEEDBACK SECTION (Restored) ---
        if st.session_state.feedback:
            f = st.session_state.feedback
            with st.expander("📊 Teacher's Feedback (Last Turn)", expanded=True):
                c1, c2, c3 = st.columns(3)
                c1.metric("Grammar", f"{f.get('grammar_score', 0)}/10")
                c2.metric("Politeness", f"{f.get('politeness_score', 0)}/10")
                c3.metric("Medical", f"{f.get('medical_score', 0)}/10")
                
                st.info(f"💡 **Correction:** {f.get('critique', 'No comments.')}")
                st.success(f"🗣️ **Better:** \"{f.get('better_phrase', '')}\"")

        st.divider()
        
        # Audio Input
        audio_value = st.audio_input("Reply in German...")

        if audio_value:
            audio_bytes = audio_value.read()
            audio_id = hash(audio_bytes)

            if audio_id != st.session_state.last_audio_id:
                st.session_state.last_audio_id = audio_id
                st.session_state.recording_count += 1
                
                with st.spinner("Listening..."):
                    user_text = transcribe_audio_with_gemini(audio_bytes)
                
                if user_text:
                    st.session_state.messages.append({"role": "user", "content": user_text})
                    
                    with st.spinner("Analyzing & Replying..."):
                        ai_data = get_ai_response(user_text, st.session_state.scenario)
                        
                        if ai_data:
                            resp_text = ai_data["response_text"]
                            st.session_state.feedback = ai_data.get("feedback")
                            
                            audio_stream = text_to_speech_free(resp_text)
                            st.session_state.messages.append({"role": "assistant", "content": resp_text})
                            
                            if audio_stream:
                                st.audio(audio_stream, format="audio/mp3", autoplay=True)
                    st.rerun()
