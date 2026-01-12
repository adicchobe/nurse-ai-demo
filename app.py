import streamlit as st
import google.generativeai as genai
from gtts import gTTS
import os
import json
import io
import time

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="CareLingo Live", page_icon="⚡", layout="centered")

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

# --- 2. UNLIMITED MODEL CONNECTOR ---
@st.cache_resource
def get_model():
    # Priority list based on your screenshot
    candidates = [
        "gemini-2.5-flash-native-audio-dialog", # ⚡ Your Unlimited Find
        "gemini-2.0-flash-exp",                 # ⚡ Standard Unlimited Preview
        "gemini-1.5-flash",                     # Fallback
        "gemini-1.5-flash-latest"
    ]
    
    status = st.empty()
    
    for name in candidates:
        try:
            status.info(f"🔌 Trying to connect to: {name}...")
            model = genai.GenerativeModel(name)
            # Quick test to see if it accepts standard text prompts
            model.generate_content("Ping") 
            status.success(f"✅ Connected to: **{name}**")
            time.sleep(1)
            status.empty()
            return model, name
        except Exception as e:
            # If the "Live" model rejects standard calls, we catch it here and move to the next
            print(f"Skipping {name}: {e}")
            continue
            
    status.error("❌ Could not connect. Please check your API Key.")
    return None, None

model, model_name = get_model()

if not model:
    st.stop()

# --- 3. SESSION STATE ---
if "messages" not in st.session_state: st.session_state.messages = []
if "scenario" not in st.session_state: st.session_state.scenario = None
if "feedback" not in st.session_state: st.session_state.feedback = None
if "last_audio_id" not in st.session_state: st.session_state.last_audio_id = None
if "recording_count" not in st.session_state: st.session_state.recording_count = 0
MAX_RECORDINGS = 20 # Increased limit since you have unlimited quota!

# --- 4. SCENARIOS ---
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

# --- 5. HELPER FUNCTIONS ---
def transcribe_audio(audio_bytes):
    try:
        # Prompt explicitly asks for text, even from native audio models
        prompt = "Transcribe this German audio exactly. Output ONLY the German text."
        response = model.generate_content([
            prompt,
            {"mime_type": "audio/mp3", "data": audio_bytes}
        ])
        return response.text.strip()
    except Exception as e:
        st.error(f"Transcription Error ({model_name}): {e}")
        return None

def get_teacher_response(user_text, scenario_key):
    scenario_data = SCENARIOS[scenario_key]
    
    system_prompt = f"""
    You are a German language tutor for nurses.
    ACT AS: {scenario_data['role']}
    USER GOAL: {scenario_data['goal']}
    
    1. Respond naturally in German (Spoken style, keep it short).
    2. Analyze the user's German strictly.
    
    Output ONLY JSON:
    {{
        "response_text": "German text to speak back",
        "feedback": {{
            "grammar_score": (1-10 integer),
            "politeness_score": (1-10 integer),
            "medical_score": (1-10 integer),
            "critique": "Brief English tip on mistake",
            "better_phrase": "Correct German phrase"
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
        st.error(f"Analysis Error: {e}")
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

# --- 6. MAIN UI ---
st.title("⚡ CareLingo Live")
# st.caption(f"Using Brain: {model_name}") 

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
    
    # Progress Bar (Increased to 20)
    usage = st.session_state.recording_count
    st.progress(usage / MAX_RECORDINGS, text=f"Session Limit: {usage}/{MAX_RECORDINGS}")

    if usage >= MAX_RECORDINGS:
        st.warning("🛑 Session limit reached. Refresh to restart.")
    else:
        # Chat History
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])
        
        # --- TEACHER FEEDBACK ---
        if st.session_state.feedback:
            f = st.session_state.feedback
            with st.expander("📊 Teacher's Feedback", expanded=True):
                c1, c2, c3 = st.columns(3)
                c1.metric("Grammar", f"{f.get('grammar_score', '?')}/10")
                c2.metric("Politeness", f"{f.get('politeness_score', '?')}/10")
                c3.metric("Medical", f"{f.get('medical_score', '?')}/10")
                st.info(f"💡 {f.get('critique', 'No specific critique.')}")
                st.success(f"🗣️ **Better:** \"{f.get('better_phrase', '')}\"")

        st.divider()
        audio_value = st.audio_input("Reply in German...")

        if audio_value:
            audio_bytes = audio_value.read()
            audio_id = hash(audio_bytes)

            # Loop Protection
            if audio_id != st.session_state.last_audio_id:
                st.session_state.last_audio_id = audio_id
                st.session_state.recording_count += 1
                
                with st.spinner(f"Listening with {model_name}..."):
                    user_text = transcribe_audio(audio_bytes)
                
                if user_text:
                    st.session_state.messages.append({"role": "user", "content": user_text})
                    
                    with st.spinner("Teacher is analyzing..."):
                        ai_data = get_teacher_response(user_text, st.session_state.scenario)
                        
                        if ai_data:
                            resp_text = ai_data["response_text"]
                            st.session_state.feedback = ai_data.get("feedback")
                            st.session_state.messages.append({"role": "assistant", "content": resp_text})
                            
                            audio_stream = text_to_speech_free(resp_text)
                            if audio_stream:
                                st.audio(audio_stream, format="audio/mp3", autoplay=True)
                    st.rerun()
