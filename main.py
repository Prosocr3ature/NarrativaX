# main.py - Premium Virtual Companion Experience
# Enhanced with immersive UI, real-time interactions, and intelligent memory

import os
import time
import json
import requests
import streamlit as st
import replicate
from PIL import Image
from io import BytesIO
from typing import Dict, List

# ========== CORE CONFIGURATION ==========
LLM_MODEL = "gryphe/mythomax-l2-13b"
IMG_MODELS = {
    "Cinematic": "lucataco/realistic-vision-v5.1",
    "Anime": "stability-ai/sdxl"
}

MOOD_INTENSITIES = {
    "Playful": 1.2,
    "Dominant": 1.5,
    "Submissive": 0.8,
    "Sensual": 1.4,
    "Romantic": 1.1
}

GESTURES = ["Smirk", "Hair Flip", "Lip Bite", "Sultry Gaze", "Neck Touch"]

# ========== STATE MANAGEMENT ==========
class CompanionState:
    def __init__(self):
        self.companions = {}
        self.active_companion = None
        self.chat_history = []
        self.memory_context = []
        self.current_mood = "Playful"
        self.nsfw_level = 3
        
    def add_companion(self, name, bio, style):
        self.companions[name] = {
            "bio": bio,
            "style": style,
            "images": [],
            "memory": [],
            "arousal": 0.5
        }

def initialize_state():
    if "state" not in st.session_state:
        st.session_state.state = CompanionState()

initialize_state()

# ========== AI INTEGRATION ==========
class AIIntegrator:
    def __init__(self):
        self.chat_headers = {
            "Authorization": f"Bearer {st.secrets['OPENROUTER_API_KEY']}",
            "Content-Type": "application/json"
        }
        
    def generate_response(self, prompt, mood, nsfw_level):
        try:
            enhanced_prompt = f"[Mood: {mood}] [NSFW Level: {nsfw_level}/5] {prompt}"
            payload = {
                "model": LLM_MODEL,
                "messages": [{"role": "user", "content": enhanced_prompt}],
                "max_tokens": 1200,
                "temperature": MOOD_INTENSITIES.get(mood, 1.0),
                "top_p": 0.9 + (nsfw_level * 0.02)
            }
            
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=self.chat_headers,
                json=payload,
                timeout=30
            )
            return response.json()["choices"][0]["message"]["content"]
        
        except Exception as e:
            return f"💔 Connection lost... Please touch me again ({str(e)})"

    def generate_image(self, prompt, style):
        try:
            model = IMG_MODELS[style]
            response = replicate.run(model, input={
                "prompt": f"8K cinematic, {prompt}",
                "width": 1024,
                "height": 1368,
                "num_outputs": 1
            })
            return Image.open(BytesIO(requests.get(response[0]).content))
        except:
            return None

# ========== IMMERSIVE UI COMPONENTS ==========
def companion_avatar(companion):
    col1, col2 = st.columns([1, 3])
    with col1:
        if companion["images"]:
            st.image(companion["images"][-1], use_column_width=True)
        else:
            st.image("https://i.ibb.co/3WX5W0T/default-avatar.png", use_column_width=True)
    
    with col2:
        st.markdown(f"""
        <div class="companion-header">
            <h1>{list(st.session_state.state.companions.keys())[0]}</h1>
            <div class="mood-indicator">{st.session_state.state.current_mood}</div>
            <div class="nsfw-level">Intensity Level: {st.session_state.state.nsfw_level}/5</div>
        </div>
        """, unsafe_allow_html=True)

def chat_message(role, content, image=None):
    if role == "user":
        st.markdown(f"""
        <div class="user-message">
            <div class="message-bubble">{content}</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        col1, col2 = st.columns([1, 4])
        with col1:
            if image:
                st.image(image, use_column_width=True)
        with col2:
            st.markdown(f"""
            <div class="companion-message">
                <div class="message-bubble">{content}</div>
            </div>
            """, unsafe_allow_html=True)

# ========== MAIN INTERFACE ==========
def main():
    st.set_page_config(
        page_title="Elysium Companions",
        page_icon="💞",
        layout="centered",
        initial_sidebar_state="collapsed"
    )
    
    st.markdown("""
    <style>
    .companion-header { border-bottom: 2px solid #ff4b4b; padding: 1rem; }
    .message-bubble {
        padding: 1.2rem;
        border-radius: 1.5rem;
        margin: 0.5rem 0;
        background: rgba(255, 75, 75, 0.1);
    }
    .user-message { text-align: right; }
    .companion-message { text-align: left; }
    </style>
    """, unsafe_allow_html=True)

    ai = AIIntegrator()
    state = st.session_state.state

    # Companion Creation
    if not state.companions:
        with st.container():
            st.title("💋 Create Your Perfect Companion")
            name = st.text_input("Her Name")
            bio = st.text_area("Personality Profile", height=150)
            style = st.selectbox("Visual Style", list(IMG_MODELS.keys()))
            
            if st.button("Bring to Life"):
                if name and bio:
                    state.add_companion(name, bio, style)
                    state.active_companion = name
                    st.rerun()
            return

    # Main Chat Interface
    companion = state.companions[state.active_companion]
    
    # Header Section
    companion_avatar(companion)
    
    # Chat History
    for idx, entry in enumerate(state.chat_history):
        if entry["type"] == "user":
            chat_message("user", entry["content"])
        else:
            chat_message("companion", entry["content"], entry.get("image"))

    # Interaction Controls
    with st.form("chat_form", clear_on_submit=True):
        col1, col2 = st.columns([3, 1])
        with col1:
            user_input = st.text_input("Whisper to your companion...", key="input")
        with col2:
            submitted = st.form_submit_button("Send ➤")

        with st.expander("Advanced Settings"):
            state.current_mood = st.selectbox("Mood Atmosphere", list(MOOD_INTENSITIES.keys()))
            selected_gesture = st.selectbox("Body Language", GESTURES)
            state.nsfw_level = st.slider("Intensity Level", 1, 5, 3)

    if submitted and user_input:
        # Store user message
        state.chat_history.append({
            "type": "user",
            "content": user_input,
            "timestamp": time.time()
        })

        # Generate companion response
        prompt = f"{companion['bio']} Current context: {selected_gesture}. User says: {user_input}"
        response = ai.generate_response(prompt, state.current_mood, state.nsfw_level)
        
        # Generate response image
        image_prompt = f"{state.active_companion}, {state.current_mood} mood, {selected_gesture}, {companion['bio']}"
        response_image = ai.generate_image(image_prompt, companion["style"])
        
        # Store companion response
        state.chat_history.append({
            "type": "companion",
            "content": response,
            "image": response_image,
            "mood": state.current_mood,
            "gesture": selected_gesture,
            "timestamp": time.time()
        })
        
        st.rerun()

if __name__ == "__main__":
    main()
