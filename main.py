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
if "companions" not in st.session_state:
    st.session_state.companions = {}

if "active_companion" not in st.session_state:
    st.session_state.active_companion = None

if "image_model" not in st.session_state:
    st.session_state.image_model = "Realistic"

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "current_scene" not in st.session_state:
    st.session_state.current_scene = {
        "description": "",
        "images": [],
        "script": ""
    }

# ========== HELPER FUNCTIONS ==========
def generate_image(prompt, model_key="Realistic") -> List[Image.Image]:
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

def generate_companion_image(companion):
    prompt = f"8k portrait of {companion['name']}, {companion['appearance']}, {companion['mood']}, {companion['setting']}, detailed facial features, expressive eyes"
    images = generate_image(prompt, st.session_state.image_model)
    if images:
        companion['images'] = images
        return images[0]
    return None

# ========== UI COMPONENTS ==========
st.set_page_config(page_title="Virtual Companions", page_icon="💋", layout="wide")

# Sidebar for companion management
with st.sidebar:
    st.title("💖 Companion Hub")
    
    # Quick companion selection
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
    
    # New companion creation
    with st.expander("➕ New Companion", expanded=not st.session_state.companions):
        with st.form("companion_creator"):
            name = st.text_input("Name")
            appearance = st.text_area("Appearance Description")
            personality = st.text_area("Personality Traits")
            relationship = st.selectbox("Relationship", RELATIONSHIPS)
            setting = st.selectbox("Default Setting", SETTINGS)
            
            if st.form_submit_button("Create Companion"):
                if name:
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
                    generate_companion_image(companion)
                    st.rerun()

    # Settings
    st.subheader("⚙️ Settings")
    st.radio("Image Style", list(IMG_MODELS.keys()), key="image_model")

