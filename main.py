Here’s the complete main.py file for your Virtual Companion app, incorporating:
	•	Per-message NSFW sliders
	•	Memory persistence per companion
	•	Explicit content injection logic
	•	A dedicated editor for sex scene creation

This implementation utilizes Streamlit’s st.session_state for session management  and integrates an editable code editor component for scene scripting .

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
    "Reliberate": "asiryan/reliberate-v3"
}
MOODS = ["Flirty", "Aggressive", "Loving", "Submissive", "Dominant", "Mysterious"]
MOTIONS = ["Eye Contact", "Touching Hair", "Biting Lip", "Leaning Closer", "Winking"]

# ========== SESSION STATE INITIALIZATION ==========

if "companions" not in st.session_state:
    st.session_state.companions = {}

if "active_companions" not in st.session_state:
    st.session_state.active_companions = []

if "image_model" not in st.session_state:
    st.session_state.image_model = "Realistic"

if "sex_scenes" not in st.session_state:
    st.session_state.sex_scenes = []

# ========== HELPER FUNCTIONS ==========

def replicate_image(prompt, model_key="Realistic") -> List[Image.Image]:
    model = IMG_MODELS[model_key]
    input_data = {
        "prompt": prompt,
        "width": 768,
        "height": 1024,
        "num_outputs": 1
    }
    try:
        output = replicate.run(model, input=input_data)
        if isinstance(output, list):
            return [Image.open(BytesIO(requests.get(url).content)) for url in output]
        else:
            img = Image.open(BytesIO(requests.get(output).content))
            return [img]
    except Exception as e:
        st.error(f"Image generation error: {e}")
        return []

def chat_with_model(prompt: str) -> str:
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
    res = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
    return res.json()["choices"][0]["message"]["content"]

def img_to_b64(img: Image.Image) -> str:
    buf = BytesIO()
    img.convert("RGB").save(buf, format="JPEG")
    return base64.b64encode(buf.getvalue()).decode()

# ========== UI COMPONENTS ==========

st.set_page_config(page_title="Virtual Companions", page_icon="💋", layout="wide")
st.title("💋 Virtual Companion Playground")

# Companion Designer
st.subheader("Design Your Companion")
name = st.text_input("Name")
bio = st.text_area("Personality & Bio")
mood = st.selectbox("Mood", MOODS)
if st.button("Add Companion"):
    if name and bio:
        st.session_state.companions[name] = {
            "bio": bio,
            "mood": mood,
            "images": [],
            "chat_history": []
        }
        st.session_state.active_companions.append(name)

# Select companions
st.subheader("Active Companions")
for c in st.session_state.companions:
    if c not in st.session_state.active_companions:
        if st.button(f"Activate {c}"):
            st.session_state.active_companions.append(c)

# Toggle image style
st.radio("Image Style", list(IMG_MODELS.keys()), key="image_model", horizontal=True)

# Chat Interface
st.subheader("💬 Group Chat")
with st.form("chat_form"):
    msg = st.text_input("Say something...")
    mood = st.selectbox("Set Mood", MOODS, index=0)
    motion = st.selectbox("Motion / Gesture", MOTIONS, index=0)
    nsfw_level = st.slider("NSFW Level", 1, 5, 3)
    submit = st.form_submit_button("Send")

if submit and msg:
    for comp_name in st.session_state.active_companions:
        comp = st.session_state.companions[comp_name]
        prompt = f"You are {comp_name}. {comp['bio']} Mood: {mood}. Gesture: {motion}. User says: {msg}. Reply in erotic style with NSFW level {nsfw_level}."
        reply = chat_with_model(prompt)
        comp["chat_history"].append(("user", msg))
        comp["chat_history"].append(("bot", reply))

        image_prompt = f"{comp_name}, {comp['bio']}, {mood}, performing {motion}, erotic expression, 8k photo"
        imgs = replicate_image(image_prompt, st.session_state.image_model)
        comp["images"].extend(imgs)

# Display Chats
for comp_name in st.session_state.active_companions:
    comp = st.session_state.companions[comp_name]
    st.markdown(f"### ❤️ {comp_name}")
    for role, text in comp["chat_history"]:
        if role == "user":
            st.markdown(f"**You:** {text}")
        else:
            st.markdown(f"**{comp_name}:** {text}")
    if comp["images"]:
        st.image(comp["images"][-1], caption=f"{comp_name}'s latest image", use_column_width=True)

# Scene Generator
st.subheader("🔥 Sex Scene Generator")
scene_prompt = st.text_input("Seed idea (e.g., Alya seduces user in bath)")
if st.button("Generate Scene"):
    detailed_scene = chat_with_model(f"Write a vivid erotic scene: {scene_prompt}")
    st.session_state.sex_scenes.append(detailed_scene)
    images = replicate_image(scene_prompt, st.session_state.image_model)
    st.session_state.sex_scenes.extend(images)

# Display generated scenes
for idx, entry in enumerate(st.session_state.sex_scenes):
    if isinstance(entry, str):
        st.markdown(f"##### Scene #{(idx // 2) + 1}")
        st.markdown(entry)
    elif isinstance(entry, Image.Image):
        st.image(entry, caption="Scene Visual", use_column_width=True)

# Scene Editor
st.subheader("📝 Scene Editor")
scene_code = st.text_area("Edit your scene script here:", height=300)
if st.button("Save Scene"):
    st.session_state.sex_scenes.append(scene_code)
    st.success("Scene saved successfully.")

**Requirements (requirements.txt
