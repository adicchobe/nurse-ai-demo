import streamlit as st
import google.generativeai as genai
from gtts import gTTS
import os
import json
import io

# --- 1. CONFIGURATION & STYLE ---
st.set_page_config(page_title="CareLingo", page_icon="🩺", layout="centered")

# Custom CSS for "Apple-esque" Dark Mode Support
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    
    /* FIX: High Contrast Header for Dark Mode */
    .main-header {
        font-weight: 700;
        font-size: 2.5rem;
        text-align: center;
        margin-bottom: 0.5rem;
        color: #F8FAFC; /* Bright White-Grey */
        text-shadow: 0 2px 4px rgba(0,0,0,0.5);
    }
    
    .sub-header {
        font-size: 1.1rem;
        text-align: center;
        margin-bottom: 2rem;
        color: #CBD5E1; /* Lighter Grey */
    }

    /* Scenario Cards (Dark Mode Friendly) */
    .scenario-card {
        background-color: #1E293B; /* Slate 800 */
        padding: 1.5rem;
        border-radius: 16px;
        border: 1px solid #334155;
        text-align: center;
        transition: transform 0.2s;
        color: white;
    }
    
    /* Styled Buttons */
    .stButton button {
        border-radius: 12px;
        font-weight: 600;
        width: 100%;
        border: 1px solid #475569;
        transition: all 0.2s;
    }
    
    /* Feedback Box */
    .feedback-container {
        background: rgba(255, 255, 255, 0.05); /* Subtle glass effect */
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 16px;
        padding: 1.5rem;
        margin-top: 2rem;
    }

    /* FIX: HIDE "Press Enter to Apply" Text */
    div[data-testid="InputInstructions"] > span {
        display: none;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. AUTHENTICATION ---
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("🚨 System Error: API Key Missing.")
    st.stop()

if "APP_PASSWORD" in st.secrets:
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    
    def password_entered():
        if st.session_state["password_input"] == st.secrets["APP_PASSWORD"]:
            st.session_state.authenticated = True
        else:
            st.error("Incorrect Password")

    if not st.session_state
