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
        "msg_buffer": ""  # Added message buffer
    }
    
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

initialize_session_state()

# ========== HELPER FUNCTIONS ==========
def generate_image(prompt: str, model_key: str = "Realistic") -> List[Image.Image]:
    """Generate images using Replicate API with error handling"""
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
            raise ValueError("Empty response from image generation API")
            
        if isinstance(output, list):
            return [Image.open(BytesIO(requests.get(url).content)) for url in output]
        return [Image.open(BytesIO(requests.get(output).content))]
    
    except Exception as e:
        st.error(f"Image generation error: {str(e)}")
        return []

def chat_with_model(prompt: str) -> str:
    """Handle LLM communication with error checking"""
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
        response.raise_for_status()
        
        return response.json()["choices"][0]["message"]["content"]
    
    except requests.exceptions.RequestException as e:
        st.error(f"API Error: {str(e)}")
        return "I'm having trouble responding right now. Please try again later."

def img_to_b64(img: Image.Image) -> str:
    """Convert image to base64 string"""
    buf = BytesIO()
    img.convert("RGB").save(buf, format="JPEG")
    return base64.b64encode(buf.getvalue()).decode()

def generate_companion_image(companion: Dict) -> Image.Image:
    """Generate companion portrait with fallback"""
    prompt = f"8k portrait of {companion['name']}, {companion['appearance']}, " \
             f"{companion['mood']}, {companion['setting']}, detailed facial features, expressive eyes"
    
    images = generate_image(prompt, st.session_state.image_model)
    if images:
        companion['images'] = images
        return images[0]
    return None

# ========== UI COMPONENTS ==========
st.set_page_config(
    page_title="Virtual Companions",
    page_icon="💋",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Sidebar for companion management
with st.sidebar:
    st.title("💖 Companion Hub")
    
    # Companion selection
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
    
    # New companion creation
    with st.expander("➕ New Companion", expanded=not st.session_state.companions):
        with st.form("companion_creator"):
            name = st.text_input("Name", placeholder="Enter companion's name")
            appearance = st.text_area("Appearance Description", 
                                    placeholder="Detailed physical description")
            personality = st.text_area("Personality Traits",
                                      placeholder="Personality characteristics")
            relationship = st.selectbox("Relationship", RELATIONSHIPS)
            setting = st.selectbox("Default Setting", SETTINGS)
            
            if st.form_submit_button("Create Companion") and name:
                new_companion = {
                    "name": name,
                    "appearance": appearance,
                    "personality": personality,
                    "relationship": relationship,
                    "setting": setting,
                    "mood": "Neutral",
                    "images": [],
                    "chat_history": []
                }
                st.session_state.companions[name] = new_companion
                st.session_state.active_companion = name
                generate_companion_image(new_companion)
                st.rerun()

    # Application settings
    st.subheader("⚙️ Settings")
    st.radio("Image Style", list(IMG_MODELS.keys()), key="image_model")

# Main chat interface
if st.session_state.active_companion:
    companion = st.session_state.companions[st.session_state.active_companion]
    
    # Profile header
    cols = st.columns([1, 4])
    with cols[0]:
        if companion.get('images'):
            st.image(companion['images'][0], width=150)
    with cols[1]:
        st.title(companion['name'])
        st.caption(f"💞 {companion['relationship']} | 🌍 {companion['setting']} | 😊 {companion['mood']}")
    
    # Chat history
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
    
    # Chat controls
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
            
            # Message handling with initialization
            msg = ""
            st.subheader("Quick Messages")
            quick_cols = st.columns(3)
            
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
            final_msg = custom_msg or msg  # Use initialized msg
            
            if st.form_submit_button("Send") and final_msg:
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

    # Scene management
    st.divider()
    st.subheader("🎭 Interactive Scenes")
    
    scene_actions = {
        "💞 Romantic Scene": ["Slow Dance", "First Kiss", "Candlelight Dinner"],
        "🔥 Erotic Scene": ["Undressing", "Oral Play", "Full Sex"],
        "😈 Kinky Scene": ["Bondage", "Sensation Play", "Roleplay"]
    }
    
    for scene_type, actions in scene_actions.items():
        with st.expander(scene_type):
            cols = st.columns(3)
            for i, action in enumerate(actions):
                with cols[i]:
                    if st.button(action):
                        scene_prompts = {
                            "Slow Dance": f"{companion['name']} takes you in their arms for a slow, sensual dance",
                            "First Kiss": f"{companion['name']} leans in for your first passionate kiss",
                            "Candlelight Dinner": f"You share an intimate candlelight dinner with {companion['name']}",
                            "Undressing": f"{companion['name']} slowly undresses before you",
                            "Oral Play": f"{companion['name']} kneels before you with hungry eyes",
                            "Full Sex": f"{companion['name']} leads you to bed for passionate lovemaking",
                            "Bondage": f"{companion['name']} ties you up with expert knots",
                            "Sensation Play": f"{companion['name']} teases you with feathers and ice",
                            "Roleplay": f"{companion['name']} suggests an exciting roleplay scenario"
                        }
                        scene = scene_prompts.get(action, "")
                        
                        if scene:
                            detailed_scene = chat_with_model(f"""
                            Expand this scene in vivid detail: {scene}. 
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

    # Current scene display
    if st.session_state.current_scene.get('description'):
        st.subheader("Current Scene")
        st.write(st.session_state.current_scene['description'])
        
        if st.session_state.current_scene.get('images'):
            st.image(
                st.session_state.current_scene['images'][0],
                caption=companion['name'],
                use_column_width=True
            )
        
        # Scene controls
        cols = st.columns(3)
        scene_controls = {
            "❤️ Continue Scene": "Continue this scene naturally",
            "📸 Add Scene Image": "Generate additional scene image",
            "💾 Save Scene": "Save to companion's memory"
        }
        
        for i, (label, action) in enumerate(scene_controls.items()):
            with cols[i]:
                if st.button(label):
                    if label == "❤️ Continue Scene":
                        continued_scene = chat_with_model(f"""
                        Continue this scene: {st.session_state.current_scene['description']}
                        Maintain {companion['name']}'s personality: {companion['personality']}
                        Current mood: {companion['mood']}
                        """)
                        st.session_state.current_scene['description'] += "\n\n" + continued_scene
                    
                    elif label == "📸 Add Scene Image":
                        new_images = generate_image(
                            f"{st.session_state.current_scene['description']}, 8k detailed photo",
                            st.session_state.image_model
                        )
                        st.session_state.current_scene['images'].extend(new_images)
                    
                    elif label == "💾 Save Scene":
                        companion['chat_history'].append({
                            "role": "system",
                            "content": f"Saved scene: {st.session_state.current_scene['description']}",
                            "images": st.session_state.current_scene['images']
                        })
                        st.session_state.current_scene = {"description": "", "images": [], "script": ""}
                    
                    st.rerun()

else:
    # Welcome screen
    st.title("Virtual Companion Experience")
    st.subheader("Your personalized AI relationship simulator")
    
    if st.session_state.companions:
        st.warning("Select a companion from the sidebar or create a new one")
    else:
        st.info("Create your first companion using the sidebar!")
    
    st.image("https://i.imgur.com/JQJZQYF.jpg", 
            caption="Your perfect companion awaits",
            use_column_width=True)
    
    st.markdown("""
    ### Features:
    - 🎭 Fully interactive companions with memory
    - 💬 Natural conversation with emotional depth
    - 🖼️ Dynamic image generation based on interactions
    - 🔥 Customizable relationship dynamics
    - 🎭 Pre-built intimate scenarios
    """)
