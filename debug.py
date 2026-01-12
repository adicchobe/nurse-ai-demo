import streamlit as st
import google.generativeai as genai

st.write("Checking available models...")
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    try:
        for m in genai.list_models():
            st.write(m.name)
    except Exception as e:
        st.error(e)
