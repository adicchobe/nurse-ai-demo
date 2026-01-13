import streamlit as st
import google.generativeai as genai
from gtts import gTTS
import os
import json
import io
import time

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="CareLingo", page_icon="🩺", layout="centered")

# --- 2. UNIVERSAL STYLING (Light & Dark Mode Safe) ---
st.markdown("""
<style>
    /* Global Font - San Francisco / Inter Style */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

    /* Scenario Cards - Adaptive Coloring */
    .scenario-card {
        border: 1px solid rgba(128, 128, 128, 0.2);
        border-radius: 12px;
        padding: 1.5rem;
        text-align: center;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        background-color: transparent; /* Lets Streamlit theme shine through */
        transition: transform 0.2s ease;
    }
    .scenario-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 6px 12px rgba(0,0,0,0.1);
        border-color: #FF4B4B; /* Streamlit Red accent */
    }
    
    /* Clean Buttons */
    div.stButton > button {
        width: 100%;
        border-radius: 8px;
        font-weight: 600;
        border: 1px solid rgba(128, 128, 128, 0.2);
        padding: 0.5rem 1rem;
    }

    /* Hide the default 'Press Enter to Apply' text on input */
    div[data-testid="InputInstructions"] > span { display: none; }
</style>
""", unsafe_allow_html=True)

# --- 3. AUTHENTICATION ---
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("🚨 System Error: API Key Missing in Streamlit Secrets.")
    st.stop()

if "APP_PASSWORD" in st.secrets:
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    
    if not st.session_state.authenticated:
        st.markdown("<h2 style='text-align: center;'>🔒 CareLingo Login</h2>", unsafe_allow_html=True)
        # Using a form prevents alignment issues
        with st.form("login_form"):
            user_pwd = st.text_input("Password", type="password")
            if st.form_submit_button("Enter", use_container_width=True):
                if user_pwd == st.secrets["APP_PASSWORD"]:
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("Incorrect Password.")
        st.stop()

# --- 4. ROBUST MODEL CONNECTION ---
@st.cache_resource
def load_model():
    # We stick to the standard stable model to prevent "404" errors
    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        model.generate_content("Ping") # Quick test
        return model
    except Exception as e:
        return None

model = load_model()
if not model:
    st.error("⚠️ AI Service Unavailable. Please check your API Key or Quota.")
    st.stop()

# --- 5. SESSION STATE ---
if "messages" not in st.session_state: st.session_state.messages = []
if "scenario" not in st.session_state: st.session_state.scenario = None
if "feedback" not in st.session_state: st.session_state.feedback = None
if "last_audio_id" not in st.session_state: st.session_state.last_audio_id = None

# --- 6. SCENARIO DATA (The Identified Themes) ---
SCENARIOS = {
    "Admission": {
        "icon": "📋", 
        "title": "Patient Admission", 
        "role": "You are Herr Müller. You are anxious and speak only German.", 
        "goal": "Collect patient history (Anamnese)."
    },
    "Medication": {
        "icon": "💊", 
        "title": "Medication Refusal", 
        "role": "You are Frau Schneider. You refuse to take your pills.", 
        "goal": "Explain why medication is needed."
    },
    "Emergency": {
        "icon": "🚨", 
        "title": "Emergency Triage", 
        "role": "You are a visitor whose husband just collapsed.", 
        "goal": "Get vital details immediately."
    }
}

# --- 7. CORE LOGIC ---
def process_audio(audio_bytes, scenario_key):
    # 1. Transcribe
    try:
        prompt = "Transcribe this German audio exactly. Output ONLY the German text."
        resp = model.generate_content([prompt, {"mime_type": "audio/mp3", "data": audio_bytes}])
        user_text = resp.text.strip()
    except:
        return None, None

    # 2. Analyze (The "Nurse Companion" Logic)
    scen = SCENARIOS[scenario_key]
    analysis_prompt = f"""
    Act as a strict German Tutor for Nurses.
    Role: {scen['role']}
    User Goal: {scen['goal']}
    
    1. Respond naturally in German (Keep it spoken and short).
    2. Analyze the user's German input.
    
    Output JSON ONLY:
    {{
        "response_text": "German reply",
        "feedback": {{
            "grammar": (1-10), "politeness": (1-10), "medical": (1-10),
            "critique": "One sentence tip in English", 
            "better_phrase": "The ideal German phrase they should have used"
        }}
    }}
    """
    try:
        res = model.generate_content(f"{analysis_prompt}\nUser: {user_text}", generation_config={"response_mime_type": "application/json"})
        data = json.loads(res.text)
        return user_text, data
    except:
        return user_text, None

