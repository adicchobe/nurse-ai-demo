import streamlit as st
import openai
import os
import json
from datetime import datetime

# --- 1. CONFIGURATION & SETUP ---
st.set_page_config(
    page_title="CareLingo: German Practice",
    page_icon="🩺",
    layout="centered"
)

# Load API Key (Ensure this is in your .streamlit/secrets.toml)
if "OPENAI_API_KEY" in st.secrets:
    openai.api_key = st.secrets["OPENAI_API_KEY"]
else:
    st.error("🚨 OpenAI API Key missing! Please add it to Streamlit Secrets.")
    st.stop()

# Initialize Session State
if "messages" not in st.session_state:
    st.session_state.messages = []
if "scenario" not in st.session_state:
    st.session_state.scenario = None
if "feedback" not in st.session_state:
    st.session_state.feedback = None

# --- 2. SCENARIOS (German Nursing Context) ---
SCENARIOS = {
    "1. Anamnese (Admission)": {
        "role": "You are a new patient, Herr Müller, admitted for chest pain. You are anxious and speak only German. You speak simply but clearly.",
        "goal": "Collect patient history: Pain level, allergies, previous conditions.",
        "icon": "📝"
    },
    "2. Medikamentengabe (Medication)": {
        "role": "You are Frau Schneider, an elderly patient who refuses to take her new pills because she fears side effects. You are stubborn but polite.",
        "goal": "Explain why the medication is needed and calm her fears.",
        "icon": "💊"
    },
    "3. Schichtübergabe (Handover)": {
        "role": "You are the Morning Shift Doctor (Oberarzt). You are in a rush and need a quick, structured report (ISBAR format) on a patient.",
        "goal": "Give a structured handover report (Symptoms, Vitals, Actions taken).",
        "icon": "📋"
    },
    "4. Notfall (Emergency)": {
        "role": "You are a panic-stricken visitor whose husband has just collapsed in the waiting room.",
        "goal": "Calm the visitor and get essential details (Name, immediate symptoms) while acting fast.",
        "icon": "🚨"
    },
    "5. Entlassung (Discharge)": {
        "role": "You are a patient eager to go home after surgery. You don't understand the wound care instructions.",
        "goal": "Explain wound care (cleaning, dressing change) clearly and verify understanding.",
        "icon": "🏠"
    }
}

# --- 3. HELPER FUNCTIONS ---

def get_ai_response(user_text, scenario_key):
    """
    Generates the conversation response AND a critique of the user's German.
    """
    scenario_data = SCENARIOS[scenario_key]
    
    # We ask for a JSON response to separate the dialogue from the feedback
    system_prompt = f"""
    You are a German language tutor for nurses. 
    ACT AS: {scenario_data['role']}
    USER GOAL: {scenario_data['goal']}
    
    1. Respond naturally to the user in German as the character.
    2. Then, analyze the user's German input.
    
    Output purely in JSON format:
    {{
        "response_audio_text": "The German text you say back to the user as the character",
        "feedback": {{
            "grammar_score": (1-10),
            "politeness_score": (1-10, strict on 'Sie' form),
            "medical_term_accuracy": (1-10),
            "critique_english": "Brief English tip on their mistake (if any)",
            "better_german_phrase": "A more professional way to say what they tried to say"
        }}
    }}
    """
    
    messages = [
        {"role": "system", "content": system_prompt},
    ] 
    # Add history
    for msg in st.session_state.messages[-4:]: # Keep context short
        messages.append({"role": msg["role"], "content": msg["content"]})
    
    messages.append({"role": "user", "content": user_text})

    try:
        completion = openai.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            response_format={"type": "json_object"}
        )
        return json.loads(completion.choices[0].message.content)
    except Exception as e:
        st.error(f"AI Error: {e}")
        return None

def text_to_speech(text):
    """
    Converts AI response to audio using OpenAI TTS
    """
    try:
        response = openai.audio.speech.create(
            model="tts-1",
            voice="shimmer", # 'shimmer' has a clear, calming female tone
            input=text
        )
        return response.content
    except Exception as e:
        st.error(f"TTS Error: {e}")
        return None

# --- 4. MAIN UI ---

# Sidebar for Setup
with st.sidebar:
    st.title("🩺 CareLingo")
    st.markdown("*Deutsch für Pflegekräfte*")
    st.markdown("---")
    
    selected_scenario = st.radio("Select Practice Scenario:", list(SCENARIOS.keys()))
    
    if st.button("Start / Reset Scenario", type="primary"):
        st.session_state.messages = []
        st.session_state.scenario = selected_scenario
        st.session_state.feedback = None
        st.rerun()
    
    st.markdown("---")
    if st.session_state.feedback:
        f = st.session_state.feedback
        st.subheader("📊 Last Turn Analysis")
        st.progress(f['grammar_score']/10, text=f"Grammar: {f['grammar_score']}/10")
        st.progress(f['politeness_score']/10, text=f"Politeness (Sie): {f['politeness_score']}/10")
        st.progress(f['medical_term_accuracy']/10, text=f"Med. Terms: {f['medical_term_accuracy']}/10")
        st.info(f"💡 **Tip:** {f['critique_english']}")
        st.success(f"**Better:** {f['better_german_phrase']}")

# Main Chat Area
if not st.session_state.scenario:
    st.info("👈 Please select a scenario and click 'Start' to begin.")
    st.image("https://img.freepik.com/free-vector/health-professional-team_23-2148484530.jpg?w=900", width=400) # Minimalist Placeholder
else:
    # Header
    scen_data = SCENARIOS[st.session_state.scenario]
    st.markdown(f"### {scen_data['icon']} {st.session_state.scenario}")
    st.caption(f"**Goal:** {scen_data['goal']}")
    
    # Chat History (Display)
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])
    
    # --- AUDIO INPUT (The Core Interaction) ---
    st.markdown("---")
    st.write("🎙️ **Reply in German:**")
    
    # Native Streamlit Audio Input (Handles the "Red Recording" state automatically)
    audio_value = st.audio_input("Record your voice")

    if audio_value:
        # 1. Transcribe User Audio
        with st.spinner("Transcribing..."):
            transcript = openai.audio.transcriptions.create(
                model="whisper-1", 
                file=audio_value
            )
            user_text = transcript.text

        # 2. Display User Text
        st.session_state.messages.append({"role": "user", "content": user_text})
        st.rerun()

# Processing Logic (Triggered after rerun to show user msg first)
if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
    with st.spinner("Nurse AI is thinking..."):
        # Get AI Response & Feedback
        ai_data = get_ai_response(st.session_state.messages[-1]["content"], st.session_state.scenario)
        
        if ai_data:
            response_text = ai_data["response_audio_text"]
            st.session_state.feedback = ai_data["feedback"]
            
            # Generate Audio
            audio_bytes = text_to_speech(response_text)
            
            # Append to history
            st.session_state.messages.append({"role": "assistant", "content": response_text})
            
            # Auto-play audio (using hidden element or just standard player)
            if audio_bytes:
                 st.audio(audio_bytes, format="audio/mp3", autoplay=True)
            
            st.rerun()