# Main chat interface
if st.session_state.active_companion:
    companion = st.session_state.companions[st.session_state.active_companion]
    
    # Companion profile header
    cols = st.columns([1, 4])
    with cols[0]:
        if companion.get('images'):
            st.image(companion['images'][0], width=150)
    with cols[1]:
        st.title(companion['name'])
        st.caption(f"💞 {companion['relationship']} | 🌍 {companion['setting']} | 😊 {companion['mood']}")
    
    # Chat history display
    st.divider()
    for msg in companion['chat_history']:
        if msg['role'] == 'user':
            with st.chat_message("user"):
                st.write(msg['content'])
        else:
            with st.chat_message("assistant", avatar=companion['images'][0] if companion.get('images') else None):
                st.write(msg['content'])
                if msg.get('image'):
                    st.image(msg['image'], caption=f"{companion['name']}'s reaction")
    
    # Interactive controls
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
        
        # Initialize message storage
        msg = ""
        st.subheader("Quick Messages")
        quick_cols = st.columns(3)
        
        # Quick message buttons
        with quick_cols[0]:
            if st.form_submit_button("💋 Compliment"):
                msg = "You look amazing today"
        with quick_cols[1]:
            if st.form_submit_button("🔥 Flirt"):
                msg = "I can't stop thinking about you"
        with quick_cols[2]:
            if st.form_submit_button("😈 Tease"):
                msg = "I know what you want..."
        
        custom_msg = st.text_input("Or type your own message")
        final_msg = custom_msg or msg  # Safely handle undefined msg
        
        if st.form_submit_button("Send") and final_msg:
            # Update companion state
            companion['mood'] = mood
            
            # Generate response
            prompt = f"""
            You are {companion['name']}, a {companion['personality']} {companion['relationship']}.
            Current setting: {companion['setting']}. Mood: {mood}. 
            User action: {action}. Intensity level: {intensity}.
            User says: {final_msg}
            Respond naturally and stay in character.
            """
            
            response = chat_with_model(prompt)
            companion['chat_history'].append({"role": "user", "content": final_msg})
            companion['chat_history'].append({
                "role": "assistant",
                "content": response,
                "mood": mood,
                "intensity": intensity
            })
            
            # Generate reaction image
            image_prompt = f"""
            {companion['name']}, {companion['appearance']}, {mood} expression,
            performing {action}, intensity {intensity}, {companion['setting']},
            8k high detail, realistic lighting
            """
            images = generate_image(image_prompt, st.session_state.image_model)
            if images:
                companion['chat_history'][-1]['image'] = images[0]
            
            st.rerun()

    # Scene creation section
    st.divider()
    st.subheader("🎭 Interactive Scenes")
    
    with st.expander("💞 Romantic Scene"):
        cols = st.columns(3)
        with cols[0]:
            if st.button("Slow Dance"):
                scene = f"{companion['name']} takes you in their arms for a slow, sensual dance"
        with cols[1]:
            if st.button("First Kiss"):
                scene = f"{companion['name']} leans in for your first passionate kiss"
        with cols[2]:
            if st.button("Candlelight Dinner"):
                scene = f"You share an intimate candlelight dinner with {companion['name']}"
        
    with st.expander("🔥 Erotic Scene"):
        cols = st.columns(3)
        with cols[0]:
            if st.button("Undressing"):
                scene = f"{companion['name']} slowly undresses before you"
        with cols[1]:
            if st.button("Oral Play"):
                scene = f"{companion['name']} kneels before you with hungry eyes"
        with cols[2]:
            if st.button("Full Sex"):
                scene = f"{companion['name']} leads you to bed for passionate lovemaking"
    
    with st.expander("😈 Kinky Scene"):
        cols = st.columns(3)
        with cols[0]:
            if st.button("Bondage"):
                scene = f"{companion['name']} ties you up with expert knots"
        with cols[1]:
            if st.button("Sensation Play"):
                scene = f"{companion['name']} teases you with feathers and ice"
        with cols[2]:
            if st.button("Roleplay"):
                scene = f"{companion['name']} suggests an exciting roleplay scenario"
    
    if 'scene' in locals():
        detailed_scene = chat_with_model(f"""
        Expand this erotic scene in vivid detail: {scene}. 
        Characters: You and {companion['name']} ({companion['personality']}).
        Mood: {companion['mood']}. Relationship: {companion['relationship']}.
        Setting: {companion['setting']}.
        """)
        
        st.session_state.current_scene = {
            "description": detailed_scene,
            "images": generate_image(f"{scene}, {companion['setting']}, 8k detailed"),
            "script": detailed_scene
        }
        st.rerun()
    
    # Display current scene
    if st.session_state.current_scene.get('description'):
        st.subheader("Current Scene")
        st.write(st.session_state.current_scene['description'])
        if st.session_state.current_scene.get('images'):
            st.image(st.session_state.current_scene['images'][0], caption=companion['name'])
        
        # Scene controls
        cols = st.columns(3)
        with cols[0]:
            if st.button("❤️ Continue Scene"):
                continued_scene = chat_with_model(f"""
                Continue this scene naturally: {st.session_state.current_scene['description']}
                Maintain {companion['name']}'s personality: {companion['personality']}
                Current mood: {companion['mood']}
                """)
                st.session_state.current_scene['description'] += "\n\n" + continued_scene
                st.rerun()
        with cols[1]:
            if st.button("📸 Add Scene Image"):
                new_images = generate_image(
                    f"{st.session_state.current_scene['description']}, 8k detailed photo",
                    st.session_state.image_model
                )
                st.session_state.current_scene['images'].extend(new_images)
                st.rerun()
        with cols[2]:
            if st.button("💾 Save Scene"):
                companion['chat_history'].append({
                    "role": "system",
                    "content": f"Saved scene: {st.session_state.current_scene['description']}",
                    "images": st.session_state.current_scene['images']
                })
                st.success("Scene saved to companion's memory")
                st.session_state.current_scene = {"description": "", "images": [], "script": ""}
                st.rerun()

else:
    # Welcome screen when no companion is selected
    st.title("Virtual Companion Experience")
    st.subheader("Your personalized AI relationship simulator")
    
    if st.session_state.companions:
        st.warning("Select a companion from the sidebar or create a new one")
    else:
        st.info("Create your first companion using the sidebar!")
    
    st.image("https://i.imgur.com/JQJZQYF.jpg", caption="Your perfect companion awaits")
    st.write("""
    ### Features:
    - 🎭 Fully interactive companions with memory
    - 💬 Natural conversation with emotional depth
    - 🖼️ Dynamic image generation based on interactions
    - 🔥 Customizable relationship dynamics
    - 🎭 Pre-built intimate scenarios
    """)
