import streamlit as st
import time

# --- Page Configuration ---
st.set_page_config(page_title="PflegePartner Prototype", page_icon="🇩🇪", layout="centered")

# --- Custom Styling for "Medical App" feel ---
st.markdown("""
    <style>
    .main-header { font-size: 2rem; color: #2C3E50; font-weight: 700; }
    .sub-text { font-size: 1.1rem; color: #7F8C8D; }
    .chat-box { padding: 15px; border-radius: 10px; margin-bottom: 10px; }
    .doctor-msg { background-color: #EBF5FB; border-left: 5px solid #3498DB; }
    .nurse-msg { background-color: #EAFAF1; border-left: 5px solid #2ECC71; }
    .feedback-box { background-color: #FDF2E9; border: 1px solid #E67E22; padding: 15px; border-radius: 5px; }
    </style>
""", unsafe_allow_html=True)

# --- Header ---
st.markdown('<div class="main-header">🇩🇪 PflegePartner</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-text">AI Voice Companion for Relocated Nurses in Germany</div>', unsafe_allow_html=True)
st.divider()

# --- Sidebar Context ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3063/3063176.png", width=50)
    st.write("## Target User")
    st.write("**Persona:** Priya, 28")
    st.write("**Origin:** India → **Goal:** Germany")
    st.write("**Challenge:** Passed B2 German exam, but freezes when doctors speak fast.")
    st.info("💡 **Prototype Goal:** Demonstrate voice-first roleplay.")

# --- Scenario Logic ---
scenarios = {
    "1. Morning Handover (Übergabe)": {
        "context": "It is 7:00 AM. Dr. Weber asks about Patient Müller's night.",
        "doctor_audio_text": "Guten Morgen Schwester. Wie war die Nacht bei Herrn Müller? Ist das Fieber runtergegangen?",
        "doctor_translation": "(Good morning Nurse. How was Mr. Müller's night? Did the fever go down?)",
        "nurse_correct_response": "Guten Morgen. Ja, das Fieber ist auf 37,5 gesunken. Er hat gut geschlafen.",
        "feedback_focus": "Past Tense Verbs (Perfekt)"
    },
    "2. Patient Distress (Notfall)": {
        "context": "A patient falls in the hallway.",
        "doctor_audio_text": "Schwester! Schnell! Herr Schmidt ist gestürzt! Bringen Sie den Notfallkoffer!",
        "doctor_translation": "(Nurse! Quick! Mr. Schmidt fell! Bring the emergency kit!)",
        "nurse_correct_response": "Ich komme sofort! Ich habe den Koffer.",
        "feedback_focus": "Urgency & Imperatives"
    }
}

selected_scenario = st.selectbox("Select Practice Scenario:", list(scenarios.keys()))
current_data = scenarios[selected_scenario]

# --- Main Interaction Area ---
st.info(f"📋 **Scenario Context:** {current_data['context']}")

# Step 1: Listen
st.subheader("1. Listen to the Doctor")
if st.button("🔊 Play Audio Prompt"):
    with st.spinner("Dr. Weber is speaking..."):
        time.sleep(1.5) # Simulate audio playing time
    st.markdown(f"""
        <div class="chat-box doctor-msg">
            <b>👨‍⚕️ Dr. Weber (Voice):</b><br>
            <i>"{current_data['doctor_audio_text']}"</i>
        </div>
    """, unsafe_allow_html=True)
    st.caption(f"Translation: {current_data['doctor_translation']}")

# Step 2: Speak
st.subheader("2. Speak Your Response")
st.write("Press record and answer in German.")

# "Wizard of Oz" Logic: We simulate the recording/processing for the demo
if st.button("🎙️ Hold to Record"):
    with st.spinner("Listening..."):
        time.sleep(2)
    st.success("Audio captured successfully.")
    
    # Simulate Processing
    with st.status("AI is analyzing your German...", expanded=True) as status:
        st.write("Transcribing audio to text...")
        time.sleep(1)
        st.write("Checking grammar consistency...")
        time.sleep(1)
        st.write("Analyzing medical tone...")
        time.sleep(0.5)
        status.update(label="Analysis Complete", state="complete", expanded=False)

    # --- Results Display ---
    st.divider()
    st.subheader("📊 Performance Report")
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Pronunciation", "85%", "Clear")
    col2.metric("Grammar", "90%", "Correct")
    col3.metric("Confidence", "High", "Steady Voice")

    st.markdown("### 🗣️ Transcript")
    st.markdown(f"""
        <div class="chat-box nurse-msg">
            <b>👩‍⚕️ You said:</b><br>
            "{current_data['nurse_correct_response']}"
        </div>
    """, unsafe_allow_html=True)

    st.markdown("### 💡 AI Coach Feedback")
    st.markdown(f"""
    <div class="feedback-box">
        <b>Focus Area: {current_data['feedback_focus']}</b><br>
        <ul>
            <li>✅ <b>Vocabulary:</b> Excellent use of medical terms.</li>
            <li>⚠️ <b>Tip:</b> Try to speak slightly faster to match the doctor's pace.</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)