def text_to_speech(text):
    try:
        tts = gTTS(text=text, lang='de')
        buf = io.BytesIO()
        tts.write_to_fp(buf)
        buf.seek(0)
        return buf
    except:
        return None

# --- 8. UI LAYOUT ---
st.title("🩺 CareLingo")

# SCENARIO SELECTOR (Home Screen)
if not st.session_state.scenario:
    st.markdown("### Select Practice Scenario")
    st.markdown("Choose a module to begin your shift.")
    
    # 3-Column Card Layout
    c1, c2, c3 = st.columns(3)
    
    with c1:
        st.markdown(f"<div class='scenario-card'><h1>{SCENARIOS['Admission']['icon']}</h1><h3>Admission</h3></div>", unsafe_allow_html=True)
        if st.button("Start Admission"):
            st.session_state.scenario = "Admission"
            st.rerun()

    with c2:
        st.markdown(f"<div class='scenario-card'><h1>{SCENARIOS['Medication']['icon']}</h1><h3>Medication</h3></div>", unsafe_allow_html=True)
        if st.button("Start Medication"):
            st.session_state.scenario = "Medication"
            st.rerun()

    with c3:
        st.markdown(f"<div class='scenario-card'><h1>{SCENARIOS['Emergency']['icon']}</h1><h3>Emergency</h3></div>", unsafe_allow_html=True)
        if st.button("Start Emergency"):
            st.session_state.scenario = "Emergency"
            st.rerun()

# ACTIVE SESSION SCREEN
else:
    curr = SCENARIOS[st.session_state.scenario]
    
    # Header & Navigation
    col_nav, col_title = st.columns([1, 4])
    with col_nav:
        if st.button("← Exit"):
            st.session_state.scenario = None
            st.session_state.messages = []
            st.session_state.feedback = None
            st.rerun()
    with col_title:
        st.markdown(f"**{curr['title']}**")
        st.caption(f"🎯 Goal: {curr['goal']}")

    st.divider()

    # Chat History
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"], avatar="👤" if msg["role"]=="user" else "🤖"):
            st.write(msg["content"])

    # Feedback Card (Visual Appeal)
    if st.session_state.feedback:
        f = st.session_state.feedback
        with st.expander("📊 Performance Analysis", expanded=True):
            cols = st.columns(3)
            cols[0].metric("Grammar", f"{f.get('grammar',0)}/10")
            cols[1].metric("Politeness", f"{f.get('politeness',0)}/10")
            cols[2].metric("Medical", f"{f.get('medical',0)}/10")
            st.info(f"💡 **Tip:** {f.get('critique', 'N/A')}")
            st.success(f"🗣️ **Better:** \"{f.get('better_phrase', 'N/A')}\"")

    # Audio Input (The "Action" Area)
    st.markdown("###")
    audio_val = st.audio_input("Tap to Speak...")
    
    if audio_val:
        # Check for new recording
        current_id = hash(audio_val.getvalue())
        if current_id != st.session_state.last_audio_id:
            st.session_state.last_audio_id = current_id
            
            # --- THE FIX: VISUAL STATUS ---
            # This box proves to the user/interviewer that the app is working
            with st.status("✅ Audio captured! Processing...", expanded=True) as status:
                
                st.write("📝 Transcribing audio...")
                user_text, ai_data = process_audio(audio_val.read(), st.session_state.scenario)
                
                if user_text and ai_data:
                    st.write("🧠 Generating feedback...")
                    # Update State
                    st.session_state.messages.append({"role": "user", "content": user_text})
                    st.session_state.feedback = ai_data["feedback"]
                    st.session_state.messages.append({"role": "assistant", "content": ai_data["response_text"]})
                    
                    # Audio Reply
                    mp3 = text_to_speech(ai_data["response_text"])
                    status.update(label="Complete!", state="complete", expanded=False)
                    
                    if mp3:
                        st.audio(mp3, format="audio/mp3", autoplay=True)
                    
                    time.sleep(1) # Visual pause
                    st.rerun()
                else:
                    status.update(label="Error connecting to AI", state="error")
                    st.error("Please try again. API Key may be busy.")
