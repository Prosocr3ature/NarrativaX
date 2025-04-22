# main.py - Virtual Companion Application
# Updated with error fixes and improvements

import os
import json
import requests
import streamlit as st
import replicate
import base64
from io import BytesIO
from PIL import Image
from typing import Dict, List

# ========== CONFIGURATION ==========
LLM_MODEL = "gryphe/mythomax-l2-13b"
IMG_MODELS = {
    "Realistic": "lucataco/realistic-vision-v5.1",
    "Reliberate": "asiryan/reliberate-v3",
    "Anime": "stability-ai/sdxl"
}

MOODS = ["Neutral", "Flirty", "Aggressive", "Loving", "Submissive", "Dominant", "Mysterious", "Playful"]
RELATIONSHIPS = ["Stranger", "Friend", "Lover", "Partner", "Dom", "Sub", "Casual Hookup"]
SETTINGS = ["Bedroom", "Office", "Beach", "Dungeon", "Fantasy Realm", "Sci-Fi Spaceship"]

# ========== SESSION STATE INITIALIZATION ==========
def initialize_session_state():
    defaults = {
        "companions": {},
        "active_companion": None,
        "image_model": "Realistic",
        "chat_history": [],
        "current_scene": {
            "description": "",
            "images": [],
            "script": ""
        },
        "msg_buffer": ""
    }
    
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

initialize_session_state()

# ========== HELPER FUNCTIONS ==========
def generate_image(prompt: str, model_key: str = "Realistic") -> List[Image.Image]:
    try:
        model = IMG_MODELS[model_key]
        input_data = {
            "prompt": prompt,
            "width": 768,
            "height": 1024,
            "num_outputs": 1
        }
        
        output = replicate.run(model, input=input_data)
        if not output:
            st.error("Image generation failed")
            return []
            
        return [Image.open(BytesIO(requests.get(url).content)) for url in output]
    
    except Exception as e:
        st.error(f"Image error: {str(e)}")
        return []

def chat_with_model(prompt: str) -> str:
    try:
        headers = {
            "Authorization": f"Bearer {st.secrets['OPENROUTER_API_KEY']}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": LLM_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 1800,
            "temperature": 1.0
        }
        
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload
        )
        return response.json()["choices"][0]["message"]["content"]
    
    except Exception as e:
        return f"Error: {str(e)}"

# ========== UI COMPONENTS ==========
st.set_page_config(
    page_title="Virtual Companions",
    page_icon="💋",
    layout="wide",
    initial_sidebar_state="expanded"
)

with st.sidebar:
    st.title("💖 Companion Hub")
    
    if st.session_state.companions:
        st.subheader("Your Companions")
        for name, companion in st.session_state.companions.items():
            cols = st.columns([1, 4])
            with cols[0]:
                if companion.get('images'):
                    st.image(companion['images'][0], width=50)
            with cols[1]:
                if st.button(name, key=f"select_{name}"):
                    st.session_state.active_companion = name
                    st.rerun()
    
    with st.expander("➕ New Companion", expanded=not st.session_state.companions):
        with st.form("companion_creator"):
            name = st.text_input("Name")
            appearance = st.text_area("Appearance")
            personality = st.text_area("Personality")
            relationship = st.selectbox("Relationship", RELATIONSHIPS)
            setting = st.selectbox("Setting", SETTINGS)
            
            if st.form_submit_button("Create") and name:
                companion = {
                    "name": name,
                    "appearance": appearance,
                    "personality": personality,
                    "relationship": relationship,
                    "setting": setting,
                    "mood": "Neutral",
                    "images": [],
                    "chat_history": []
                }
                st.session_state.companions[name] = companion
                st.session_state.active_companion = name
                generate_image(f"Portrait of {name}: {appearance}")
                st.rerun()

    st.subheader("⚙️ Settings")
    st.radio("Image Style", list(IMG_MODELS.keys()), key="image_model")

if st.session_state.active_companion:
    companion = st.session_state.companions[st.session_state.active_companion]
    
    cols = st.columns([1, 4])
    with cols[0]:
        if companion.get('images'):
            st.image(companion['images'][0], width=150)
    with cols[1]:
        st.title(companion['name'])
        st.caption(f"💞 {companion['relationship']} | 🌍 {companion['setting']} | 😊 {companion['mood']}")
    
    st.divider()
    for msg in companion['chat_history']:
        if msg['role'] == 'user':
            with st.chat_message("user"):
                st.write(msg['content'])
        else:
            avatar = companion['images'][0] if companion.get('images') else "🦄"
            with st.chat_message("assistant", avatar=avatar):
                st.write(msg['content'])
                if msg.get('image'):
                    st.image(msg['image'], caption=f"{companion['name']}'s reaction")

    with st.expander("💬 Chat Controls", expanded=True):
        with st.form("chat_controls"):
            cols = st.columns(3)
            with cols[0]:
                mood = st.selectbox("Mood", MOODS, index=MOODS.index(companion['mood']))
            with cols[1]:
                intensity = st.slider("Intensity", 1, 5, 3)
            with cols[2]:
                action = st.selectbox("Action", [
                    "None", "Smile", "Touch", "Whisper", "Kiss", 
                    "Undress", "Tease", "Command", "Submit"
                ])
            
            msg = ""
            st.subheader("Quick Messages")
            quick_cols = st.columns(3)
            
            with quick_cols[0]:
                if st.form_submit_button("💋 Compliment"):
                    msg = "You look amazing"
            with quick_cols[1]:
                if st.form_submit_button("🔥 Flirt"):
                    msg = "I want you"
            with quick_cols[2]:
                if st.form_submit_button("😈 Tease"):
                    msg = "I know what you need..."
            
            custom_msg = st.text_input("Your message")
            final_msg = custom_msg or msg
            
            if st.form_submit_button("Send") and final_msg:
                companion['mood'] = mood
                prompt = f"""
                As {companion['name']} ({companion['personality']} {companion['relationship']}), 
                in {companion['setting']} (mood: {mood}), respond to: {final_msg}
                Action: {action} (intensity {intensity})
                """
                
                response = chat_with_model(prompt)
                companion['chat_history'].extend([
                    {"role": "user", "content": final_msg},
                    {"role": "assistant", "content": response}
                ])
                
                img_prompt = f"{companion['name']} {mood} during {action}, {companion['setting']}"
                images = generate_image(img_prompt)
                if images:
                    companion['chat_history'][-1]['image'] = images[0]
                
                st.rerun()

else:
    st.title("AI Companion Experience")
    st.subheader("Your personalized relationship simulator")
    
    if st.session_state.companions:
        st.warning("Select or create a companion")
    else:
        st.info("Create your first companion →")
